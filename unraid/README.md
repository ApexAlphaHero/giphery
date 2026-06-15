# Giphery on Unraid (native templates + SWAG)

Runs Giphery as two Docker containers managed by Unraid's own template system
(no Compose plugin), reverse-proxied by your existing **SWAG** container.

```
phone ──HTTPS──> SWAG ──http (giphery net)──> giphery-api ──> giphery-db
                                                  └──> /mnt/user/appdata/giphery/{media,logs}
```

## 0. One-time: image + network

**Image (GHCR).** Pushing to `main` builds and publishes
`ghcr.io/apexalphahero/giphery-api:latest` via the *Publish API image* workflow.
After the first publish, make the package **public** so Unraid can pull it
without credentials:
GitHub → your profile → **Packages** → `giphery-api` → *Package settings* →
**Change visibility → Public**. (Or, to keep it private, add your GHCR
username + a read:packages PAT under Unraid → Settings → Docker → registries.)

**Network.** SWAG and both Giphery containers must share a user-defined docker
network so SWAG can reach `giphery-api` by name. On the Unraid console:

```sh
docker network create giphery
docker network connect giphery swag     # use your SWAG container's name
```

(If you already have a proxy network, you can use that name instead and set it
in both templates + the SWAG conf upstream.)

## 1. Add the templates

Copy both XML files to the Unraid templates folder, then add them from the
Docker tab:

```sh
cp giphery-db.xml giphery-api.xml /boot/config/plugins/dockerMan/templates-user/
```

Docker tab → **Add Container** → *Template* dropdown → **giphery-db**, fill in:
- **POSTGRES_PASSWORD** — a strong password.
- Network is preset to `giphery`. **Do not add a port.** Apply.

Then **Add Container** → **giphery-api**, fill in:
- **DATABASE_URL** — replace `CHANGE_ME` with the same Postgres password:
  `postgresql+asyncpg://giphery:<password>@giphery-db:5432/giphery`
- **SECRET_KEY** and **INVITE_ENC_KEY** — generate each with `openssl rand -hex 32`.
- **PUBLIC_BASE_URL** and **CORS_ALLOWED_ORIGINS** — your real URL, e.g.
  `https://giphery.yourdomain.com`.
- Network `giphery`. **No host port.** Apply.

The API container runs as **UID 99 / GID 100**, so the appdata folders
(`/mnt/user/appdata/giphery/...`, owned by `nobody:users`) are writable with no
extra steps. It **runs migrations automatically** on start and waits for the DB.

## 2. SWAG

```sh
cp swag/giphery.subdomain.conf /mnt/user/appdata/swag/nginx/proxy-confs/
docker restart swag
```

- Add a DNS record for `giphery.yourdomain.com` (or use a wildcard cert), and
  make sure SWAG already serves that domain (valid CA cert — Let's Encrypt etc.).
- The conf proxies to `giphery-api:8000` over the `giphery` network and forwards
  the real client IP (needed for rate limiting).

## 3. First run

1. Open `https://giphery.yourdomain.com` → you'll land on first-run setup →
   create the **admin** account.
2. Log in → create an **invitation** (label it, set max-uses) → copy the code.
3. On the phone (Giphery app): enter the server URL, the code, and a username →
   you're in.

## Verifying / troubleshooting

```sh
# health (from the Unraid console, on the giphery network)
docker exec giphery-api python -c "import urllib.request;print(urllib.request.urlopen('http://localhost:8000/api/v1/health').read())"

# rolling logs
ls -la /mnt/user/appdata/giphery/logs
docker logs giphery-api          # also echoes app/access/audit JSON lines
```

- **api restarts / 500s on first boot:** it's waiting on `giphery-db` — confirm
  both are on the `giphery` network and the DB password matches `DATABASE_URL`.
- **SWAG 502:** SWAG isn't on the `giphery` network (`docker network connect
  giphery swag`) or the container name differs from `giphery-api`.
- **App won't connect:** it requires real HTTPS. A self-signed cert will be
  rejected by the release build — use a CA-issued cert via SWAG.

## Image channels & updating

Two tags are published to GHCR:

| Tag | Moves when | Use for |
|-----|-----------|---------|
| `:stable` | a release is tagged (`git tag v1.2.3 && git push --tags`) | **production / Unraid auto-update** (the template uses this) |
| `:latest` | every push to `main` | testing the newest build |

The **giphery-db** template adds a `pg_isready` healthcheck so Unraid shows DB
readiness. There's no `depends_on` with native templates, but it isn't needed:
**giphery-api** runs its migration entrypoint with a ~60s retry loop, so it
self-heals regardless of which container starts first.

To update: when a new `:stable` is published, the **giphery-api** container shows
an update in Unraid → **Force update** (or enable CA Auto-Update). It re-runs
migrations on start. To stay on the bleeding edge instead, change the
Repository to `…/giphery-api:latest`.

## Backups

Everything stateful lives under `/mnt/user/appdata/giphery/` (`db`, `media`,
`logs`) — include it in the **Appdata Backup** plugin. The `logs` folder is
disposable (24h rolling).
