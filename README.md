# Giphery

Self-hosted GIF library: a dockerized **FastAPI + PostgreSQL** server (behind a
SWAG reverse proxy) and an **Android management app** to upload, tag, search,
and manage GIFs. A future keyboard/IME app (separate project) will reuse the
GIF search + raw-serve endpoints to insert GIFs.

> **Scope:** this repo contains the **server** and the **Android management
> app** only. The IME/keyboard app is out of scope.

- **CLAUDE.md** — operating guide & commands.
- **ARCHITECTURE.md** — data model, full REST API contract, flows, logging, decisions.
- **SECURITY.md** — STRIDE threat model, hardening checklist, secret rotation.

## Quick start

```bash
# 1. Configure
cp .env.example .env
# generate strong secrets:
openssl rand -hex 32                                   # -> SECRET_KEY
python -c "import secrets,base64; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"  # -> INVITE_ENC_KEY
# edit .env: set the secrets above, POSTGRES_PASSWORD, PUBLIC_BASE_URL, CORS_ALLOWED_ORIGINS

# 2. Bring up the stack
docker compose up --build -d

# 3. Apply migrations
docker compose exec api alembic upgrade head

# 4. First-run admin + invites
#  - open the web UI (via SWAG, e.g. https://giphery.example.com) → create the admin
#  - log in → create an invitation (optionally label who it's for) → copy the code
#  - on the phone: open the Giphery app → enter server URL + code + a username → paired
```

Status: **Phase 1 (docs & scaffolding) complete.** Backend, web UI, and Android
app are built in subsequent phases — see CLAUDE.md / the build phases.

## Running behind SWAG

The API listens only on the internal `giphery_net` docker network. Put SWAG on
the same network and proxy to `api:8000`. Sample site-conf snippet
(`swag/nginx/site-confs/giphery.conf`):

```nginx
server {
    listen 443 ssl;
    server_name giphery.example.com;

    include /config/nginx/ssl.conf;          # TLS + HSTS

    # security headers
    add_header Strict-Transport-Security "max-age=63072000; includeSubDomains" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "DENY" always;
    add_header Referrer-Policy "no-referrer" always;
    add_header Content-Security-Policy "default-src 'self'; img-src 'self' data:; script-src 'self' 'unsafe-inline'" always;

    client_max_body_size 20m;                # > MAX_UPLOAD_BYTES for GIF uploads

    location / {
        resolver 127.0.0.11 valid=30s;       # docker DNS
        set $upstream_app api;                # container name on giphery_net
        set $upstream_port 8000;
        proxy_pass http://$upstream_app:$upstream_port;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;   # rate limiting needs real IP
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_http_version 1.1;
        proxy_read_timeout 60s;
    }
}
```

Pre-create the shared network if SWAG runs in a different compose project:

```bash
docker network create giphery_net
# then set `external: true` under networks.giphery_net in docker-compose.yml
```

## Troubleshooting logs

The API writes a **24-hour rolling log** (hourly rotation, last 24h retained) to
the `giphery_logs` volume — request/access lines, app events, and a security
audit stream, as structured JSON. Secrets/tokens are redacted. View live:

```bash
docker compose logs -f api                  # stdout echo
docker compose exec api ls -la /data/logs   # rotated files
```

## Development

See **CLAUDE.md** for the full command reference (run backend locally, tests,
lint, type-check, migrations, build the Android app).

## Security

Report vulnerabilities privately (see SECURITY.md → Responsible disclosure).
Never commit `.env` or real secrets.
