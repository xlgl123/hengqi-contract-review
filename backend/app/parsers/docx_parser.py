from __future__ import annotations

import io
import zipfile

from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P

from app.errors import UnsupportedDocumentError
from app.parsers.common import digest, normalize_text
from app.schemas import DocumentBlock, ParsedContract


MAX_ARCHIVE_FILES = 2_000
MAX_UNCOMPRESSED_BYTES = 60 * 1024 * 1024


def validate_docx(content: bytes) -> None:
    if not content.startswith(b"PK"):
        raise UnsupportedDocumentError("文件扩展名是DOCX，但内容不是有效的Word文件。")
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            infos = archive.infolist()
            if len(infos) > MAX_ARCHIVE_FILES:
                raise UnsupportedDocumentError("DOCX内部文件数量异常。")
            if sum(info.file_size for info in infos) > MAX_UNCOMPRESSED_BYTES:
                raise UnsupportedDocumentError("DOCX解压后体积过大。")
            if "word/document.xml" not in archive.namelist():
                raise UnsupportedDocumentError("DOCX缺少word/document.xml。")
    except zipfile.BadZipFile as exc:
        raise UnsupportedDocumentError("DOCX压缩结构损坏。") from exc


def iter_blocks(document: Document):
    for child in document.element.body.iterchildren():
        if isinstance(child, CT_P):
            yield Paragraph(child, document)
        elif isinstance(child, CT_Tbl):
            yield Table(child, document)


def parse_docx(content: bytes, *, filename: str) -> ParsedContract:
    validate_docx(content)
    try:
        document = Document(io.BytesIO(content))
    except Exception as exc:
        raise UnsupportedDocumentError("Word文件无法解析，可能已经损坏。") from exc

    blocks: list[DocumentBlock] = []
    paragraph_index = 0
    table_index = 0
    source_order = 0

    for item in iter_blocks(document):
        if isinstance(item, Paragraph):
            text = normalize_text(item.text)
            if not text:
                continue
            paragraph_index += 1
            source_order += 1
            blocks.append(
                DocumentBlock(
                    block_id=f"docx-p{paragraph_index}",
                    kind="paragraph",
                    text=text,
                    paragraph_index=paragraph_index,
                    source_order=source_order,
                )
            )
        else:
            table_index += 1
            for row_index, row in enumerate(item.rows, start=1):
                cells = [normalize_text(cell.text) for cell in row.cells]
                text = " | ".join(cell for cell in cells if cell)
                if not text:
                    continue
                source_order += 1
                blocks.append(
                    DocumentBlock(
                        block_id=f"docx-t{table_index}-r{row_index}",
                        kind="table_row",
                        text=text,
                        table_index=table_index,
                        source_order=source_order,
                    )
                )

    text_length = sum(len(block.text) for block in blocks)
    if text_length < 30:
        raise UnsupportedDocumentError("Word文件中没有足够的可审查文本。")

    return ParsedContract(
        filename=filename,
        file_type="docx",
        sha256=digest(content),
        text_length=text_length,
        blocks=blocks,
    )

