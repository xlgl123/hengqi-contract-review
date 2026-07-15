from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.db import ReviewStore
from app.errors import ContractReviewError, UnsupportedDocumentError
from app.parsers.service import parse_pasted_text, parse_upload
from app.review.service import ReviewService
from app.schemas import ReviewListItem, ReviewResult


settings = get_settings()
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


@app.get("/api/health")
def health() -> dict[str, object]:
    return {
        "status": "ok",
        "ai_configured": settings.ai_enabled,
        "model": settings.ai_model_review if settings.ai_enabled else None,
    }


@app.get("/api/sample")
def sample() -> dict[str, str]:
    return {
        "filename": "天河云创技术服务合同（演示）.txt",
        "text": settings.sample_path.read_text(encoding="utf-8"),
        "recommended_role": "service_provider",
    }


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
            content = await file.read(settings.max_upload_bytes + 1)
            parsed = parse_upload(file.filename, content, settings)
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
