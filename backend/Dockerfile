FROM ghcr.io/astral-sh/uv:0.8.22-python3.12-bookworm-slim
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY alembic.ini ./
COPY alembic ./alembic
COPY src ./src
COPY seed ./seed
ENV PATH="/app/.venv/bin:${PATH}" PYTHONPATH=/app/src
CMD ["sh", "-c", "alembic upgrade head && python -m risk_api"]
