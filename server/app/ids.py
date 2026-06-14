"""Time-ordered UUIDv7 generation (RFC 9562), portable across PG and SQLite.

PostgreSQL 18 has a native ``uuidv7()``; generating in Python lets the same
models work against the SQLite test database without a DB extension.
"""

from __future__ import annotations

import os
import time
import uuid


def uuid7() -> uuid.UUID:
    """Return a UUIDv7: 48-bit Unix-ms timestamp + 74 random bits."""
    unix_ms = int(time.time() * 1000)
    rand = os.urandom(10)  # 80 random bits; we use 74 after version/variant.

    ts = unix_ms.to_bytes(6, "big")
    b = bytearray(16)
    b[0:6] = ts
    b[6:16] = rand

    # version 7 in the high nibble of byte 6
    b[6] = (b[6] & 0x0F) | 0x70
    # RFC 4122 variant (10xx) in the top bits of byte 8
    b[8] = (b[8] & 0x3F) | 0x80
    return uuid.UUID(bytes=bytes(b))
