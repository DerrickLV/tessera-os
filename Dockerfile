FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
COPY requirements.lock pyproject.toml README.md ./
COPY src ./src
COPY web ./web
RUN python -m pip install --upgrade pip && \
    python -m pip install --no-deps -r requirements.lock && \
    python -m pip install --no-deps .

RUN useradd --create-home --uid 10001 tessera && mkdir -p /var/data/tessera && \
    chown -R tessera:tessera /var/data/tessera /app
USER tessera

EXPOSE 8000
CMD ["sh", "-c", "uvicorn tessera_os.portal:create_portal_app --factory --host 0.0.0.0 --port ${PORT:-8000}"]
