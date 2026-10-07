# 业务 API

Python 3.12 + uv，FastAPI / Dishka / 异步 SQLAlchemy。

```bash
uv sync --dev
uv run alembic upgrade head
uv run python -m risk_api
uv run ruff check src alembic tests
uv run mypy src/risk_api
uv run pytest -q
uv run python -m risk_api.export_openapi
```

`shared/` 管理配置、数据库、日志、HTTP 信封和中间件；模块的 `api/` 管理路由、Handler、DTO。
ORM 放模块内 `model.py`；工作台新增记录位于 `modules/modeling/workbench_model.py`，旧 ORM 仅用于保留历史表。

模型工作台通过独立 `ModelClient` 调用 RiskGNN 内部 HTTP，不安装 Torch 或本地 runtime 包。
业务记录与 Outbox 在同一事务提交，应用生命周期启动异步投递器；模型服务不可用不影响其他模块。
`RISK_GNN_URL`、`RISK_GNN_API_TOKEN` 及建模 Bucket 凭据由 Compose 注入。

本地命令与环境变量见[本地开发](../docs/architecture/local-development.md)，
模型架构见[工作台](../docs/architecture/modeling-workbench.md)。
