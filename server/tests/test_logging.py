"""Tests for the 24h rolling log: rotation policy, JSON shape, redaction."""

from __future__ import annotations

import json
import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

from app.config import Settings
from app.logging_config import JsonFormatter, RedactionFilter, configure_logging


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        secret_key="x" * 16,
        invite_enc_key="y" * 32,
        log_dir=str(tmp_path),
        log_retention_hours=24,
        log_json=True,
    )  # type: ignore[call-arg]


def test_rolling_handler_keeps_24_hours(tmp_path: Path) -> None:
    configure_logging(_settings(tmp_path))
    handlers = [h for h in logging.getLogger().handlers if isinstance(h, TimedRotatingFileHandler)]
    assert handlers, "expected a TimedRotatingFileHandler"
    h = handlers[0]
    assert h.when == "H"  # hourly rotation
    assert h.backupCount == 24  # last 24 hours retained


def test_json_formatter_emits_single_line_json() -> None:
    record = logging.makeLogRecord(
        {"name": "giphery.app", "levelno": logging.INFO, "levelname": "INFO", "msg": "hi"}
    )
    record.user_id = "abc"
    out = JsonFormatter().format(record)
    parsed = json.loads(out)
    assert parsed["msg"] == "hi"
    assert parsed["user_id"] == "abc"
    assert parsed["logger"] == "giphery.app"


def test_redaction_filter_masks_secrets() -> None:
    record = logging.makeLogRecord({"name": "giphery.audit", "msg": "login"})
    record.password = "hunter2"
    record.access_token = "secret.jwt.value"
    record.username = "alice"
    RedactionFilter().filter(record)
    assert record.password == "***redacted***"
    assert record.access_token == "***redacted***"
    assert record.username == "alice"  # non-secret field preserved


def test_redaction_filter_masks_nested_dict() -> None:
    record = logging.makeLogRecord({"name": "giphery.app", "msg": "x"})
    record.payload = {"token": "abc", "user": {"name": "bob", "secret": "s"}}
    RedactionFilter().filter(record)
    assert record.payload["token"] == "***redacted***"
    assert record.payload["user"]["secret"] == "***redacted***"
    assert record.payload["user"]["name"] == "bob"
