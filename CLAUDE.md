# CLAUDE.md — Giphery operating guide

## Project summary

Giphery is a self-hosted, single-tenant GIF library. An **admin** runs the
server (Docker, behind a SWAG reverse proxy that terminates TLS). The admin
invites users with single-use codes; each user pairs an **Android management
app** to upload, tag, search, and manage their own GIFs. A separate, future
**keyboard/IME app performs the actual GIF insertion and is OUT OF SCOPE here**
— but the GIF raw-serve and search endpoints are designed so that IME client
can consume them without server changes.

**Scope of this repo: the server (FastAPI + PostgreSQL, dockerized) and the
Android management app only.** Do not build the IME/keyboard app here.

## Tech stack (pinned major versions)

### Server
- Python **3.13**
- FastAPI **0.137.x** on Uvicorn (`uvicorn[standard]`); Gunicorn optional as process manager
- Pydantic **v2** (2.13.x) + `pydantic-settings`
- SQLAlchemy **2.0.x** (async) + **asyncpg**
- Alembic (migrations)
- PostgreSQL **18**
- Auth: **PyJWT**, password hashing **Argon2id** via `argon2-cffi`
- Rate limiting: **slowapi** (Redis-backed or in-process)
- Image validation: **Pillow** (magic-byte sniffing)
- Invite-code encryption at rest: **cryptography** (Fernet)

### Web UI (admin console, served by the container)
- FastAPI + **Jinja2** templates + **HTMX** + minimal vanilla JS.
  Chosen over a React SPA for minimal attack surface — see ARCHITECTURE.md
  Decision log.

### Android management app
- Kotlin **2.4.0**, Jetpack **Compose** (BOM 2026.05.00), **Material 3** 1.4.x
- AGP **8.5.2+**, `compileSdk`/`targetSdk` **36**, `minSdk` **26**
- Retrofit + OkHttp + kotlinx.serialization; **Coil** for animated GIFs
- Coroutines + Flow; **Hilt** DI; **DataStore** + Keystore-encrypted token storage
- MVVM + repository pattern, single-activity, Compose Navigation

### Tooling / quality
- Backend: **ruff** (lint+format), **mypy** (strict), **pytest** + `pytest-asyncio`, `httpx`, coverage, `pip-audit`
- Android: **ktlint/detekt**, JUnit + **Turbine**, Compose UI tests
- **pre-commit** hooks, **GitHub Actions** CI (lint, type-check, tests, dep vuln scan)

## Monorepo layout

```
giphery/
├─ CLAUDE.md / ARCHITECTURE.md / SECURITY.md / README.md
├─ docker-compose.yml          # api + postgres (+ optional redis)
├─ .env.example                # documented config; no real secrets
├─ .github/workflows/ci.yml    # lint, type-check, test, dep scan
├─ server/
│  ├─ Dockerfile               # multi-stage, non-root, slim
│  ├─ pyproject.toml           # pinned deps; ruff/mypy/pytest config
│  ├─ alembic/                 # migrations
│  ├─ app/
│  │  ├─ main.py               # app, middleware, routers
│  │  ├─ config.py             # pydantic-settings
│  │  ├─ db.py                 # async engine/session
│  │  ├─ models/               # SQLAlchemy models
│  │  ├─ schemas/              # Pydantic v2 schemas
│  │  ├─ auth/                 # hashing, JWT, deps, RBAC
│  │  ├─ routers/              # auth, users, invites, gifs, tags, health
│  │  ├─ services/             # business logic
│  │  ├─ storage/              # filesystem GIF storage
│  │  └─ webui/                # Jinja2 templates + static
│  └─ tests/
└─ android/
   ├─ settings.gradle.kts
   ├─ build.gradle.kts
   ├─ gradle/libs.versions.toml
   └─ app/src/main/java/.../giphery/{data,domain,ui,di}/
```

## Commands

> Backend commands run from `server/`. Android from `android/`.

| Task | Command |
|------|---------|
| Run full stack | `docker compose up --build` |
| Apply migrations | `docker compose exec api alembic upgrade head` |
| New migration | `docker compose exec api alembic revision --autogenerate -m "msg"` |
| Backend deps (local) | `cd server && pip install -e ".[dev]"` |
| Run backend locally | `cd server && uvicorn app.main:app --reload` |
| Run web UI | served by the API at `/` (no separate process) |
| Backend tests | `cd server && pytest` |
| Backend lint+format | `cd server && ruff check . && ruff format .` |
| Backend type-check | `cd server && mypy app` |
| Dependency vuln scan | `cd server && pip-audit` |
| Build Android (debug) | `cd android && ./gradlew assembleDebug` |
| Android tests | `cd android && ./gradlew testDebugUnitTest` |
| Android lint | `cd android && ./gradlew ktlintCheck detekt` |

## Coding conventions
- **Formatters/linters:** ruff (line length 100) for Python; ktlint/detekt for Kotlin. CI fails on lint errors.
- **Types:** mypy strict on `app/`. No untyped public functions.
- **Naming:** snake_case (Python), camelCase/PascalCase (Kotlin), kebab-case routes, plural resource nouns (`/gifs`, `/invites`).
- **Commits:** Conventional Commits (`feat:`, `fix:`, `docs:`, `chore:`, `test:`, `refactor:`). One logical change per commit.
- **API:** versioned `/api/v1`; consistent error envelope `{ "error": { "code", "message", "details" } }`.

## Do / Don't (security rules)
**Do**
- Validate all input with Pydantic; use explicit field allow-lists (no mass assignment).
- Enforce ownership + RBAC server-side on every mutation.
- Use parameterized queries via SQLAlchemy; never build SQL by string concat.
- Sniff uploaded files with Pillow; never trust client extension/MIME.
- Read all secrets from env; keep `.env.example` complete and current.
- Run as non-root in the container; least-privilege DB role.

**Don't**
- Don't log secrets, tokens, password hashes, or raw passwords.
- Don't disable TLS verification or enable cleartext traffic (Android).
- Don't return password hashes or raw tokens in any response.
- Don't enable `/docs` in production (`ENABLE_DOCS=false`).
- Don't add a dependency without confirming it's maintained and pinning it.
- Don't hand-roll crypto, token signing, or password hashing — use the pinned libs.

## Logging
- A **24-hour rolling application log** records every request and significant
  app event to aid troubleshooting. Implemented with Python's
  `TimedRotatingFileHandler` (hourly rotation, `backupCount` = `LOG_RETENTION_HOURS`,
  default 24) writing to `LOG_DIR` (a Docker volume so it survives restarts).
- Two streams share the same rotation: a **request/app log** (method, path,
  status, latency, request id, actor) and the **security audit log** (login,
  invite create/redeem/revoke, gif delete). Both are structured JSON when
  `LOG_JSON=true`.
- **Never** log secrets, tokens, password hashes, or raw passwords — values are
  redacted by a logging filter. See ARCHITECTURE.md → "Logging & observability"
  and SECURITY.md → Repudiation.

## Secrets / config
- All config via environment variables (see `.env.example`); `pydantic-settings` loads them.
- `.env` is git-ignored; only `.env.example` is committed.
- Generate `SECRET_KEY` with `openssl rand -hex 32`; `INVITE_ENC_KEY` per the comment in `.env.example`.
- To rotate a compromised secret, see SECURITY.md → "Rotating secrets/tokens".
