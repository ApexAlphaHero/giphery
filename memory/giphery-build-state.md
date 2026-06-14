---
name: giphery-build-state
description: Giphery monorepo build progress, phase status, and how to run/test the server
metadata:
  type: project
---

Giphery = self-hosted GIF library: dockerized FastAPI+PostgreSQL server (behind SWAG) + Android management app. IME/keyboard app is OUT of scope. Built in 8 phases per the master prompt in the first user message.

**Phase status (as of 2026-06-14):**
- Phase 1 (docs & scaffolding) — DONE, committed. CLAUDE.md, ARCHITECTURE.md (data model, REST contract, flows, decision log), SECURITY.md (STRIDE + checklist), .env.example, docker-compose.yml, CI, pre-commit, pinned manifests.
- Phase 2 (backend core) — DONE, committed. config, async DB, UUIDv7 ids, ORM models, Alembic initial migration (citext/pg_trgm), health endpoint, FastAPI app (error envelope, CORS, docs gating), non-root Dockerfile. Tests green.
- Phases 3–8 PENDING: auth+setup, invitations, gifs+tags, web UI, Android app, security pass.

**User-added requirement:** a 24-hour rolling app log for troubleshooting — IMPLEMENTED in [server/app/logging_config.py] (TimedRotatingFileHandler, hourly rotation, 24 backups, JSON lines, secret-redaction filter; access/app/audit streams) + request-id middleware. Verified writing + redaction.

**Local dev note:** machine has only Python 3.14 (project targets 3.13 via Docker). For local verification a venv at `server/.venv` was created with UNPINNED deps just to run tests/ruff/mypy. Real builds use Docker `python:3.13-slim` with the pinned versions in [server/pyproject.toml]. Run tests: `server/.venv/Scripts/python.exe -m pytest`. See [[giphery-quality-gates]] if created.
