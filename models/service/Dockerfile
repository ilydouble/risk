FROM ghcr.io/astral-sh/uv:0.8.22-python3.12-bookworm-slim
WORKDIR /app/models
COPY service/pyproject.toml service/uv.lock service/.python-version ./service/
COPY vendor/jevforge ./vendor/jevforge
RUN --mount=type=cache,target=/root/.cache/uv UV_PROJECT_ENVIRONMENT=/opt/venv UV_HTTP_TIMEOUT=180 UV_CONCURRENT_DOWNLOADS=4 uv sync --project service --frozen --no-dev --no-install-project
ENV MODEL_CODE_ROOT=/app/models
ENV PATH="/opt/venv/bin:${PATH}" RISK_GNN_WORKSPACE=/workspace
COPY . .
RUN --mount=type=cache,target=/root/.cache/uv UV_PROJECT_ENVIRONMENT=/opt/venv uv sync --project service --frozen --no-dev --no-editable
CMD ["sh", "-c", "alembic -c service/alembic.ini upgrade head && python -m model_service.cli serve"]
