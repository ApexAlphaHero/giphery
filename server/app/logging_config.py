"""24-hour rolling application logging.

Three logical streams share one hourly-rotating file set (last
``LOG_RETENTION_HOURS`` hours kept, older auto-deleted) plus a stdout echo:

* ``giphery.access`` — one structured line per HTTP request.
* ``giphery.app``    — application/debug events and exceptions.
* ``giphery.audit``  — security events (login, invite, gif delete, ...).

A redaction filter guarantees secrets/tokens/passwords are never written.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Any

from app.config import Settings

# Keys whose values must never be logged, matched case-insensitively as a
# substring of the field name.
_SECRET_KEY_PATTERN = re.compile(
    r"(password|passwd|secret|token|authorization|api[_-]?key|"
    r"refresh|access[_-]?token|code|enc[_-]?key|hash)",
    re.IGNORECASE,
)
_REDACTED = "***redacted***"

# Standard LogRecord attributes we don't want to duplicate into the JSON "extra".
_RESERVED = set(logging.makeLogRecord({}).__dict__.keys()) | {
    "message",
    "asctime",
    "taskName",
}


def _redact(value: Any) -> Any:
    """Recursively redact secret-looking keys in dict/list structures."""
    if isinstance(value, dict):
        return {
            k: (_REDACTED if _SECRET_KEY_PATTERN.search(str(k)) else _redact(v))
            for k, v in value.items()
        }
    if isinstance(value, list | tuple):
        return [_redact(v) for v in value]
    return value


class RedactionFilter(logging.Filter):
    """Strip secret-looking keys from structured ``extra`` fields in-place."""

    def filter(self, record: logging.LogRecord) -> bool:
        for key in list(record.__dict__.keys()):
            if key in _RESERVED:
                continue
            if _SECRET_KEY_PATTERN.search(key):
                record.__dict__[key] = _REDACTED
            else:
                record.__dict__[key] = _redact(record.__dict__[key])
        return True


class JsonFormatter(logging.Formatter):
    """Render records as single-line JSON for machine-readable troubleshooting."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for key, val in record.__dict__.items():
            if key in _RESERVED or key in payload:
                continue
            payload[key] = val
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, ensure_ascii=False)


def _build_handlers(settings: Settings) -> list[logging.Handler]:
    handlers: list[logging.Handler] = []
    redaction = RedactionFilter()
    formatter: logging.Formatter = (
        JsonFormatter()
        if settings.log_json
        else logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s",
        )
    )

    # Rolling file: rotate hourly, keep the last LOG_RETENTION_HOURS files.
    try:
        Path(settings.log_dir).mkdir(parents=True, exist_ok=True)
        file_handler: logging.Handler = TimedRotatingFileHandler(
            filename=str(Path(settings.log_dir) / "giphery.log"),
            when="H",
            interval=1,
            backupCount=max(1, settings.log_retention_hours),
            encoding="utf-8",
            utc=True,
            delay=True,
        )
        file_handler.setFormatter(formatter)
        file_handler.addFilter(redaction)
        handlers.append(file_handler)
    except OSError:
        # If the log volume is unavailable, fall back to stdout only.
        pass

    # Stdout echo for `docker logs`.
    stream = logging.StreamHandler()
    stream.setFormatter(formatter)
    stream.addFilter(redaction)
    handlers.append(stream)
    return handlers


def configure_logging(settings: Settings) -> None:
    """Install the rolling handlers on the root + giphery loggers (idempotent)."""
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    handlers = _build_handlers(settings)

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level)
    for h in handlers:
        root.addHandler(h)

    # Access + audit always emit at INFO regardless of the global level.
    for name in ("giphery.access", "giphery.audit"):
        lg = logging.getLogger(name)
        lg.setLevel(logging.INFO)

    # Quiet noisy libraries one notch.
    for noisy in ("uvicorn.access",):
        logging.getLogger(noisy).setLevel(logging.WARNING)


# Convenience module-level loggers.
access_logger = logging.getLogger("giphery.access")
app_logger = logging.getLogger("giphery.app")
audit_logger = logging.getLogger("giphery.audit")


def audit(action: str, **fields: Any) -> None:
    """Emit a security audit event (secrets auto-redacted by the filter)."""
    audit_logger.info(action, extra={"event": action, **fields})
