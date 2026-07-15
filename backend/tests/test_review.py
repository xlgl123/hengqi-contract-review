from __future__ import annotations

import unittest
from unittest.mock import patch

from app.config import get_settings
from app.parsers.service import parse_pasted_text
from app.review.ai_client import AIClient
from app.review.rules import build_risk_bill, run_rules
from app.review.service import validate_ai_risks
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


if __name__ == "__main__":
    unittest.main()
