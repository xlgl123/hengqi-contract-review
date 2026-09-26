from __future__ import annotations

import ctypes
import json
import os
import sys
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path


class SecureSettingsError(RuntimeError):
    pass


@dataclass(frozen=True)
class StoredAISettings:
    provider: str
    base_url: str
    model: str
    api_key: str


class _DataBlob(ctypes.Structure):
    _fields_ = [
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_byte)),
    ]


def _input_blob(data: bytes) -> tuple[_DataBlob, ctypes.Array[ctypes.c_char]]:
    buffer = ctypes.create_string_buffer(data)
    blob = _DataBlob(
        len(data),
        ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte)),
    )
    return blob, buffer


def _protect_windows(data: bytes) -> bytes:
    if sys.platform != "win32":
        raise SecureSettingsError("安全记住功能当前仅支持Windows本地版。")
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    source, source_buffer = _input_blob(data)
    output = _DataBlob()
    crypt32.CryptProtectData.argtypes = [
        ctypes.POINTER(_DataBlob),
        wintypes.LPCWSTR,
        ctypes.POINTER(_DataBlob),
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(_DataBlob),
    ]
    crypt32.CryptProtectData.restype = wintypes.BOOL
    if not crypt32.CryptProtectData(
        ctypes.byref(source),
        "衡契AI连接",
        None,
        None,
        None,
        0x1,
        ctypes.byref(output),
    ):
        raise SecureSettingsError(f"Windows加密失败：{ctypes.WinError()}")
    try:
        return ctypes.string_at(output.pbData, output.cbData)
    finally:
        kernel32.LocalFree(output.pbData)
        del source_buffer


def _unprotect_windows(data: bytes) -> bytes:
    if sys.platform != "win32":
        raise SecureSettingsError("安全记住功能当前仅支持Windows本地版。")
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    source, source_buffer = _input_blob(data)
    output = _DataBlob()
    description = wintypes.LPWSTR()
    crypt32.CryptUnprotectData.argtypes = [
        ctypes.POINTER(_DataBlob),
        ctypes.POINTER(wintypes.LPWSTR),
        ctypes.POINTER(_DataBlob),
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(_DataBlob),
    ]
    crypt32.CryptUnprotectData.restype = wintypes.BOOL
    if not crypt32.CryptUnprotectData(
        ctypes.byref(source),
        ctypes.byref(description),
        None,
        None,
        None,
        0x1,
        ctypes.byref(output),
    ):
        raise SecureSettingsError(f"Windows解密失败：{ctypes.WinError()}")
    try:
        return ctypes.string_at(output.pbData, output.cbData)
    finally:
        if description:
            kernel32.LocalFree(description)
        kernel32.LocalFree(output.pbData)
        del source_buffer


class AICredentialStore:
    def __init__(self, path: Path):
        self.path = path

    def save(self, settings: StoredAISettings) -> None:
        payload = json.dumps(
            {
                "version": 1,
                "provider": settings.provider,
                "base_url": settings.base_url,
                "model": settings.model,
                "api_key": settings.api_key,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        encrypted = _protect_windows(payload)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_bytes(encrypted)
        os.replace(temporary, self.path)

    def load(self) -> StoredAISettings | None:
        if not self.path.is_file():
            return None
        try:
            payload = json.loads(_unprotect_windows(self.path.read_bytes()).decode("utf-8"))
            if payload.get("version") != 1:
                raise ValueError("unsupported version")
            values = {
                key: str(payload.get(key) or "").strip()
                for key in ("provider", "base_url", "model", "api_key")
            }
            if not all(values.values()):
                raise ValueError("missing field")
            return StoredAISettings(**values)
        except (OSError, UnicodeError, ValueError, json.JSONDecodeError, SecureSettingsError):
            self.clear()
            return None

    def clear(self) -> None:
        try:
            self.path.unlink(missing_ok=True)
        except OSError as exc:
            raise SecureSettingsError(f"删除本机加密密钥失败：{exc}") from exc
