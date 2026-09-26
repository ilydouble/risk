FROM ghcr.io/astral-sh/uv:0.8.22-python3.12-bookworm-slim
WORKDIR /app/backend
COPY com_risk_model/runtime /app/com_risk_model/runtime
COPY backend/pyproject.toml backend/uv.lock ./
COPY backend/src ./src
RUN uv sync --frozen --no-dev --no-editable
COPY backend/alembic.ini ./
COPY backend/alembic ./alembic
COPY backend/seed ./seed
COPY com_risk_model/data/processed/smesd/test.json /app/com_risk_model/data/processed/smesd/test.json
RUN mkdir -p /app/com_risk_model/weights
ENV PATH="/app/backend/.venv/bin:${PATH}" PYTHONPATH=/app/backend/src
CMD ["sh", "-c", "alembic upgrade head && python -m risk_api"]
