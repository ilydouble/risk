FROM ghcr.io/astral-sh/uv:0.8.22-python3.12-bookworm-slim
WORKDIR /app/models
COPY service/requirements.lock.txt ./service/requirements.lock.txt
RUN --mount=type=cache,target=/root/.cache/uv uv venv /opt/venv && UV_HTTP_TIMEOUT=180 UV_CONCURRENT_DOWNLOADS=4 uv pip sync --python /opt/venv/bin/python --torch-backend cpu service/requirements.lock.txt
ENV PATH="/opt/venv/bin:${PATH}" RISK_GNN_WORKSPACE=/workspace
COPY . .
CMD ["sh", "-c", "alembic -c service/alembic.ini upgrade head && python -m service.cli serve"]
