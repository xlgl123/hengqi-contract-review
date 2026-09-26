from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

from app.config import get_settings
from app.parsers.service import parse_pasted_text
from app.review.ai_client import AIClient, parse_ai_review_content
from app.review.legal_basis import load_legal_library
from app.review.rules import build_risk_bill, run_rules
from app.review.service import merge_risks, sanitize_ai_legal_claims, validate_ai_risks
from app.schemas import AIReviewPayload, RiskItem


CONTRACT = """技术服务合同
第一条 服务内容
乙方负责开发系统，并根据甲方要求完成其他工作。
第二条 付款
系统经甲方验收合格后支付全部款项。
第三条 验收
项目完成后由甲方验收。
第四条 知识产权
全部成果、源代码及通用组件知识产权均归甲方所有。
第五条 违约
乙方赔偿甲方因此产生的一切损失。
第六条 解除
甲方可随时单方解除合同，无需承担责任。
第七条 争议
争议提交甲方所在地人民法院。
"""

CONTRACT_4B = """软件系统开发与技术服务合同
第一条 付款
甲方认为项目存在任何问题时，有权暂停支付全部未付款项，且不承担逾期付款责任。
第二条 验收
具体功能、技术标准和验收要求由双方在项目实施过程中另行协商。
第三条 知识产权
项目形成的全部源代码、通用组件及开发工具均无偿归甲方所有。
第四条 数据
乙方有权将甲方客户数据用于产品训练、算法优化、商业分析或其他用途，无需取得相关个人同意。
第五条 解除
甲方有权根据自身经营需要随时单方解除合同，无需说明理由，也无需承担违约责任。
第六条 争议
任何一方均可向甲方所在地或乙方所在地人民法院起诉，也可以提交广州仲裁委员会仲裁。
"""


class ReviewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.parsed = parse_pasted_text(CONTRACT)

    def test_rules_find_core_provider_risks(self) -> None:
        risks = run_rules(self.parsed, "service_provider")
        categories = {risk.category for risk in risks}
        self.assertIn("acceptance", categories)
        self.assertIn("scope", categories)
        self.assertIn("intellectual_property", categories)
        self.assertIn("liability", categories)
        self.assertIn("termination", categories)
        self.assertTrue(all(risk.business_impact for risk in risks))
        self.assertTrue(all(risk.ideal_revision for risk in risks))
        acceptance = next(risk for risk in risks if risk.category == "acceptance")
        self.assertEqual(acceptance.legal_nature, "agreement_gap")
        self.assertIn("CIVIL-845", acceptance.basis_ids)
        dispute = next(risk for risk in risks if risk.category == "dispute_resolution")
        self.assertEqual(dispute.legal_nature, "enforceability_risk")
        self.assertEqual(dispute.basis_ids, ["CPL-35"])

    def test_4b_rules_cover_cashflow_data_termination_and_dispute(self) -> None:
        risks = run_rules(parse_pasted_text(CONTRACT_4B), "service_provider")
        by_id = {risk.risk_id: risk for risk in risks}
        self.assertIn("TS-PAYMENT-001", by_id)
        self.assertIn("TS-DATA-001", by_id)
        self.assertIn("TS-TERM-001", by_id)
        self.assertIn("TS-DISPUTE-002", by_id)
        self.assertEqual(by_id["TS-PAYMENT-001"].basis_ids, ["CIVIL-509", "CIVIL-579"])
        self.assertIn("PIPL-6", by_id["TS-DATA-001"].basis_ids)
        self.assertIn("ARB-27", by_id["TS-DISPUTE-002"].basis_ids)
        self.assertIn("甲方保证数据来源", by_id["TS-DATA-001"].ideal_revision)
        self.assertIn("不得由乙方兜底", by_id["TS-DATA-001"].bottom_line)

    def test_local_rules_suppress_ai_duplicates_and_sort_business_priority(self) -> None:
        parsed = parse_pasted_text(CONTRACT_4B)
        local = run_rules(parsed, "service_provider")
        ai = [
            RiskItem(
                risk_id="AI-PAY",
                category="payment",
                severity="high",
                risk_type="existing_clause",
                title="AI重复付款风险",
                source_block_ids=[parsed.blocks[1].block_id],
                quote=parsed.blocks[1].text,
                legal_issue="问题",
                business_impact="影响",
                ideal_revision="理想",
                compromise_revision="妥协",
                bottom_line="底线",
                negotiation_message="话术",
                confidence="high",
                source="ai",
            ),
            RiskItem(
                risk_id="AI-OTHER",
                category="general",
                severity="medium",
                risk_type="existing_clause",
                title="独立补充风险",
                source_block_ids=[parsed.blocks[0].block_id],
                quote=parsed.blocks[0].text,
                legal_issue="问题",
                business_impact="影响",
                ideal_revision="理想",
                compromise_revision="妥协",
                bottom_line="底线",
                negotiation_message="话术",
                confidence="high",
                source="ai",
            ),
            RiskItem(
                risk_id="AI-ACCEPT",
                category="acceptance",
                severity="high",
                risk_type="existing_clause",
                title="AI重复验收风险",
                source_block_ids=[parsed.blocks[2].block_id],
                quote=parsed.blocks[2].text,
                legal_issue="验收标准和期限不明确",
                business_impact="影响结项",
                ideal_revision="明确验收标准和期限",
                compromise_revision="明确期限",
                bottom_line="必须有期限",
                negotiation_message="请明确验收",
                confidence="high",
                source="ai",
            ),
        ]
        merged = merge_risks(local, ai)
        self.assertNotIn("AI-PAY", {risk.risk_id for risk in merged})
        self.assertNotIn("AI-ACCEPT", {risk.risk_id for risk in merged})
        self.assertIn("AI-OTHER", {risk.risk_id for risk in merged})
        high_titles = [risk.category for risk in merged if risk.severity == "high"]
        self.assertEqual(high_titles[:4], ["payment", "data_privacy", "intellectual_property", "termination"])

    def test_unverified_ai_penalty_claim_is_neutralized(self) -> None:
        risk = RiskItem(
            risk_id="AI-LEGAL-CLAIM",
            category="data_privacy",
            severity="high",
            risk_type="existing_clause",
            title="数据条款将导致行政处罚",
            source_block_ids=[],
            quote="",
            legal_issue="违反《个人信息保护法》第六十六条。",
            business_impact="最高罚款5000万元或上一年度营业额5%，并承担连带责任。",
            ideal_revision="限定处理目的",
            compromise_revision="限定用途",
            bottom_line="不得无限使用",
            negotiation_message="请限定用途",
            confidence="medium",
            source="ai",
        )
        sanitized, changed = sanitize_ai_legal_claims(risk)
        self.assertTrue(changed)
        self.assertNotIn("5000", sanitized.business_impact)
        self.assertNotIn("第六十六条", sanitized.legal_issue)
        self.assertIn("人工复核", sanitized.legal_issue)

    def test_risk_bill_counts_severity(self) -> None:
        risks = run_rules(self.parsed, "service_provider")
        bill = build_risk_bill(risks)
        self.assertEqual(bill.total_risks, len(risks))
        self.assertGreaterEqual(bill.high, 4)

    def test_ai_risk_with_fake_quote_is_rejected(self) -> None:
        risk = RiskItem(
            risk_id="AI-001",
            category="payment",
            severity="high",
            risk_type="existing_clause",
            title="虚构引用",
            source_block_ids=[self.parsed.blocks[0].block_id],
            quote="合同中不存在的句子",
            legal_issue="问题",
            business_impact="影响",
            ideal_revision="理想",
            compromise_revision="妥协",
            bottom_line="底线",
            negotiation_message="话术",
            confidence="high",
            source="ai",
        )
        payload = AIReviewPayload(risks=[risk])
        valid, warnings = validate_ai_risks(payload, self.parsed)
        self.assertEqual(valid, [])
        self.assertEqual(len(warnings), 1)

    def test_ai_cannot_inject_unverified_legal_basis(self) -> None:
        risk = RiskItem(
            risk_id="AI-LEGAL-001",
            category="payment",
            severity="high",
            risk_type="existing_clause",
            title="虚构法条测试",
            source_block_ids=[self.parsed.blocks[0].block_id],
            quote=self.parsed.blocks[0].text,
            legal_issue="问题",
            business_impact="影响",
            basis_ids=["FAKE-LAW-999"],
            legal_nature="compliance_risk",
            legal_conclusion="模型声称违法",
            ideal_revision="理想",
            compromise_revision="妥协",
            bottom_line="底线",
            negotiation_message="话术",
            confidence="high",
            source="ai",
        )
        payload = AIReviewPayload(risks=[risk])
        valid, warnings = validate_ai_risks(payload, self.parsed)
        self.assertEqual(warnings, [])
        self.assertEqual(valid[0].basis_ids, [])
        self.assertEqual(valid[0].legal_bases, [])
        self.assertEqual(valid[0].legal_nature, "commercial_risk")
        self.assertIn("未绑定经核验法条", valid[0].legal_conclusion)

    def test_siliconflow_flash_uses_fast_non_thinking_request(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "AI_BASE_URL": "https://api.siliconflow.cn/v1",
                "AI_MODEL_REVIEW": "deepseek-ai/DeepSeek-V4-Flash",
                "AI_ENABLE_THINKING": "false",
                "AI_MAX_TOKENS": "4096",
            },
        ):
            body = AIClient(get_settings())._request_body([])
        self.assertEqual(body["enable_thinking"], False)
        self.assertEqual(body["max_tokens"], 4096)
        self.assertNotIn("thinking", body)
        self.assertNotIn("reasoning_effort", body)

    def test_ai_parser_accepts_common_aliases_and_ignores_extra_fields(self) -> None:
        content = """```json
        {
          "contract_type": "技术服务合同",
          "counterparty_role": "甲方",
          "key_terms": "付款与验收",
          "extra_summary": "ignored",
          "risks": [{
            "id": "AI-9",
            "category": "payment",
            "severity": "高风险",
            "type": "存在条款",
            "risk_title": "付款期限过长",
            "source_block_id": "text-p1",
            "original_text": "技术服务合同",
            "issue": "付款条件缺少时间边界",
            "impact": "回款周期不可控",
            "suggestion": "约定固定付款期限",
            "confidence": "高",
            "unexpected": "ignored"
          }]
        }
        ```"""
        payload, warnings = parse_ai_review_content(content)
        self.assertEqual(warnings, [])
        self.assertEqual(payload.key_terms, ["付款与验收"])
        self.assertEqual(payload.risks[0].risk_id, "AI-9")
        self.assertEqual(payload.risks[0].severity, "high")
        self.assertEqual(payload.risks[0].risk_type, "existing_clause")
        self.assertEqual(payload.risks[0].source, "ai")

    def test_ai_parser_normalizes_chinese_categories_for_deduplication(self) -> None:
        content = """{
          "risks": [
            {
              "risk_id": "AI-IP",
              "category": "知识产权",
              "severity": "high",
              "risk_type": "existing_clause",
              "title": "既有技术被转让",
              "source_block_ids": ["text-p1"],
              "quote": "技术服务合同",
              "legal_issue": "既有技术边界不清",
              "business_impact": "无法复用技术",
              "ideal_revision": "保留既有技术",
              "confidence": "high"
            },
            {
              "risk_id": "AI-PAY",
              "category": "付款与价格",
              "severity": "high",
              "risk_type": "existing_clause",
              "title": "暂停全部付款",
              "source_block_ids": ["text-p3"],
              "quote": "第二条 付款",
              "legal_issue": "付款暂停条件主观",
              "business_impact": "影响现金流",
              "ideal_revision": "限定暂停范围",
              "confidence": "high"
            },
            {
              "risk_id": "AI-DATA",
              "category": "data_usage",
              "severity": "high",
              "risk_type": "existing_clause",
              "title": "项目数据可任意使用",
              "source_block_ids": ["text-p1"],
              "quote": "技术服务合同",
              "legal_issue": "数据使用目的过宽",
              "business_impact": "增加数据风险",
              "ideal_revision": "限定数据用途",
              "confidence": "high"
            }
          ]
        }"""
        payload, warnings = parse_ai_review_content(content)
        self.assertEqual(warnings, [])
        self.assertEqual(
            [risk.category for risk in payload.risks],
            ["intellectual_property", "payment", "data_privacy"],
        )

    def test_ai_parser_keeps_valid_items_when_one_item_is_invalid(self) -> None:
        content = """{
          "risks": [
            {"title": "缺字段"},
            {
              "risk_id": "AI-002",
              "category": "data",
              "severity": "medium",
              "risk_type": "missing_clause",
              "title": "缺少数据删除安排",
              "legal_issue": "合同未约定删除机制",
              "business_impact": "合作结束后数据持续留存",
              "ideal_revision": "约定终止后删除数据",
              "confidence": "medium"
            }
          ]
        }"""
        payload, warnings = parse_ai_review_content(content)
        self.assertEqual(len(payload.risks), 1)
        self.assertEqual(payload.risks[0].risk_id, "AI-002")
        self.assertEqual(len(warnings), 1)


class AIClientAsyncTests(unittest.IsolatedAsyncioTestCase):
    async def test_review_retries_once_after_truncated_json(self) -> None:
        parsed = parse_pasted_text(CONTRACT)
        with patch.dict(
            "os.environ",
            {
                "AI_API_KEY": "test-key-not-a-real-secret-123",
                "AI_BASE_URL": "https://api.siliconflow.cn/v1",
                "AI_MODEL_REVIEW": "deepseek-ai/DeepSeek-V4-Flash",
            },
        ):
            client = AIClient(get_settings())
        valid_content = """{
          "contract_type": "技术服务合同",
          "counterparty_role": "甲方",
          "key_terms": [],
          "risks": [{
            "risk_id": "AI-001",
            "category": "payment",
            "severity": "high",
            "risk_type": "existing_clause",
            "title": "付款条件不明确",
            "source_block_ids": ["text-p3"],
            "quote": "第二条 付款",
            "legal_issue": "付款节点缺少明确期限",
            "business_impact": "可能导致回款延迟",
            "ideal_revision": "补充明确付款期限",
            "confidence": "high"
          }]
        }"""
        client._post = AsyncMock(
            side_effect=[
                {
                    "choices": [
                        {
                            "message": {"content": '{"risks": [{"title": "被截断"'},
                            "finish_reason": "length",
                        }
                    ]
                },
                {
                    "choices": [
                        {
                            "message": {"content": valid_content},
                            "finish_reason": "stop",
                        }
                    ]
                },
            ]
        )

        payload, warnings = await client.review(parsed, "乙方/服务提供方", [])

        self.assertEqual(client._post.await_count, 2)
        self.assertEqual(payload.risks[0].risk_id, "AI-001")
        self.assertIn("自动精简重试并恢复", warnings[0])


class LegalLibraryTests(unittest.TestCase):
    def test_library_is_unique_current_and_official(self) -> None:
        library = load_legal_library(get_settings().root_dir)
        bases = library.all()
        self.assertGreaterEqual(len(bases), 10)
        self.assertEqual(len({basis.basis_id for basis in bases}), len(bases))
        self.assertTrue(all(basis.effective_status == "现行有效" for basis in bases))
        official_hosts = ("court.gov.cn", "npc.gov.cn", "cac.gov.cn")
        self.assertTrue(
            all(any(host in basis.official_url for host in official_hosts) for basis in bases)
        )

    def test_enrichment_resolves_only_whitelisted_basis_ids(self) -> None:
        library = load_legal_library(get_settings().root_dir)
        risk = run_rules(parse_pasted_text(CONTRACT), "service_provider")[0]
        enriched = library.enrich(
            risk.model_copy(update={"basis_ids": [*risk.basis_ids, "FAKE-LAW-999"]})
        )
        self.assertNotIn("FAKE-LAW-999", enriched.basis_ids)
        self.assertEqual(
            enriched.basis_ids,
            [basis.basis_id for basis in enriched.legal_bases],
        )


if __name__ == "__main__":
    unittest.main()
