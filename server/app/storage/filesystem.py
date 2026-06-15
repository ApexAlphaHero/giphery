"""Content-addressed filesystem storage for GIFs.

Files are sharded by content hash under ``MEDIA_ROOT`` and never served
statically — only via the authenticated raw endpoint. The DB stores the path
*relative* to ``MEDIA_ROOT`` (never an absolute or client-supplied path).
"""

from __future__ import annotations

import re
from pathlib import Path

from app.config import get_settings

settings = get_settings()

_SAFE_FILENAME = re.compile(r"[^A-Za-z0-9._-]+")


def _media_root() -> Path:
    root = Path(settings.media_root)
    root.mkdir(parents=True, exist_ok=True)
    return root


def sanitize_filename(name: str) -> str:
    """Strip directories and unsafe characters; bound length."""
    base = Path(name).name  # drop any path components
    cleaned = _SAFE_FILENAME.sub("_", base).strip("._") or "file.gif"
    return cleaned[:255]


def stored_path_for_hash(content_hash: str) -> str:
    """Relative sharded path, e.g. ab/cd/abcd...gif."""
    return f"{content_hash[0:2]}/{content_hash[2:4]}/{content_hash}.gif"


def store_bytes(content_hash: str, data: bytes) -> str:
    """Write bytes to the content-addressed path; return the relative path."""
    rel = stored_path_for_hash(content_hash)
    target = _media_root() / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():  # content-addressed → identical bytes already stored
        # Write atomically: temp then replace.
        tmp = target.with_suffix(".tmp")
        tmp.write_bytes(data)
        tmp.replace(target)
    return rel


def read_file(relative_path: str) -> bytes:
    # Guard against traversal: resolve and ensure it stays under MEDIA_ROOT.
    root = _media_root().resolve()
    full = (root / relative_path).resolve()
    if not str(full).startswith(str(root)):
        raise FileNotFoundError(relative_path)
    return full.read_bytes()


def delete_file(relative_path: str) -> None:
    root = _media_root().resolve()
    full = (root / relative_path).resolve()
    if str(full).startswith(str(root)) and full.exists():
        full.unlink()
