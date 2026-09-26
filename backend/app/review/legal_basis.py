from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from app.schemas import LegalBasis, LegalLibraryInfo, RiskItem


class LegalLibraryFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str
    verified_at: str
    disclaimer: str
    bases: list[LegalBasis] = Field(default_factory=list)


class LegalLibrary:
    def __init__(self, path: Path):
        payload = LegalLibraryFile.model_validate_json(path.read_text(encoding="utf-8"))
        self.version = payload.version
        self.verified_at = payload.verified_at
        self.disclaimer = payload.disclaimer
        self._bases = {basis.basis_id: basis for basis in payload.bases}
        if len(self._bases) != len(payload.bases):
            raise ValueError("法律依据库存在重复basis_id")

    def resolve(self, basis_ids: list[str]) -> list[LegalBasis]:
        return [self._bases[basis_id] for basis_id in basis_ids if basis_id in self._bases]

    def enrich(self, risk: RiskItem) -> RiskItem:
        valid_ids = [basis_id for basis_id in risk.basis_ids if basis_id in self._bases]
        return risk.model_copy(
            update={
                "basis_ids": valid_ids,
                "legal_bases": self.resolve(valid_ids),
            }
        )

    def info(self) -> LegalLibraryInfo:
        sources = sorted({basis.document_name for basis in self._bases.values()})
        return LegalLibraryInfo(
            version=self.version,
            verified_at=self.verified_at,
            basis_count=len(self._bases),
            sources=sources,
            disclaimer=self.disclaimer,
        )

    def all(self) -> list[LegalBasis]:
        return list(self._bases.values())


def load_legal_library(root_dir: Path) -> LegalLibrary:
    return LegalLibrary(root_dir / "data" / "legal_bases.json")
