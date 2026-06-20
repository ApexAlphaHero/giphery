---
name: giphery-build-state
description: Giphery monorepo build progress, phase status, and how to run/test the server
metadata:
  type: project
---

Giphery = self-hosted GIF library: dockerized FastAPI+PostgreSQL server (behind SWAG) + Android management app. IME/keyboard app is OUT of scope. Built in 8 phases per the master prompt in the first user message.

**Phase status: ALL 8 PHASES COMPLETE (as of 2026-06-15), each committed.**
- P1 docs/scaffolding, P2 backend core, P3 auth+setup (Argon2id, JWT rotation+reuse-detection, rate limit), P4 invitations (Fernet-encrypted codes + HMAC lookup, token-based redeem), P5 gifs+tags (Pillow validation, content-addressed storage, dedupe, raw-serve, search), P6 admin web console (Jinja2, cookie+CSRF, no JS), P7 Android app (30 Kotlin files, Compose M3, encrypted tokens, transparent refresh), P8 security pass (headers, least-priv DB SQL, pip-audit clean).
- Backend: **38 tests pass, ruff + mypy strict clean.** The Android app has since been split out into its own repository; this repo is server-only.
- All SECURITY.md hardening checklist items ✅. Git: 9 commits on default branch, no remote.

**User-added requirement:** a 24-hour rolling app log for troubleshooting — IMPLEMENTED in [server/app/logging_config.py] (TimedRotatingFileHandler, hourly rotation, 24 backups, JSON lines, secret-redaction filter; access/app/audit streams) + request-id middleware. Verified writing + redaction.

**Local dev note:** machine has only Python 3.14 (project targets 3.13 via Docker). For local verification a venv at `server/.venv` was created with UNPINNED deps just to run tests/ruff/mypy. Real builds use Docker `python:3.13-slim` with the pinned versions in [server/pyproject.toml]. Run tests: `server/.venv/Scripts/python.exe -m pytest`. See [[giphery-quality-gates]] if created.
