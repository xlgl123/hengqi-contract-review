from __future__ import annotations

from dataclasses import replace
from ipaddress import ip_address
from pathlib import Path
from urllib.parse import quote

from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.db import ReviewStore
from app.errors import ContractReviewError, UnsupportedDocumentError
from app.parsers.service import parse_pasted_text, parse_upload
from app.review.ai_client import AIClient
from app.review.service import ReviewService
from app.reporting import build_review_docx
from app.secure_settings import (
    AICredentialStore,
    SecureSettingsError,
    StoredAISettings,
)
from app.schemas import (
    AISettingsRequest,
    AISettingsStatus,
    LegalBasis,
    LegalLibraryInfo,
    ReviewListItem,
    ReviewExportRequest,
    ReviewResult,
)


settings = get_settings()
credential_store = AICredentialStore(settings.ai_credential_path)
saved_ai_settings = credential_store.load()
ai_storage_mode = "environment" if settings.ai_enabled else "memory_only"
if not settings.ai_enabled and saved_ai_settings:
    settings = replace(
        settings,
        ai_base_url=saved_ai_settings.base_url,
        ai_api_key=saved_ai_settings.api_key,
        ai_model_review=saved_ai_settings.model,
        ai_enable_thinking=False,
        ai_max_tokens=4096,
    )
    ai_storage_mode = "encrypted_local"
store = ReviewStore(settings.database_path)
service = ReviewService(settings, store)

app = FastAPI(
    title="衡契・中小企业合同风险助手",
    version="0.2.0",
    description="面向中小企业的规则与AI联合合同风险审查网页应用。",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)


ALLOWED_ROLES = {"service_provider", "customer", "seller", "buyer"}
AI_PROVIDERS = {
    "siliconflow": {
        "base_url": "https://api.siliconflow.cn/v1",
        "default_model": "deepseek-ai/DeepSeek-V4-Flash",
    },
    "deepseek": {
        "base_url": "https://api.deepseek.com",
        "default_model": "deepseek-v4-flash",
    },
}


def _provider_name(base_url: str) -> str:
    return "siliconflow" if "siliconflow.cn" in base_url.lower() else "deepseek"


def _settings_status(
    *, tested_model: str | None = None, test_tokens: int | None = None
) -> AISettingsStatus:
    current = service.settings
    if current.ai_enabled:
        provider = _provider_name(current.ai_base_url)
        base_url = current.ai_base_url
        model = current.ai_model_review
    else:
        provider = "siliconflow"
        base_url = AI_PROVIDERS[provider]["base_url"]
        model = AI_PROVIDERS[provider]["default_model"]
    return AISettingsStatus(
        configured=current.ai_enabled,
        provider=provider,
        base_url=base_url,
        model=model,
        key_hint=(f"••••{current.ai_api_key[-4:]}" if current.ai_enabled else None),
        storage=ai_storage_mode,
        tested_model=tested_model,
        test_tokens=test_tokens,
    )


def _require_local_request(request: Request) -> None:
    host = request.client.host if request.client else ""
    if host == "testclient":
        return
    try:
        if ip_address(host).is_loopback:
            return
    except ValueError:
        pass
    raise HTTPException(status_code=403, detail="AI配置仅允许在本机操作。")


@app.get("/api/health")
def health() -> dict[str, object]:
    return {
        "status": "ok",
        "ai_configured": service.settings.ai_enabled,
        "model": service.settings.ai_model_review if service.settings.ai_enabled else None,
    }


@app.get("/api/settings/ai", response_model=AISettingsStatus)
def get_ai_settings(request: Request) -> AISettingsStatus:
    _require_local_request(request)
    return _settings_status()


@app.post("/api/settings/ai", response_model=AISettingsStatus)
async def configure_ai_settings(
    payload: AISettingsRequest, request: Request
) -> AISettingsStatus:
    global ai_storage_mode
    _require_local_request(request)
    provider = AI_PROVIDERS[payload.provider]
    candidate = replace(
        service.settings,
        ai_base_url=provider["base_url"],
        ai_api_key=payload.api_key,
        ai_model_review=payload.model or provider["default_model"],
        ai_enable_thinking=False,
        ai_max_tokens=4096,
    )
    try:
        test_result = await AIClient(candidate).test_connection()
    except ContractReviewError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        if payload.remember:
            credential_store.save(
                StoredAISettings(
                    provider=payload.provider,
                    base_url=provider["base_url"],
                    model=candidate.ai_model_review,
                    api_key=payload.api_key,
                )
            )
            ai_storage_mode = "encrypted_local"
        else:
            credential_store.clear()
            ai_storage_mode = "memory_only"
    except SecureSettingsError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    service.update_settings(candidate)
    return _settings_status(
        tested_model=str(test_result["model"]),
        test_tokens=int(test_result["total_tokens"]),
    )


@app.delete("/api/settings/ai", response_model=AISettingsStatus)
def clear_ai_settings(request: Request) -> AISettingsStatus:
    global ai_storage_mode
    _require_local_request(request)
    try:
        credential_store.clear()
    except SecureSettingsError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    service.update_settings(replace(service.settings, ai_api_key=""))
    ai_storage_mode = "memory_only"
    return _settings_status()


@app.get("/api/sample")
def sample() -> dict[str, str]:
    return {
        "filename": "天河云创技术服务合同（演示）.txt",
        "text": settings.sample_path.read_text(encoding="utf-8"),
        "recommended_role": "service_provider",
    }


@app.get("/api/legal-library", response_model=LegalLibraryInfo)
def legal_library_info() -> LegalLibraryInfo:
    return service.legal_library.info()


@app.get("/api/legal-bases", response_model=list[LegalBasis])
def legal_bases() -> list[LegalBasis]:
    return service.legal_library.all()


@app.post("/api/reviews", response_model=ReviewResult)
async def create_review(
    file: UploadFile | None = File(default=None),
    text: str = Form(default=""),
    party_role: str = Form(default="service_provider"),
) -> ReviewResult:
    if party_role not in ALLOWED_ROLES:
        raise HTTPException(status_code=400, detail="不支持的我方身份。")
    if file is None and not text.strip():
        raise HTTPException(status_code=400, detail="请上传文件或粘贴合同文本。")

    try:
        if file is not None:
            content = await file.read(service.settings.max_upload_bytes + 1)
            parsed = parse_upload(file.filename, content, service.settings)
        else:
            parsed = parse_pasted_text(text)
        return await service.review(parsed, party_role)
    except (UnsupportedDocumentError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ContractReviewError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/api/reviews", response_model=list[ReviewListItem])
def list_reviews(limit: int = Query(default=8, ge=1, le=20)) -> list[ReviewListItem]:
    from datetime import UTC, datetime

    store.purge_expired(datetime.now(UTC).isoformat())
    return store.list_recent(limit)


@app.get("/api/reviews/{review_id}", response_model=ReviewResult)
def get_review(review_id: str) -> ReviewResult:
    result = store.get(review_id)
    if result is None:
        raise HTTPException(status_code=404, detail="审查结果不存在或已删除。")
    return result


@app.post("/api/reviews/{review_id}/export/docx")
def export_review_docx(review_id: str, payload: ReviewExportRequest) -> Response:
    result = store.get(review_id)
    if result is None:
        raise HTTPException(status_code=404, detail="审查结果不存在或已删除。")
    report = build_review_docx(result, payload.risk_statuses)
    base_name = Path(result.filename).stem or "合同"
    filename = f"{base_name}-合同风险审查报告.docx"
    return Response(
        content=report,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )


@app.delete("/api/reviews/{review_id}")
def delete_review(review_id: str) -> dict[str, bool]:
    return {"deleted": store.delete(review_id)}


frontend_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if frontend_dist.exists():
    assets_dir = frontend_dist / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        requested = frontend_dist / path
        if path and requested.is_file() and frontend_dist in requested.resolve().parents:
            return FileResponse(requested)
        return FileResponse(frontend_dist / "index.html")
