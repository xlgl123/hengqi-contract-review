from __future__ import annotations

import re
from collections.abc import Iterable

from app.schemas import DocumentBlock, ParsedContract, RiskBill, RiskItem


ROLE_LABELS = {
    "service_provider": ("乙方/服务提供方", "甲方/客户方"),
    "customer": ("甲方/客户方", "乙方/服务提供方"),
    "seller": ("销售方", "采购方"),
    "buyer": ("采购方", "销售方"),
}


def role_labels(role: str) -> tuple[str, str]:
    return ROLE_LABELS.get(role, ("我方", "合同相对方"))


def classify_contract(parsed: ParsedContract) -> str:
    text = "\n".join(block.text for block in parsed.blocks)
    if any(keyword in text for keyword in ("技术服务", "软件开发", "系统开发", "技术开发")):
        return "技术服务合同"
    if any(keyword in text for keyword in ("采购合同", "采购方", "供应商")):
        return "采购合同"
    if any(keyword in text for keyword in ("销售合同", "买方", "卖方", "购销")):
        return "销售合同"
    return "经营合同"


def find_blocks(blocks: Iterable[DocumentBlock], keywords: tuple[str, ...]) -> list[DocumentBlock]:
    return [block for block in blocks if any(keyword in block.text for keyword in keywords)]


def has_pattern(text: str, patterns: tuple[str, ...]) -> bool:
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)


def make_risk(
    *,
    risk_id: str,
    category: str,
    severity: str,
    title: str,
    legal_issue: str,
    business_impact: str,
    ideal_revision: str,
    compromise_revision: str,
    bottom_line: str,
    negotiation_message: str,
    block: DocumentBlock | None = None,
    confidence: str = "high",
) -> RiskItem:
    return RiskItem(
        risk_id=risk_id,
        category=category,
        severity=severity,
        risk_type="existing_clause" if block else "missing_clause",
        title=title,
        source_block_ids=[block.block_id] if block else [],
        quote=block.text if block else "",
        legal_issue=legal_issue,
        business_impact=business_impact,
        basis_ids=[risk_id.split("-")[0] + "-RULE"],
        ideal_revision=ideal_revision,
        compromise_revision=compromise_revision,
        bottom_line=bottom_line,
        negotiation_message=negotiation_message,
        confidence=confidence,
        human_review_required=severity == "high" and confidence != "high",
        source="rule",
    )


def run_rules(parsed: ParsedContract, role: str) -> list[RiskItem]:
    blocks = parsed.blocks
    full_text = "\n".join(block.text for block in blocks)
    risks: list[RiskItem] = []

    acceptance = find_blocks(blocks, ("验收", "确认交付", "测试通过"))
    acceptance_text = "\n".join(block.text for block in acceptance)
    if not acceptance:
        risks.append(
            make_risk(
                risk_id="TS-ACCEPT-001",
                category="acceptance",
                severity="high",
                title="缺少明确的验收机制",
                legal_issue="合同没有约定验收标准、期限及不反馈时的处理。",
                business_impact="交付是否完成缺少客观节点，可能影响付款、返工范围和违约责任判断。",
                ideal_revision="补充可量化验收标准、5个工作日反馈期限及逾期视为验收通过。",
                compromise_revision="至少明确验收材料、反馈期限和一次性书面提出异议。",
                bottom_line="必须约定明确验收期限，不能无限期等待。",
                negotiation_message="为保证双方交付和结算节奏，建议补充明确的验收标准与反馈期限。",
            )
        )
    elif not has_pattern(
        acceptance_text,
        (r"\d+\s*(个)?(工作)?日", r"验收期限", r"逾期.{0,12}(视为|自动).{0,8}(通过|合格)"),
    ):
        risks.append(
            make_risk(
                risk_id="TS-ACCEPT-002",
                category="acceptance",
                severity="high",
                title="验收条款没有反馈期限",
                legal_issue="条款将付款或履约完成与验收绑定，但没有限定对方反馈时间。",
                business_impact="对方可能长期不确认验收，从而推迟尾款或要求持续修改。",
                ideal_revision="约定收到验收材料后5个工作日内反馈，逾期未书面异议视为通过。",
                compromise_revision="约定10个工作日内一次性书面反馈，逾期视为通过。",
                bottom_line="验收必须有固定期限。",
                negotiation_message="当前验收没有时间边界，会影响双方项目结项，建议增加明确反馈期限。",
                block=acceptance[0],
            )
        )

    scope_blocks = find_blocks(blocks, ("服务内容", "工作内容", "项目范围", "甲方要求", "其他工作"))
    broad_scope = next(
        (
            block
            for block in scope_blocks
            if has_pattern(block.text, (r"根据甲方.{0,8}要求", r"其他.{0,8}(工作|事项|服务)", r"另行通知"))
        ),
        None,
    )
    if broad_scope and role in ("service_provider", "seller"):
        risks.append(
            make_risk(
                risk_id="TS-SCOPE-001",
                category="scope",
                severity="high",
                title="服务范围存在无限扩张空间",
                legal_issue="工作范围包含兜底性表述，且未与变更费用和工期调整联动。",
                business_impact="我方可能被要求无偿追加工作，造成成本和交付期限失控。",
                ideal_revision="删除兜底表述；新增需求必须通过书面变更单确定费用、工期和验收标准。",
                compromise_revision="保留合理配合义务，但限定在附件工作范围内，超出部分另行报价。",
                bottom_line="任何新增交付物都必须同步调整费用或工期。",
                negotiation_message="为避免项目执行中对范围理解不一致，建议用书面变更单管理新增需求。",
                block=broad_scope,
            )
        )

    if "变更" not in full_text and classify_contract(parsed) == "技术服务合同":
        risks.append(
            make_risk(
                risk_id="TS-CHANGE-001",
                category="change_management",
                severity="medium",
                title="缺少需求变更机制",
                legal_issue="合同没有规定需求、范围或交付标准发生变化时如何确认。",
                business_impact="项目过程中容易出现无偿加项、反复返工和延期争议。",
                ideal_revision="新增书面变更流程，明确变更内容、价格、工期和双方确认方式。",
                compromise_revision="至少约定超出原范围的工作由双方另行书面确认。",
                bottom_line="口头新增需求不得自动纳入原合同价。",
                negotiation_message="技术项目需求可能调整，建议提前约定简洁的变更确认流程。",
            )
        )

    ip_blocks = find_blocks(blocks, ("知识产权", "著作权", "源代码", "成果归属"))
    ip_transfer = next(
        (
            block
            for block in ip_blocks
            if has_pattern(block.text, (r"(全部|所有).{0,10}(归甲方|归客户)", r"知识产权.{0,12}甲方所有"))
        ),
        None,
    )
    if ip_transfer and role == "service_provider":
        risks.append(
            make_risk(
                risk_id="TS-IP-001",
                category="intellectual_property",
                severity="high",
                title="知识产权整体转让范围过宽",
                legal_issue="条款可能同时覆盖定制成果、既有工具、通用组件和经验方法。",
                business_impact="我方可能失去复用通用代码和既有技术资产的权利。",
                ideal_revision="客户取得已付费定制成果权利；我方既有技术、通用组件和工具仍归我方。",
                compromise_revision="对定制成果转让，但为我方保留通用能力和非客户专属部分的复用权。",
                bottom_line="既有技术与通用组件不得无偿整体转让。",
                negotiation_message="为区分本项目定制成果与我方既有技术，建议补充知识产权边界。",
                block=ip_transfer,
            )
        )
    elif not ip_blocks:
        risks.append(
            make_risk(
                risk_id="TS-IP-002",
                category="intellectual_property",
                severity="medium",
                title="缺少知识产权归属约定",
                legal_issue="合同未明确项目成果、既有技术和第三方素材的权利边界。",
                business_impact="交付后双方可能就使用、修改、转授权和复用发生争议。",
                ideal_revision="分别约定定制成果、既有技术、通用组件和第三方材料的权利。",
                compromise_revision="至少明确交付成果的使用范围及双方既有知识产权不受影响。",
                bottom_line="必须明确交付成果能否使用、修改和再授权。",
                negotiation_message="为避免交付后的使用争议，建议明确项目成果及既有技术的权利边界。",
            )
        )

    liability_blocks = find_blocks(blocks, ("赔偿", "损失", "违约责任", "无限责任"))
    unlimited = next(
        (
            block
            for block in liability_blocks
            if has_pattern(block.text, (r"(全部|一切|所有).{0,8}损失", r"无限责任", r"任何.{0,5}损失"))
        ),
        None,
    )
    liability_cap_present = has_pattern(full_text, (r"责任上限", r"赔偿.{0,12}(不超过|以).{0,12}(合同|已付|总价)"))
    if unlimited and not liability_cap_present:
        risks.append(
            make_risk(
                risk_id="TS-LIABILITY-001",
                category="liability",
                severity="high",
                title="赔偿责任没有上限",
                legal_issue="赔偿范围使用概括性表述，未限制责任总额或间接损失。",
                business_impact="小额合同可能产生远高于合同金额的赔偿暴露。",
                ideal_revision="一般违约责任总额不超过合同已付金额，并排除间接损失和可得利益损失。",
                compromise_revision="责任上限设为合同总价；故意或重大过失等法定例外另行处理。",
                bottom_line="一般违约责任必须设置可计算上限。",
                negotiation_message="为保持合同金额与责任风险匹配，建议增加一般责任上限。",
                block=unlimited,
            )
        )

    termination_blocks = find_blocks(blocks, ("解除", "终止", "随时取消"))
    unilateral = next(
        (
            block
            for block in termination_blocks
            if has_pattern(block.text, (r"甲方.{0,8}(随时|单方).{0,8}(解除|终止)", r"客户.{0,8}无需理由.{0,8}终止"))
        ),
        None,
    )
    if unilateral and role == "service_provider":
        risks.append(
            make_risk(
                risk_id="TS-TERM-001",
                category="termination",
                severity="high",
                title="对方可无条件单方解除",
                legal_issue="对方享有随时解除权，但未约定已完成工作结算和投入补偿。",
                business_impact="我方前期投入可能无法回收，项目资源安排也会受到影响。",
                ideal_revision="仅在重大违约且整改期届满后解除；无过错解除应结算已完成工作并补偿承诺成本。",
                compromise_revision="允许提前通知解除，但必须支付已完成工作和不可撤销成本。",
                bottom_line="解除时已完成工作必须结算。",
                negotiation_message="可以保留项目调整空间，但建议同步明确终止时的工作量确认和结算。",
                block=unilateral,
            )
        )

    dispute_blocks = find_blocks(blocks, ("人民法院", "仲裁委员会", "争议解决"))
    adverse_venue = next(
        (
            block
            for block in dispute_blocks
            if has_pattern(block.text, (r"甲方所在地.{0,8}人民法院", r"客户所在地.{0,8}法院"))
        ),
        None,
    )
    if adverse_venue and role in ("service_provider", "seller"):
        risks.append(
            make_risk(
                risk_id="TS-DISPUTE-001",
                category="dispute_resolution",
                severity="medium",
                title="争议解决地单方偏向对方",
                legal_issue="争议只能在对方所在地处理。",
                business_impact="发生纠纷时我方可能承担额外差旅、时间和代理成本。",
                ideal_revision="约定合同履行地法院或双方认可的仲裁机构。",
                compromise_revision="选择与交易有实际联系且双方成本相对均衡的地点。",
                bottom_line="确认管辖约定明确且实际可执行。",
                negotiation_message="为平衡双方争议处理成本，建议选择合同履行地或中立仲裁机构。",
                block=adverse_venue,
                confidence="medium",
            )
        )

    return risks


def build_risk_bill(risks: list[RiskItem]) -> RiskBill:
    counts = {severity: sum(1 for risk in risks if risk.severity == severity) for severity in ("high", "medium", "low")}
    categories = {risk.category: risk for risk in risks}
    return RiskBill(
        total_risks=len(risks),
        high=counts["high"],
        medium=counts["medium"],
        low=counts["low"],
        payment_exposure="受验收节点影响" if "acceptance" in categories else "未发现明显付款触发风险",
        acceptance_exposure="验收机制需优先修改" if "acceptance" in categories else "已识别到基本验收安排",
        liability_exposure="责任上限不明确" if "liability" in categories else "未发现明显无限责任表述",
        ip_exposure="知识产权边界需修改" if "intellectual_property" in categories else "未发现明显知识产权缺失",
    )

