# syntax=docker/dockerfile:1

# ---------- builder ----------
FROM python:3.13-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /build

# Build wheels for all deps into a venv we copy into the final image.
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY pyproject.toml ./
# Install only runtime deps (not the [dev] extra) into the venv.
RUN pip install --upgrade pip setuptools wheel && \
    pip install .

# ---------- runtime ----------
FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

# Non-root user; create data dirs it can write to.
RUN groupadd --system giphery && \
    useradd --system --gid giphery --home-dir /app --no-create-home giphery && \
    mkdir -p /app /data/media /data/logs && \
    chown -R giphery:giphery /app /data

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
COPY --chown=giphery:giphery alembic.ini ./
COPY --chown=giphery:giphery alembic ./alembic
COPY --chown=giphery:giphery app ./app

USER giphery
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/api/v1/health').status==200 else 1)"

# Gunicorn manages Uvicorn workers in production.
CMD ["gunicorn", "app.main:app", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--workers", "2", \
     "--bind", "0.0.0.0:8000", \
     "--access-logfile", "-", \
     "--timeout", "60"]
