from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


Severity = Literal["high", "medium", "low"]
EngineMode = Literal["hybrid_ai", "rules_demo", "hybrid_fallback"]
AIProvider = Literal["siliconflow", "deepseek"]


class DocumentBlock(BaseModel):
    block_id: str
    kind: Literal["paragraph", "table_row"] = "paragraph"
    text: str
    page: int | None = None
    paragraph_index: int | None = None
    table_index: int | None = None
    source_order: int

    @field_validator("text")
    @classmethod
    def text_must_not_be_empty(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("document block text cannot be empty")
        return value


class ParsedContract(BaseModel):
    filename: str
    file_type: Literal["docx", "pdf", "txt", "pasted_text"]
    sha256: str
    text_length: int
    page_count: int | None = None
    blocks: list[DocumentBlock]

    @property
    def full_text(self) -> str:
        return "\n".join(f"[{block.block_id}] {block.text}" for block in self.blocks)


class RiskItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    risk_id: str
    category: str
    severity: Severity
    risk_type: Literal["existing_clause", "missing_clause"]
    title: str
    source_block_ids: list[str] = Field(default_factory=list)
    quote: str = ""
    legal_issue: str
    business_impact: str
    basis_ids: list[str] = Field(default_factory=list)
    ideal_revision: str
    compromise_revision: str
    bottom_line: str
    negotiation_message: str
    confidence: Literal["high", "medium", "low"]
    human_review_required: bool = False
    source: Literal["rule", "ai"] = "rule"


class ContractSummary(BaseModel):
    contract_type: str
    our_role: str
    counterparty_role: str
    key_terms: list[str]
    must_fix: list[str]


class RiskBill(BaseModel):
    total_risks: int
    high: int
    medium: int
    low: int
    payment_exposure: str
    acceptance_exposure: str
    liability_exposure: str
    ip_exposure: str


class ReviewResult(BaseModel):
    review_id: str
    engine_mode: EngineMode
    model_name: str | None = None
    warnings: list[str] = Field(default_factory=list)
    filename: str
    file_type: str
    text_length: int
    summary: ContractSummary
    risk_bill: RiskBill
    risks: list[RiskItem]
    created_at: str
    expires_at: str


class ReviewListItem(BaseModel):
    review_id: str
    filename: str
    engine_mode: EngineMode
    contract_type: str
    total_risks: int
    high_risks: int
    created_at: str
    expires_at: str


class AIReviewPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    contract_type: str = "经营合同"
    counterparty_role: str = "合同相对方"
    key_terms: list[str] = Field(default_factory=list)
    risks: list[RiskItem] = Field(default_factory=list)


class AISettingsRequest(BaseModel):
    provider: AIProvider
    api_key: str = Field(min_length=16, max_length=512)
    model: str = Field(min_length=3, max_length=160)

    @field_validator("api_key", "model")
    @classmethod
    def strip_ai_setting(cls, value: str) -> str:
        return value.strip()


class AISettingsStatus(BaseModel):
    configured: bool
    provider: AIProvider
    base_url: str
    model: str
    key_hint: str | None = None
    storage: Literal["memory_only"] = "memory_only"
    tested_model: str | None = None
    test_tokens: int | None = None
