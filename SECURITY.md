# SECURITY.md — Giphery

## STRIDE threat model

Trust boundaries: **(B1)** Internet → SWAG (TLS edge); **(B2)** SWAG → API (internal network); **(B3)** API → PostgreSQL/Redis/filesystem; **(B4)** Android app ↔ API; **(B5)** browser (admin) ↔ web UI.

### Spoofing — *impersonating a user/admin/device*
- **Threats:** credential stuffing, brute force, user enumeration, stolen/forged tokens, fake devices, invite-code guessing.
- **Mitigations (implemented):**
  - Argon2id password hashing (`argon2-cffi`) with tuned params; password-strength policy on `/setup` and redeem.
  - JWTs signed (HS256 default) with full claim validation (`exp, iat, nbf, aud, iss, typ`).
  - Generic auth errors on `/auth/login` and `/invites/redeem` — no user enumeration; constant-ish response regardless of whether the username exists.
  - Rate limiting + backoff (slowapi) on login and redeem (`RATE_LIMIT_LOGIN`, `RATE_LIMIT_REDEEM`).
  - High-entropy invite codes (≥128 bits) with HMAC lookup; single-use + expiry + revocation.
  - Per-device refresh `jti`; refresh-token **reuse detection** revokes the device.
  - TLS enforced at SWAG; HSTS. Android: HTTPS-only, no cleartext, optional cert pinning.

### Tampering — *modifying data in transit or at rest*
- **Threats:** request body/param tampering, IDOR/ownership bypass, SQL injection, mass assignment, file/path manipulation, token modification.
- **Mitigations:**
  - All input validated by Pydantic v2 schemas with **explicit field allow-lists** (no mass assignment; client-supplied `owner_id`/`role` ignored).
  - Ownership + RBAC checks server-side on every read/mutation (§RBAC in ARCHITECTURE.md).
  - SQLAlchemy parameterized queries only — no string-built SQL.
  - Signed tokens (any modification fails signature check).
  - Uploads: Pillow magic-byte validation, sha256 content hash, server-generated sharded `stored_path`; filenames sanitized; no client path trusted.
  - Immutable `created_at`; `updated_at` server-set.

### Repudiation — *denying an action occurred*
- **Threats:** a user/admin denies creating/redeeming/revoking an invite or deleting a GIF.
- **Mitigations:**
  - **24-hour rolling structured audit log** (`giphery.audit`) records actor, action, target, source IP (`X-Forwarded-For`), `request_id`, timestamp for: login success/failure, setup, invite create/redeem/revoke, gif upload/delete, device revoke. See ARCHITECTURE.md §8.
  - Correlation `request_id` on every request (`X-Request-ID`) links access + audit lines.
  - Logs **never** contain secrets/tokens/passwords (redaction filter).
  - Retention is intentionally bounded to 24h for troubleshooting; if long-term non-repudiation is needed, ship logs to an external append-only sink (documented as future work).

### Information disclosure — *leaking sensitive data*
- **Threats:** leaking password hashes/tokens, invite-code disclosure, verbose errors, directory traversal on media, OpenAPI exposure, CORS abuse, secrets in code/logs.
- **Mitigations:**
  - Response schemas never include `password_hash`, raw tokens, or `code_lookup_hash`.
  - Invite codes encrypted at rest (Fernet); decrypted only for the authenticated admin list view.
  - Consistent error envelope; no stack traces to clients in production.
  - Media served only via authenticated `/gifs/{id}/raw`; volume is not web-root; `stored_path` server-controlled (no traversal).
  - `/docs` & `/redoc` gated by `ENABLE_DOCS` (off in prod).
  - CORS locked to `CORS_ALLOWED_ORIGINS`; `*` rejected in production.
  - Safe `Content-Type: image/gif` and `Content-Disposition` on raw serve.
  - All secrets via env/secret store; `.env` git-ignored; log redaction filter; no secrets in source.

### Denial of service — *exhausting resources*
- **Threats:** huge/malformed uploads, request floods, unbounded queries, connection exhaustion, decompression bombs.
- **Mitigations:**
  - `MAX_UPLOAD_BYTES` enforced (app + SWAG `client_max_body_size`); reject oversized/malformed images early (Pillow), with image dimension/frame sanity limits.
  - Rate limiting on auth + redeem; pagination caps (`limit ≤ 100`, cursor-based).
  - SQLAlchemy connection-pool limits; request timeouts; SWAG in front.
  - Body-size limits at the ASGI layer.

### Elevation of privilege — *gaining higher rights*
- **Threats:** user→admin escalation, setup re-run, container breakout, DB over-privilege, role injection via payload.
- **Mitigations:**
  - RBAC enforced server-side; `role` never accepted from client (mass-assignment guard).
  - `/setup` hard-fails (409) once any user exists — first-run lock.
  - Container runs as **non-root** (dedicated UID), minimal slim image, no build tools in final stage.
  - Least-privilege PostgreSQL role (owns only the app schema; not superuser); DB not exposed to host.
  - Refresh-token rotation + per-device revocation limits blast radius of a stolen token.

### Android-specific
- `usesCleartextTraffic=false` + network security config (HTTPS-only).
- Refresh token stored encrypted via Android Keystore (EncryptedSharedPreferences / DataStore + Keystore key); access token in memory only.
- No token/secret logging.
- Certificate pinning **optional** (documented trade-off: pinning breaks with SWAG cert rotation / self-signed — provide config toggle).
- `android:allowBackup` set so the token store is excluded from backup/data-extraction rules; consider `FLAG_SECURE` on sensitive screens.

## Hardening checklist (status)

Legend: ✅ done · 🚧 in progress · ⬜ not started (tracked by build phase)

- ✅ Container runs as non-root, minimal slim image, healthcheck present. *(Phase 2 — server/Dockerfile)*
- ✅ Least-privilege DB role; DB not exposed to host. *(Phase 2 compose keeps DB internal; Phase 8 `server/deploy/init-db.sql` provisions a CRUD-only `giphery_app` role)*
- 🚧 All secrets via env; `.env` git-ignored; `.env.example` complete. *(Phase 1 — `.env.example` + gitignore done)*
- ✅ Argon2id password hashing (t=3, m=64MiB, p=2); password strength enforced. *(Phase 3 — app/auth/passwords.py)*
- ✅ JWT access+refresh with rotation, jti, full claim validation (exp/iat/nbf/iss/aud/typ); per-device revocation + reuse detection. *(Phase 3 — app/auth/tokens.py, services/auth_service.py)*
- ✅ Rate limiting + backoff on login and invite-redeem; no user enumeration (uniform login errors + timing; generic invite errors). *(Phase 3/4 — slowapi on /auth/login, /auth/refresh, /invites/redeem)*
- ✅ Strict input validation (Pydantic v2), explicit field allow-lists — `role`/`owner_id` never client-settable; GifUpdate/SetupRequest/InviteRedeem are closed schemas. *(Phases 3–6)*
- ✅ File uploads: type sniffed (Pillow magic bytes + decode-verify), size + pixel-capped, filename sanitized, sha256 content-hashed/deduped, sharded storage outside web root, safe `image/gif` + `nosniff` + inline disposition + traversal guard. *(Phase 5 — services/gif_validation.py, storage/filesystem.py, routers/gifs.py)*
- ✅ RBAC + ownership enforced server-side on every mutation; cross-owner access returns 404 (no existence disclosure). *(Phase 3+/5)*
- ✅ CORS locked to known origins (wildcard rejected in prod); OpenAPI docs gated by `ENABLE_DOCS`. *(Phase 2 — app/main.py)*
- ✅ Admin web console: httpOnly+SameSite cookies, double-submit CSRF on all POSTs, no inline JS/CDN, rate-limited login. *(Phase 6 — webui/security.py, routers/webui.py)*
- ✅ Security headers at SWAG (sample conf in README) + app-level defense-in-depth (CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, COOP, Permissions-Policy); HTTPS + HSTS at SWAG. *(Phase 8 — app/middleware.py, README)*
- ✅ Structured audit logging without secrets + 24h rolling app log (hourly rotation, 24 backups, redaction filter). *(Phase 2 — app/logging_config.py, app/middleware.py)*
- ✅ Android: HTTPS-only (no cleartext + network security config), refresh token in Keystore-backed EncryptedSharedPreferences (access token in-memory), OkHttp logging redacts Authorization, `allowBackup=false` + backup/data-extraction rules exclude the token store, transparent 401 refresh. *(Phase 7)*
- ✅ CI runs lint (ruff incl. flake8-bandit `S` rules), type-check (mypy strict), tests, dependency vulnerability scan (`pip-audit` — clean; `gradle`/`npm` jobs); static analysis run each phase. *(Phase 1 skeleton → Phase 8)*

## Responsible disclosure
Report vulnerabilities privately to the repository owner (see README contact). Do not open public issues for security bugs. Expected acknowledgement within a reasonable window; fixes prioritized by severity.

## Rotating secrets/tokens
- **`SECRET_KEY` (JWT signing):** generate a new key (`openssl rand -hex 32`), set in `.env`, restart API. All existing access/refresh tokens become invalid → clients re-pair/re-login. For zero-downtime, support a key-set (current + previous) during a grace window (future enhancement).
- **`INVITE_ENC_KEY`:** rotating invalidates the ability to decrypt existing `code_encrypted` values. Procedure: decrypt-all with the old key and re-encrypt with the new (one-off migration script) **before** swapping, or revoke outstanding invites and issue new ones.
- **Database password:** rotate in PostgreSQL and `.env` together; restart API.
- **Compromised device/refresh token:** admin revokes the device (`revoked_at`); the user re-pairs. Logout revokes the current device.
- **Compromised admin password:** change via the account flow; consider rotating `SECRET_KEY` to invalidate all sessions.
