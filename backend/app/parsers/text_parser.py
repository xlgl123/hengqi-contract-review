from __future__ import annotations

from app.parsers.common import digest, normalize_text
from app.schemas import DocumentBlock, ParsedContract


def parse_text(content: str, *, filename: str, pasted: bool = False) -> ParsedContract:
    normalized = normalize_text(content)
    if len(normalized) < 30:
        raise ValueError("合同文本过短，至少需要30个字符。")

    paragraphs = [normalize_text(part) for part in normalized.split("\n")]
    paragraphs = [part for part in paragraphs if part]
    blocks = [
        DocumentBlock(
            block_id=f"text-p{index}",
            text=paragraph,
            paragraph_index=index,
            source_order=index,
        )
        for index, paragraph in enumerate(paragraphs, start=1)
    ]
    raw = content.encode("utf-8")
    return ParsedContract(
        filename=filename,
        file_type="pasted_text" if pasted else "txt",
        sha256=digest(raw),
        text_length=sum(len(block.text) for block in blocks),
        blocks=blocks,
    )


def decode_text(content: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("文本文件编码无法识别，请使用UTF-8或GB18030。")

