from __future__ import annotations

import io

import pdfplumber

from app.errors import UnsupportedDocumentError
from app.parsers.common import digest, normalize_text
from app.schemas import DocumentBlock, ParsedContract


MAX_PAGES = 80


def parse_pdf(content: bytes, *, filename: str) -> ParsedContract:
    if not content.startswith(b"%PDF"):
        raise UnsupportedDocumentError("文件扩展名是PDF，但内容不是有效PDF。")

    try:
        pdf = pdfplumber.open(io.BytesIO(content))
    except Exception as exc:
        raise UnsupportedDocumentError("PDF无法打开，可能已损坏或加密。") from exc

    blocks: list[DocumentBlock] = []
    nonempty_pages = 0
    try:
        if len(pdf.pages) > MAX_PAGES:
            raise UnsupportedDocumentError(f"PDF超过{MAX_PAGES}页，MVP暂不支持。")
        for page_number, page in enumerate(pdf.pages, start=1):
            try:
                raw_text = page.extract_text(x_tolerance=2, y_tolerance=3) or ""
            except Exception as exc:
                raise UnsupportedDocumentError(f"PDF第{page_number}页文本解析失败。") from exc
            lines = [normalize_text(line) for line in raw_text.splitlines()]
            lines = [line for line in lines if line]
            if lines:
                nonempty_pages += 1
            for line_index, line in enumerate(lines, start=1):
                blocks.append(
                    DocumentBlock(
                        block_id=f"pdf-p{page_number}-b{line_index}",
                        text=line,
                        page=page_number,
                        paragraph_index=line_index,
                        source_order=len(blocks) + 1,
                    )
                )
    finally:
        pdf.close()

    text_length = sum(len(block.text) for block in blocks)
    page_count = max((block.page or 0 for block in blocks), default=0)
    if text_length < 30 or nonempty_pages == 0:
        raise UnsupportedDocumentError(
            "PDF没有足够的可复制文本，可能是扫描件。阶段三请改用DOCX、文本型PDF或粘贴文本。"
        )

    return ParsedContract(
        filename=filename,
        file_type="pdf",
        sha256=digest(content),
        text_length=text_length,
        page_count=page_count,
        blocks=blocks,
    )

