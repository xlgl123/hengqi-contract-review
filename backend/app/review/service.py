from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.config import Settings
from app.db import ReviewStore
from app.errors import AIReviewError
from app.parsers.common import normalize_text
from app.review.ai_client import AIClient
from app.review.legal_basis import LegalLibrary, load_legal_library
from app.review.rules import build_risk_bill, classify_contract, role_labels, run_rules
from app.schemas import AIReviewPayload, ContractSummary, ParsedContract, ReviewResult, RiskItem


AI_UNVERIFIED_LEGAL_CLAIM = re.compile(
    r"第[一二三四五六七八九十百千万\d]+条|《[^》]{2,40}》|行政处罚|罚款|"
    r"营业额.{0,8}%|最高.{0,15}(?:万元|亿元)|连带责任|当然无效|必然无效|"
    r"构成违法|违反.{0,15}(?:法|条例|规定)"
)

SEVERITY_WEIGHT = {"high": 300, "medium": 200, "low": 100}
CATEGORY_PRIORITY = {
    "payment": 95,
    "data_privacy": 90,
    "intellectual_property": 85,
    "termination": 80,
    "liability": 75,
    "acceptance": 70,
    "scope": 60,
    "change_management": 55,
    "dispute_resolution": 45,
}
LOCAL_CATEGORY_DOMINANCE = {
    "payment",
    "data_privacy",
    "intellectual_property",
    "termination",
    "acceptance",
    "dispute_resolution",
}


def _quote_is_valid(risk: RiskItem, parsed: ParsedContract) -> bool:
    if risk.risk_type == "missing_clause":
        return not risk.source_block_ids and not risk.quote.strip()
    if not risk.source_block_ids or not risk.quote.strip():
        return False
    block_map = {block.block_id: block for block in parsed.blocks}
    if any(block_id not in block_map for block_id in risk.source_block_ids):
        return False
    quote = normalize_text(risk.quote)
    combined = "\n".join(normalize_text(block_map[block_id].text) for block_id in risk.source_block_ids)
    return quote in combined


def validate_ai_risks(payload: AIReviewPayload, parsed: ParsedContract) -> tuple[list[RiskItem], list[str]]:
    valid: list[RiskItem] = []
    warnings: list[str] = []
    seen_ids: set[str] = set()
    for index, risk in enumerate(payload.risks, start=1):
        if risk.risk_id in seen_ids:
            warnings.append(f"AI风险{risk.risk_id}编号重复，已忽略。")
            continue
        if not _quote_is_valid(risk, parsed):
            warnings.append(f"AI风险{risk.risk_id}无法核对原文，已忽略。")
            continue
        seen_ids.add(risk.risk_id)
        valid.append(
            risk.model_copy(
                update={
                    "source": "ai",
                    "basis_ids": [],
                    "legal_bases": [],
                    "legal_nature": "commercial_risk",
                    "legal_conclusion": (
                        "本项由AI补充识别，当前未绑定经核验法条；"
                        "属于经营风险提示，不等同于违法或条款无效认定。"
                    ),
                }
            )
        )
    return valid, warnings


def merge_risks(local: list[RiskItem], ai: list[RiskItem]) -> list[RiskItem]:
    merged = list(local)
    local_categories = {risk.category for risk in local}
    occupied = {
        (risk.category, risk.source_block_ids[0] if risk.source_block_ids else "missing")
        for risk in local
    }
    for risk in ai:
        key = (risk.category, risk.source_block_ids[0] if risk.source_block_ids else "missing")
        local_rule_is_authoritative = (
            risk.category in LOCAL_CATEGORY_DOMINANCE and risk.category in local_categories
        )
        if key not in occupied and not local_rule_is_authoritative:
            merged.append(risk)
            occupied.add(key)
    return sorted(
        merged,
        key=lambda item: (
            -(SEVERITY_WEIGHT[item.severity] + CATEGORY_PRIORITY.get(item.category, 50)),
            item.risk_id,
        ),
    )


def sanitize_ai_legal_claims(risk: RiskItem) -> tuple[RiskItem, bool]:
    if risk.source != "ai":
        return risk, False
    generated_text = " ".join((risk.title, risk.legal_issue, risk.business_impact))
    if not AI_UNVERIFIED_LEGAL_CLAIM.search(generated_text):
        return risk, False
    safe_title = re.sub(r"(违法|无效|必然承担连带责任)", "存在待复核法律风险", risk.title)
    return (
        risk.model_copy(
            update={
                "title": safe_title,
                "legal_issue": "该安排可能涉及合规、效力或责任争议，但AI未绑定经核验依据，需人工复核。",
                "business_impact": (
                    "可能增加监管应对、争议处理、赔偿或声誉成本；"
                    "具体责任类型和金额需结合交易事实与经核验法律依据判断。"
                ),
            }
        ),
        True,
    )


def extract_key_terms(parsed: ParsedContract) -> list[str]:
    patterns = (
        ("合同金额", r"(?:合同总价|合同金额|服务费)[^\n]{0,35}"),
        ("付款", r"(?:付款|支付)[^\n]{0,45}"),
        ("服务期限", r"(?:服务期限|项目周期|合同期限)[^\n]{0,35}"),
        ("验收", r"验收[^\n]{0,45}"),
    )
    text = "\n".join(block.text for block in parsed.blocks)
    terms: list[str] = []
    for label, pattern in patterns:
        match = re.search(pattern, text)
        if match:
            terms.append(f"{label}：{match.group(0).strip()}")
    return terms[:6]


class ReviewService:
    def __init__(self, settings: Settings, store: ReviewStore):
        self.settings = settings
        self.store = store
        self.ai = AIClient(settings)
        self.legal_library: LegalLibrary = load_legal_library(settings.root_dir)

    def update_settings(self, settings: Settings) -> None:
        self.settings = settings
        self.ai = AIClient(settings)

    async def review(self, parsed: ParsedContract, role: str) -> ReviewResult:
        our_role, counterparty_role = role_labels(role)
        local_risks = run_rules(parsed, role)
        warnings: list[str] = []
        ai_payload: AIReviewPayload | None = None
        ai_risks: list[RiskItem] = []

        if self.ai.enabled:
            try:
                ai_payload, parse_warnings = await self.ai.review(parsed, our_role, local_risks)
                warnings.extend(parse_warnings)
                ai_risks, validation_warnings = validate_ai_risks(ai_payload, parsed)
                warnings.extend(validation_warnings)
                engine_mode = "hybrid_ai"
            except AIReviewError as exc:
                engine_mode = "hybrid_fallback"
                warnings.append(f"真实AI审查失败，当前结果仅来自本地原创规则：{exc}")
        else:
            engine_mode = "rules_demo"
            warnings.append("未配置AI_API_KEY：当前为本地规则演示，不是DeepSeek实时分析。")

        merged_risks = merge_risks(local_risks, ai_risks)
        sanitized_risks: list[RiskItem] = []
        sanitized_count = 0
        for risk in merged_risks:
            sanitized, changed = sanitize_ai_legal_claims(risk)
            sanitized_risks.append(sanitized)
            sanitized_count += int(changed)
        if sanitized_count:
            warnings.append(f"{sanitized_count}项AI补充包含未经核验的法律结论，已自动改为中性提示。")
        risks = [self.legal_library.enrich(risk) for risk in sanitized_risks]
        must_fix = [risk.title for risk in risks if risk.severity == "high"][:3]
        if not must_fix:
            must_fix = ["当前规则未发现高风险，仍建议结合交易背景进行人工复核。"]

        summary = ContractSummary(
            contract_type=ai_payload.contract_type if ai_payload else classify_contract(parsed),
            our_role=our_role,
            counterparty_role=ai_payload.counterparty_role if ai_payload else counterparty_role,
            key_terms=(ai_payload.key_terms if ai_payload and ai_payload.key_terms else extract_key_terms(parsed)),
            must_fix=must_fix,
        )
        now = datetime.now(UTC)
        expires = now + timedelta(hours=self.settings.result_ttl_hours)
        result = ReviewResult(
            review_id=uuid4().hex,
            engine_mode=engine_mode,
            model_name=self.settings.ai_model_review if engine_mode == "hybrid_ai" else None,
            warnings=warnings,
            filename=parsed.filename,
            file_type=parsed.file_type,
            text_length=parsed.text_length,
            legal_library_version=self.legal_library.version,
            legal_library_verified_at=self.legal_library.verified_at,
            summary=summary,
            risk_bill=build_risk_bill(risks),
            risks=risks,
            document_blocks=parsed.blocks,
            created_at=now.isoformat(),
            expires_at=expires.isoformat(),
        )
        self.store.purge_expired(now.isoformat())
        self.store.save(result)
        return result
