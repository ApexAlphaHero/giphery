"""Validate uploaded bytes are a real GIF (magic bytes via Pillow), not a guess."""

from __future__ import annotations

import hashlib
import io

from PIL import Image, UnidentifiedImageError

from app.config import get_settings
from app.schemas.errors import ApiError

settings = get_settings()

# Cap decoded pixel area to reject decompression bombs (Pillow also warns).
MAX_PIXELS = 30_000_000
GIF_MIME = "image/gif"


def validate_gif(data: bytes) -> tuple[int, int, str]:
    """Return (width, height, sha256-hex) or raise ApiError on invalid input."""
    if not data:
        raise ApiError(422, "empty_file", "Uploaded file is empty")
    if len(data) > settings.max_upload_bytes:
        raise ApiError(
            413,
            "file_too_large",
            f"File exceeds the {settings.max_upload_bytes}-byte limit",
        )

    try:
        with Image.open(io.BytesIO(data)) as img:
            fmt = img.format
            width, height = img.size
            if fmt != "GIF":
                raise ApiError(415, "not_a_gif", "File is not a valid GIF")
            if width * height > MAX_PIXELS:
                raise ApiError(413, "image_too_large", "Image dimensions are too large")
            # Decode-verify integrity (header-only checks aren't enough).
            img.verify()
    except UnidentifiedImageError as exc:
        raise ApiError(415, "not_a_gif", "File is not a valid GIF") from exc
    except ApiError:
        raise
    except Exception as exc:
        raise ApiError(415, "not_a_gif", "File is not a valid GIF") from exc

    content_hash = hashlib.sha256(data).hexdigest()
    return width, height, content_hash
