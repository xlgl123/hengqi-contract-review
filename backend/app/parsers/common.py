from __future__ import annotations

import re
from hashlib import sha256


CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def normalize_text(text: str) -> str:
    text = CONTROL_CHARS.sub("", text.replace("\r\n", "\n").replace("\r", "\n"))
    text = re.sub(r"[ \t\u3000]+", " ", text)
    return text.strip()


def digest(content: bytes) -> str:
    return sha256(content).hexdigest()


def safe_display_filename(filename: str | None, default: str) -> str:
    candidate = (filename or default).replace("\\", "/").split("/")[-1].strip()
    candidate = CONTROL_CHARS.sub("", candidate)
    return candidate[:160] or default

