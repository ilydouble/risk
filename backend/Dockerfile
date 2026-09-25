FROM ghcr.io/astral-sh/uv:0.8.22-python3.12-bookworm-slim
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY alembic.ini ./
COPY alembic ./alembic
COPY src ./src
COPY seed ./seed
COPY data/processed/smesd/test.json ./data/processed/smesd/test.json
COPY artifacts/smesd-v1 ./artifacts/smesd-v1
COPY docs/demo-bundle-manifest.json ./docs/demo-bundle-manifest.json
ENV PATH="/app/.venv/bin:${PATH}" PYTHONPATH=/app/src
CMD ["sh", "-c", "alembic upgrade head && python -m risk_api"]
