FROM ghcr.io/astral-sh/uv:0.8.22-python3.12-bookworm-slim
WORKDIR /app/backend
COPY backend/pyproject.toml backend/uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv UV_HTTP_TIMEOUT=180 UV_CONCURRENT_DOWNLOADS=4 uv sync --frozen --no-dev --no-install-project
COPY backend/src ./src
RUN --mount=type=cache,target=/root/.cache/uv UV_HTTP_TIMEOUT=180 UV_CONCURRENT_DOWNLOADS=4 uv sync --frozen --no-dev --no-editable
COPY backend/alembic.ini ./
COPY backend/alembic ./alembic
COPY backend/seed ./seed
ENV PATH="/app/backend/.venv/bin:${PATH}" PYTHONPATH=/app/backend/src
CMD ["sh", "-c", "alembic upgrade head && python -m risk_api"]
