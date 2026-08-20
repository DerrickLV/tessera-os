FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
COPY requirements.lock pyproject.toml README.md ./
COPY src ./src

# Tessera OS is not a self-contained Python package at runtime. It resolves a
# *repository root* -- ``paths.project_root()`` looks for ``config/routing.json``
# beside an ``agents/`` directory and raises if it cannot find them -- and reads
# the clause library, the console fixtures, and the portal UI from that root.
#
# So these four directories are application code, not development scaffolding.
# Omitting any one of them produces a container that builds cleanly and then
# fails at startup or at first request.
COPY config ./config
COPY agents ./agents
COPY fixtures ./fixtures
COPY web ./web

# Set explicitly rather than relying on the working-directory fallback, so the
# root stays correct regardless of where the process is started from.
ENV TESSERA_ROOT=/app

RUN python -m pip install --upgrade pip && \
    python -m pip install --no-deps -r requirements.lock && \
    python -m pip install --no-deps .

RUN useradd --create-home --uid 10001 tessera && mkdir -p /var/data/tessera && \
    chown -R tessera:tessera /var/data/tessera /app
USER tessera

EXPOSE 8000
CMD ["sh", "-c", "uvicorn tessera_os.portal:create_portal_app --factory --host 0.0.0.0 --port ${PORT:-8000}"]
