#!/bin/sh
# Apply DB migrations (waiting for Postgres to come up), then exec the app.
# Idempotent: alembic upgrade head is a no-op when already current.
set -e

echo "[giphery] applying database migrations..."
n=0
until alembic upgrade head; do
    n=$((n + 1))
    if [ "$n" -ge 30 ]; then
        echo "[giphery] database not reachable after $n attempts; giving up" >&2
        exit 1
    fi
    echo "[giphery] database not ready, retry $n/30 in 2s..."
    sleep 2
done

echo "[giphery] migrations applied; starting application"
exec "$@"
