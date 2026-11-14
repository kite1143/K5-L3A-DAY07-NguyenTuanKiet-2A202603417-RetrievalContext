"""Nạp .env cho CLI (không ghi đè biến môi trường đã có).

Không in giá trị bí mật; chỉ trả về tên biến đã nạp.
"""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENV = ROOT / ".env"


def load_env(path: Path | None = None, environ: dict | None = None) -> list[str]:
    environ = environ if environ is not None else os.environ
    path = Path(path) if path is not None else DEFAULT_ENV
    if not path.exists():
        return []
    loaded: list[str] = []
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if not key or key in environ:
            continue
        environ[key] = value
        loaded.append(key)
    return loaded
