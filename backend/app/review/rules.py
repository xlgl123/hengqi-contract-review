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
    legal_nature: str = "commercial_risk",
    legal_conclusion: str = "本项主要属于经营风险判断，不等同于违法或条款无效认定。",
    basis_ids: list[str] | None = None,
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
        basis_ids=basis_ids or [],
        legal_nature=legal_nature,
        legal_conclusion=legal_conclusion,
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
                legal_nature="agreement_gap",
                legal_conclusion="《民法典》将验收标准和方法列为技术合同通常应约定的内容；缺失通常属于约定不完整，并不当然导致合同无效。",
                basis_ids=["CIVIL-845"],
            )
        )
    elif not has_pattern(
        acceptance_text,
        (r"\d+\s*(个)?(工作)?日", r"验收期限", r"逾期.{0,12}(视为|自动).{0,8}(通过|合格)"),
    ):
        standards_deferred = has_pattern(
            acceptance_text,
            (r"(验收要求|验收标准|技术标准).{0,20}(另行协商|另行确定|后续确定)",),
        )
        risks.append(
            make_risk(
                risk_id="TS-ACCEPT-002",
                category="acceptance",
                severity="high",
                title="验收标准和反馈期限均不明确" if standards_deferred else "验收条款没有反馈期限",
                legal_issue=(
                    "验收标准被留待项目实施中另行协商，同时没有限定对方反馈时间。"
                    if standards_deferred
                    else "条款将付款或履约完成与验收绑定，但没有限定对方反馈时间。"
                ),
                business_impact=(
                    "对方既可在履约过程中改变验收口径，也可能长期不确认验收，从而推迟尾款或要求持续修改。"
                    if standards_deferred
                    else "对方可能长期不确认验收，从而推迟尾款或要求持续修改。"
                ),
                ideal_revision=(
                    "在附件中写明可量化验收标准，并约定收到验收材料后5个工作日内一次性反馈，"
                    "逾期未书面异议视为通过。"
                    if standards_deferred
                    else "约定收到验收材料后5个工作日内反馈，逾期未书面异议视为通过。"
                ),
                compromise_revision=(
                    "至少在开工前书面确认验收清单，并约定10个工作日内一次性反馈，逾期视为通过。"
                    if standards_deferred
                    else "约定10个工作日内一次性书面反馈，逾期视为通过。"
                ),
                bottom_line="验收必须有固定标准和期限。" if standards_deferred else "验收必须有固定期限。",
                negotiation_message="当前验收没有时间边界，会影响双方项目结项，建议增加明确反馈期限。",
                block=acceptance[0],
                legal_nature="agreement_gap",
                legal_conclusion="法律未统一规定技术项目必须在几日内验收，但验收标准和方法属于技术合同的重要约定；建议通过合同补足时间边界。",
                basis_ids=["CIVIL-845"],
            )
        )

    payment_blocks = find_blocks(blocks, ("付款", "支付", "未付款项", "暂停支付", "停止支付"))
    subjective_payment_stop = next(
        (
            block
            for block in payment_blocks
            if has_pattern(
                block.text,
                (
                    r"(甲方|客户).{0,30}(认为|认定|判断).{0,25}(暂停|拒绝|停止).{0,12}(支付|付款)",
                    r"(甲方|客户).{0,30}(暂停|拒绝|停止).{0,12}(全部|任何)?未?付款",
                    r"(暂停|拒绝|停止).{0,10}支付全部未付款项",
                ),
            )
        ),
        None,
    )
    if subjective_payment_stop and role in ("service_provider", "seller"):
        risks.append(
            make_risk(
                risk_id="TS-PAYMENT-001",
                category="payment",
                severity="high",
                title="对方可凭主观判断暂停全部付款",
                legal_issue="付款暂停条件由对方单方判断，缺少具体触发标准、异议流程和无争议款支付安排。",
                business_impact="对方可以用笼统的项目问题冻结全部回款，直接影响我方现金流和持续履约能力。",
                ideal_revision=(
                    "仅对存在书面证据的重大未解决缺陷暂停对应比例款项；"
                    "对方应一次性说明理由，无争议款按期支付，争议部分通过约定程序处理。"
                ),
                compromise_revision="允许暂缓与争议事项直接对应的部分款项，但不得暂停全部款项或免除逾期责任。",
                bottom_line="已到期且无争议的款项必须按期支付。",
                negotiation_message="为避免小范围争议影响整个项目现金流，建议将暂停付款限定为有证据的争议部分。",
                block=subjective_payment_stop,
                legal_nature="enforceability_risk",
                legal_conclusion=(
                    "合同应按约全面履行，金钱债务未履行时相对方可请求支付；"
                    "双方可以约定合理暂停条件，但仅凭单方主观判断冻结全部到期款项存在适用争议。"
                ),
                basis_ids=["CIVIL-509", "CIVIL-579"],
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
                legal_nature="commercial_risk",
                legal_conclusion="该表述主要造成范围和成本失控风险；仅凭此条不能直接认定违法或无效。",
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
                legal_nature="agreement_gap",
                legal_conclusion="合同变更以双方协商一致为基础；提前约定书面变更流程有助于证明双方是否就新增范围、费用和工期达成一致。",
                basis_ids=["CIVIL-543", "CIVIL-845"],
            )
        )

    ip_blocks = find_blocks(
        blocks,
        ("知识产权", "著作权", "源代码", "成果归属", "通用组件", "开发工具", "既有技术"),
    )
    ip_transfer = next(
        (
            block
            for block in ip_blocks
            if has_pattern(
                block.text,
                (
                    r"(全部|所有).{0,60}(归甲方|归客户)",
                    r"(源代码|通用组件|开发工具|既有技术).{0,60}(归甲方|转让给甲方)",
                    r"知识产权.{0,30}甲方所有",
                ),
            )
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
                legal_nature="commercial_risk",
                legal_conclusion="技术成果归属可以由当事人约定；整体转让并非当然违法，但将既有技术和通用组件一并转让可能造成重大资产损失。",
                basis_ids=["CIVIL-845"],
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
                legal_nature="agreement_gap",
                legal_conclusion="技术成果归属和收益分配属于技术合同通常应明确的内容；缺失容易产生权属和使用范围争议。",
                basis_ids=["CIVIL-845"],
            )
        )

    data_blocks = find_blocks(
        blocks,
        ("个人信息", "客户数据", "用户数据", "数据用于", "产品训练", "算法优化", "商业分析"),
    )
    broad_data_use = next(
        (
            block
            for block in data_blocks
            if has_pattern(
                block.text,
                (
                    r"数据.{0,25}(产品训练|算法优化|商业分析|其他用途)",
                    r"(产品训练|算法优化|商业分析).{0,20}(无需|不需要).{0,12}(同意|授权)",
                    r"(无需|不需要).{0,15}(相关个人|用户|客户).{0,8}(同意|授权)",
                    r"有权.{0,30}数据.{0,20}其他用途",
                ),
            )
        ),
        None,
    )
    if broad_data_use:
        if role in ("service_provider", "seller"):
            impact = (
                "即使合同赋予乙方宽泛权限，乙方仍可能因超出履约目的处理数据而承担监管、赔偿和声誉风险；"
                "甲方数据来源或授权不足也可能向乙方传导风险。"
            )
            ideal = (
                "甲方保证数据来源及必要授权合法；乙方仅按甲方书面指令、在履约必要范围内处理数据。"
                "未经另行书面协议不得用于模型训练、商业分析或其他独立目的；"
                "双方按各自法定义务和过错承担责任，合同终止后按约返还或删除。"
            )
            compromise = (
                "如确需将数据用于产品优化，应限定数据类型、处理目的、去标识化措施和期限，"
                "由甲方确认合法基础，乙方不得取得无限用途授权。"
            )
            bottom = "不得仅凭本合同取得客户个人信息的无限用途，也不得由乙方兜底承担甲方数据来源责任。"
        else:
            impact = "客户数据可能被用于履约之外的训练或商业分析，增加个人投诉、监管调查、泄露及商业秘密暴露风险。"
            ideal = (
                "乙方仅可为履行本合同处理数据，不得用于训练、商业分析或其他独立目的；"
                "明确安全措施、分包限制、事件通知、审计和终止后的返还或删除。"
            )
            compromise = "仅允许使用完成履约所必需的数据；任何额外用途须经甲方书面同意并满足适用法律要求。"
            bottom = "禁止未经另行确认将客户数据用于模型训练、商业分析或向第三方提供。"
        risks.append(
            make_risk(
                risk_id="TS-DATA-001",
                category="data_privacy",
                severity="high",
                title="数据使用目的和授权边界过宽",
                legal_issue="合同试图用概括授权覆盖训练、优化、商业分析等多种目的，且未区分个人信息、业务数据及双方角色。",
                business_impact=impact,
                ideal_revision=ideal,
                compromise_revision=compromise,
                bottom_line=bottom,
                negotiation_message="数据条款需要与实际履约目的和双方角色对应，建议限定用途并单独明确授权、安全与责任边界。",
                block=broad_data_use,
                legal_nature="compliance_risk",
                legal_conclusion=(
                    "个人信息处理应具有明确合理目的并限于最小必要范围；"
                    "如属于委托处理，还应约定目的、方式、期限、安全措施及终止处置。"
                    "是否违法仍需结合数据类型、主体角色、合法基础和实际处理行为判断。"
                ),
                basis_ids=["PIPL-5", "PIPL-6", "PIPL-21", "PIPL-51", "DSL-27"],
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
                legal_nature="enforceability_risk",
                legal_conclusion="损失赔偿仍需受因果关系、实际损失和可预见性限制；合同未设责任上限属于风险分配不利，不代表全部赔偿表述当然无效。",
                basis_ids=["CIVIL-584"],
            )
        )

    termination_blocks = find_blocks(blocks, ("解除", "终止", "随时取消"))
    unilateral = next(
        (
            block
            for block in termination_blocks
            if has_pattern(
                block.text,
                (
                    r"甲方.{0,35}(随时|单方).{0,10}(解除|终止)",
                    r"客户.{0,35}(随时|无需理由|单方).{0,10}(解除|终止)",
                    r"(随时|无需理由).{0,8}单方.{0,8}(解除|终止)",
                ),
            )
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
                legal_nature="enforceability_risk",
                legal_conclusion="单方解除约定是否有效需结合合同性质和条款形成方式判断；解除后已履行部分及结算清理事项仍应依法依约处理。",
                basis_ids=["CIVIL-566", "CIVIL-567"],
            )
        )

    dispute_blocks = find_blocks(blocks, ("人民法院", "仲裁委员会", "仲裁机构", "争议解决"))
    mixed_dispute = next(
        (
            block
            for block in dispute_blocks
            if "人民法院" in block.text and ("仲裁委员会" in block.text or "仲裁机构" in block.text)
        ),
        None,
    )
    if mixed_dispute:
        risks.append(
            make_risk(
                risk_id="TS-DISPUTE-002",
                category="dispute_resolution",
                severity="medium",
                title="争议条款同时选择诉讼和仲裁",
                legal_issue="同一条款并列赋予诉讼和仲裁选择，可能引发仲裁协议是否明确、应由哪个机构受理的程序争议。",
                business_impact="纠纷发生后可能先就管辖和仲裁协议效力争执，增加立案、异议和代理成本。",
                ideal_revision="诉讼与仲裁二选一；如选择仲裁，明确唯一仲裁机构及仲裁事项；如选择诉讼，明确有实际联系的管辖法院。",
                compromise_revision="保留协商前置程序，但协商不成后的正式争议解决方式只能保留一种。",
                bottom_line="诉讼和仲裁不能并列为任意选择，最终受理机构必须可以确定。",
                negotiation_message="当前条款可能先引发程序争议，建议统一为一种明确、可执行的争议解决方式。",
                block=mixed_dispute,
                legal_nature="enforceability_risk",
                legal_conclusion=(
                    "现行《仲裁法》要求仲裁协议具有请求仲裁的意思表示、仲裁事项和选定的仲裁机构；"
                    "已达成有效仲裁协议的，原则上应按仲裁处理。并列诉讼和仲裁会增加解释与程序不确定性。"
                ),
                basis_ids=["ARB-5", "ARB-27", "ARB-29"],
            )
        )

    adverse_venue = next(
        (
            block
            for block in dispute_blocks
            if has_pattern(block.text, (r"甲方所在地.{0,8}人民法院", r"客户所在地.{0,8}法院"))
        ),
        None,
    )
    if adverse_venue and role in ("service_provider", "seller") and not mixed_dispute:
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
                legal_nature="enforceability_risk",
                legal_conclusion=(
                    "合同纠纷可书面选择与争议有实际联系地点的法院，但不得违反级别管辖和专属管辖。"
                    "对方所在地是否有效需结合其与争议的联系判断；即使有效，也可能显著增加我方维权成本。"
                ),
                basis_ids=["CPL-35"],
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
