# Dockerfile — M0 Oracle migration readiness (see docs/operations/ORACLE_MIGRATION_M0.md)
#
# NOT used by Render today (Render's native Python runtime builds/runs this
# repo directly — verified live via the Render API: buildCommand
# "pip install -r requirements.txt", startCommand "gunicorn  app:app", no
# Dockerfile involved). This image exists only for the Oracle Compose stack
# in docker-compose.oracle.yml and for local/manual verification.
#
# Does NOT reuse gunicorn.conf.py's implicit bind behavior — that file is
# auto-loaded by gunicorn on Render too (see its own header comment), so it
# is left untouched here. The container's bind address/port is passed as an
# explicit CLI flag in CMD instead, which take precedence over the config
# file without needing to touch a file Render also loads.

FROM --platform=$BUILDPLATFORM python:3.11-slim AS base

# PYTHON_VERSION=3.11.0 confirmed via live Render env vars (2026-08-28);
# python:3.11-slim tracks the latest 3.11.x patch, which is the closer
# match to "keep patched" than pinning the exact historical patch release.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# requirements.txt has exactly one native-extension dependency
# (psycopg2-binary==2.9.12), which ships a manylinux aarch64 wheel — no
# build toolchain (gcc/libpq-dev) needed for either amd64 or arm64.
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Non-root runtime user — nothing in this repo requires root at runtime.
RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin appuser \
    && chown -R appuser:appuser /app
USER appuser

# Internal-only: Caddy is the sole public listener (see docker-compose.oracle.yml
# and Caddyfile.oracle). This EXPOSE is documentation only, not enforcement.
EXPOSE 10000

# Uses the stdlib (no curl in this slim image) to hit app.py's existing
# /health route (app.py:6187) — same endpoint Render's own health check
# path is documented (but, per live Render config, not actually set) to use.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys,os; \
        urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",\"10000\")}/health', timeout=4).read(); \
        sys.exit(0)" || exit 1

# --bind is a CLI flag, so it overrides/coexists with gunicorn.conf.py's
# workers=1 and post_worker_init without editing that shared file.
# workers=1 is preserved exactly as-is: gunicorn.conf.py's own comment
# explains it's load-bearing (the in-process scheduler dedup check is
# process-local, so >1 worker fires every scheduled job N times).
CMD ["sh", "-c", "exec gunicorn --bind 0.0.0.0:${PORT:-10000} app:app"]
