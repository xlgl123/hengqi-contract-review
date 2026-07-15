from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _load_local_env(path: Path) -> None:
    """Load an optional developer-only env file without adding a runtime dependency."""
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)


@dataclass(frozen=True)
class Settings:
    root_dir: Path
    ai_base_url: str
    ai_api_key: str
    ai_model_review: str
    ai_timeout_seconds: float
    ai_enable_thinking: bool
    ai_max_tokens: int
    result_ttl_hours: int
    max_upload_bytes: int

    @property
    def ai_enabled(self) -> bool:
        return bool(self.ai_api_key.strip())

    @property
    def database_path(self) -> Path:
        configured = os.getenv("DATABASE_PATH", "").strip()
        if configured:
            return Path(configured)
        return self.root_dir / "data" / "mvp.db"

    @property
    def sample_path(self) -> Path:
        return self.root_dir / "data" / "sample_contract.txt"


def get_settings() -> Settings:
    root = Path(__file__).resolve().parents[1]
    _load_local_env(root.parent / ".env.local")
    return Settings(
        root_dir=root,
        ai_base_url=os.getenv("AI_BASE_URL", "https://api.deepseek.com").rstrip("/"),
        ai_api_key=os.getenv("AI_API_KEY", os.getenv("DEEPSEEK_API_KEY", "")),
        ai_model_review=os.getenv("AI_MODEL_REVIEW", "deepseek-v4-pro"),
        ai_timeout_seconds=float(os.getenv("AI_TIMEOUT_SECONDS", "90")),
        ai_enable_thinking=os.getenv("AI_ENABLE_THINKING", "false").strip().lower() in {"1", "true", "yes", "on"},
        ai_max_tokens=int(os.getenv("AI_MAX_TOKENS", "4096")),
        result_ttl_hours=int(os.getenv("RESULT_TTL_HOURS", "24")),
        max_upload_bytes=int(os.getenv("MAX_UPLOAD_BYTES", str(10 * 1024 * 1024))),
    )
