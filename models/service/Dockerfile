FROM ghcr.io/astral-sh/uv:0.8.22-python3.12-bookworm-slim
WORKDIR /app/models
ARG MODEL_TORCH_GROUP=cpu
COPY service/pyproject.toml service/uv.lock service/.python-version ./service/
COPY vendor/jevforge ./vendor/jevforge
COPY uk_decision ./uk_decision
RUN --mount=type=cache,target=/root/.cache/uv \
    case "$MODEL_TORCH_GROUP" in cpu|cuda) ;; *) exit 2 ;; esac && \
    UV_PROJECT_ENVIRONMENT=/opt/venv UV_HTTP_TIMEOUT=180 UV_CONCURRENT_DOWNLOADS=4 \
    uv sync --project service --frozen --no-default-groups --group "$MODEL_TORCH_GROUP" --no-install-project
ENV MODEL_CODE_ROOT=/app/models
ENV PATH="/opt/venv/bin:${PATH}" RISK_GNN_WORKSPACE=/workspace
ENV HF_HUB_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 TOKENIZERS_PARALLELISM=false
COPY . .
RUN --mount=type=cache,target=/root/.cache/uv UV_PROJECT_ENVIRONMENT=/opt/venv \
    uv sync --project service --frozen --no-default-groups --group "$MODEL_TORCH_GROUP" --no-editable
CMD ["sh", "-c", "alembic -c service/alembic.ini upgrade head && python -m model_service.cli serve"]
