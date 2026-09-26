FROM ghcr.io/astral-sh/uv:0.8.22-python3.12-bookworm-slim
WORKDIR /app/backend
COPY com_risk_model/runtime /app/com_risk_model/runtime
COPY backend/pyproject.toml backend/uv.lock ./
COPY backend/src ./src
RUN uv sync --frozen --no-dev --no-editable
COPY backend/alembic.ini ./
COPY backend/alembic ./alembic
COPY backend/seed ./seed
COPY backend/data/processed/smesd/test.json ./data/processed/smesd/test.json
COPY backend/artifacts/smesd-v1 ./artifacts/smesd-v1
COPY backend/docs/demo-bundle-manifest.json ./docs/demo-bundle-manifest.json
ENV PATH="/app/backend/.venv/bin:${PATH}"
CMD ["sh", "-c", "alembic upgrade head && python -m risk_api"]
