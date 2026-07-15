from __future__ import annotations

from pathlib import Path

from app.config import Settings
from app.errors import UnsupportedDocumentError
from app.parsers.common import safe_display_filename
from app.parsers.docx_parser import parse_docx
from app.parsers.pdf_parser import parse_pdf
from app.parsers.text_parser import decode_text, parse_text
from app.schemas import ParsedContract


MAX_TEXT_LENGTH = 120_000


def parse_upload(filename: str | None, content: bytes, settings: Settings) -> ParsedContract:
    if not content:
        raise UnsupportedDocumentError("上传文件为空。")
    if len(content) > settings.max_upload_bytes:
        raise UnsupportedDocumentError("文件超过10MB限制。")

    display_name = safe_display_filename(filename, "contract.txt")
    suffix = Path(display_name).suffix.lower()
    if suffix == ".docx":
        parsed = parse_docx(content, filename=display_name)
    elif suffix == ".pdf":
        parsed = parse_pdf(content, filename=display_name)
    elif suffix == ".txt":
        parsed = parse_text(decode_text(content), filename=display_name)
    elif suffix == ".doc":
        raise UnsupportedDocumentError("阶段三暂不支持旧版DOC，请另存为DOCX后上传。")
    else:
        raise UnsupportedDocumentError("仅支持DOCX、文本型PDF和TXT文件。")

    if parsed.text_length > MAX_TEXT_LENGTH:
        raise UnsupportedDocumentError("解析文本超过12万字符，MVP暂不支持。")
    return parsed


def parse_pasted_text(text: str) -> ParsedContract:
    parsed = parse_text(text, filename="粘贴的合同文本.txt", pasted=True)
    if parsed.text_length > MAX_TEXT_LENGTH:
        raise UnsupportedDocumentError("粘贴文本超过12万字符，MVP暂不支持。")
    return parsed

