# Build from the project root so uv can resolve the workspace:
#   docker build -f backend/Dockerfile -t growth-chat-backend .

# ── Stage 1: builder ─────────────────────────────────────────────────────────
FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim AS builder

WORKDIR /app

# Workspace root manifest and lock file
COPY pyproject.toml uv.lock ./

# Member manifests — needed for workspace dependency resolution
COPY backend/pyproject.toml              backend/
COPY backend/README.md                   backend/
COPY evaluation/pyproject.toml           evaluation/
COPY data/database/pyproject.toml        data/database/
COPY data/ingestion/pyproject.toml       data/ingestion/
COPY shared/knowledge_base/pyproject.toml shared/knowledge_base/

# Backend source — required so hatchling editable install registers the .pth file
COPY backend/src/ backend/src/
COPY shared/knowledge_base/src/ shared/knowledge_base/src/

# Install backend deps into .venv; no dev extras, honour the lock file
RUN uv sync --package backend --no-dev --frozen

# ── Stage 2: runtime ─────────────────────────────────────────────────────────
FROM python:3.14-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_ENV=production \
    VIRTUAL_ENV=/app/.venv \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Copy the pre-built venv (no uv, no workspace manifests in this layer)
COPY --from=builder /app/.venv /app/.venv

# Copy backend source from the build context
COPY backend/src/ backend/src/
COPY shared/knowledge_base/src/ shared/knowledge_base/src/

# Non-root user
RUN groupadd --system appgroup \
    && useradd --system --gid appgroup --no-create-home --shell /sbin/nologin appuser \
    && chown -R appuser:appgroup /app

USER appuser

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" || exit 1

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8080"]
