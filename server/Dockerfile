# syntax=docker/dockerfile:1

# ---------- builder ----------
FROM python:3.13-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /build

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# The package needs its source present to build a valid wheel; copying app here
# also installs deps from pyproject into the venv.
COPY pyproject.toml ./
COPY app ./app
RUN pip install --upgrade pip setuptools wheel && \
    pip install .

# ---------- runtime ----------
FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

# Run as UID 99 / GID 100 (Unraid's nobody:users) so appdata bind-mounts and
# fresh named volumes are writable without any chown. Numeric USER also works
# if the named user/group already exists; failures are tolerated.
RUN set -eux; \
    groupadd -g 100 appusers 2>/dev/null || true; \
    useradd -u 99 -g 100 -M -d /app -s /usr/sbin/nologin giphery 2>/dev/null || true; \
    mkdir -p /app /data/media /data/logs; \
    chown -R 99:100 /app /data

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
COPY --chown=99:100 alembic.ini ./
COPY --chown=99:100 alembic ./alembic
COPY --chown=99:100 app ./app
COPY --chown=99:100 docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

USER 99:100
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/api/v1/health').status==200 else 1)"

# Migrations run first (entrypoint), then Gunicorn manages Uvicorn workers.
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["gunicorn", "app.main:app", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--workers", "2", \
     "--bind", "0.0.0.0:8000", \
     "--access-logfile", "-", \
     "--timeout", "60"]
