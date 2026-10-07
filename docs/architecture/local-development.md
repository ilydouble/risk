# 本地开发与验收

## 推荐：容器运行服务，Vite 开发界面

```bash
cp .env.example .env
docker compose up --build -d backend gateway riskgnn riskgnn-worker
cd frontend && npm ci && npm run dev
```

浏览器使用 http://localhost:3000 。模型服务仍在容器内部，不需要额外的对外端口。
完整容器验收可启动 frontend；若 FRONTEND_HOST_PORT=3000，需先关闭 Vite 避免端口冲突。

基础设施需单独暴露给本机应用时使用 compose.infrastructure.override.yaml。
它只增加 PostgreSQL/Redis/Neo4j 的 loopback 映射，不改变容器内固定端口。

## 本机运行模型服务（可选）

```bash
docker compose -f compose.yaml -f compose.infrastructure.override.yaml \
  up -d postgres redis rustfs rustfs-init model-db-init neo4j neo4j-init
cd models
uv sync --project service --locked
export RISK_GNN_DATABASE_URL=postgresql+asyncpg://riskgnn:local-riskgnn-db-password@localhost:15432/riskgnn
export RISK_GNN_API_TOKEN=local-riskgnn-change-me
export STORAGE_ENDPOINT=http://localhost:19000 MODELING_STORAGE_BUCKET=risk-modeling
export AWS_ACCESS_KEY_ID=RISKMODELINGAPP2026 AWS_SECRET_ACCESS_KEY=local-modeling-change-me
uv run --project service alembic -c service/alembic.ini upgrade head
uv run --project service python -m uvicorn service.api.app:create_app --factory --port 8001
# 另一个终端使用相同环境与工作目录：uv run --project service python -m service.execution.worker
```

本机业务 API 设置 RISK_GNN_URL=http://localhost:8001 及相同服务令牌，数据库用 risk 库，
不要复用模型数据库账号。其他基础设施配置参照 .env.example 和 compose.yaml。
不要同时启动本机和容器 Worker 指向不同工作目录；恢复依赖相同持久目录。

## Compose

```bash
cp .env.example .env
docker compose up --build -d
docker compose ps -a
docker compose logs -f backend demo-seed
```

浏览器默认访问 `http://localhost:18080`；登录页可自助注册，注册后再登录，新环境不预置账号。新环境请先修改 `.env` 中基础设施的示例凭据。项目名 `risk` 负责容器命名空间，服务键不重复加前缀。运行 `docker compose down` 不删除命名卷；服务更名后可加 `--remove-orphans` 清理旧容器，不使用 `-v`。Redis 不持久化，重建时需要重新登录。新空卷写入八家演示企业；已有卷中的旧账号和企业不会自动删除。

宿主机端口在 `.env` 中单独设置，所有映射只绑定 `127.0.0.1`；容器内端口和服务间地址保持固定：

| 变量 | 默认宿主机端口 | 容器端口 |
| --- | ---: | ---: |
| `FRONTEND_HOST_PORT` | 18080 | 80 |
| `GATEWAY_HOST_PORT` | 18081 | 8081 |
| `RUSTFS_API_HOST_PORT` | 19000 | 9000 |
| `RUSTFS_CONSOLE_HOST_PORT` | 19001 | 9001 |
| `POSTGRES_HOST_PORT` | 15432 | 5432 |
| `REDIS_HOST_PORT` | 16379 | 6379 |
| `NEO4J_HTTP_HOST_PORT` | 17474 | 7474 |
| `NEO4J_BOLT_HOST_PORT` | 17687 | 7687 |

本机默认的 Origin 白名单随前端端口变化，浏览器预签名地址随 RustFS API 端口变化；独立运行的 Vite 仍监听 3000，其 API 代理会读取仓库根目录 `.env` 的网关端口。自定义域名可显式设置 `PUBLIC_ORIGINS`、`STORAGE_PUBLIC_ENDPOINT`，`VITE_API_PROXY` 仍可覆盖开发代理。旧 `.env` 如保留固定的 `PUBLIC_ORIGINS` 或 `STORAGE_PUBLIC_ENDPOINT`，需删除这两项旧默认值才能让端口自动联动；自定义值会继续覆盖默认值。

镜像构建如需经过宿主机代理，在 `.env` 设置 `BUILD_HTTP_PROXY`、`BUILD_HTTPS_PROXY`，地址可使用 `host.docker.internal`；`BUILD_NO_PROXY` 用于排除直连地址。网关构建在线下载 Go 模块；需使用模块镜像时设置 `BUILD_GOPROXY`，留空则采用 Go 默认源。这些变量只用于构建步骤，不传给运行中的应用。RustFS 服务固定为 `rustfs/rustfs:1.0.0`，切换镜像前保留现有数据卷。

后端与种子容器在本地默认输出易读的 `pretty` 日志；服务器有日志采集器时设置 `RISK_LOG_FORMAT=json`，输出单行 JSON。`RISK_LOG_LEVEL` 默认 `INFO`，只控制应用日志。业务请求的日志带 `X-Request-ID`，可以从响应头复制该值在容器日志中检索；成功的健康检查不产生日志。容器日志的保留期限取决于 Docker 配置。

## 模型工作台

无需预下载旧权重。从 `/modeling` 上传 comrisk_export ZIP，等待校验，运行默认两轮子集实验，
独立测试完成后发布和下载。模型服务未启动时登录与企业演示仍可使用。
运行边界见[工作台](modeling-workbench.md)，命令行重放见[模型服务](../../models/service/README.md)。

## 组件命令

```bash
cd backend && uv sync --dev
uv run ruff check src alembic tests
uv run mypy src/risk_api
uv run pytest -q tests
cd ../gateway && go test ./...
cd ../frontend && npm ci
npm run api:generate
npm run demo:generate
npm run lint && npm run type-check && npm run build
```

导出契约在 `backend/` 执行 `uv run python -m risk_api.export_openapi`，随后生成前端类型，并检查 Git diff。演示种子生成到 `backend/seed/demo/`，重复生成也应无差异。提交前始终运行后端 Ruff 与 mypy。

## 最小验收链路

1. 空卷首次启动后 `postgres`、`redis`、`rustfs`、`neo4j`、`backend`、`riskgnn` 健康；四个 init/seed 容器正常退出。演示库有八家企业且无预置用户，重复运行 init/seed 不覆盖数据。
2. 登录后检索企业，打开画像、1–3 跳图谱及评分；评分与解释必须标记为演示快照。
3. 在画像上传一个测试文件，经 RustFS 直传、确认登记、下载并核对字节。报告、决策、模型看板和批量评估仍能显示演示标识。
4. 校验 401 会话过期、503 Redis 故障、伪造身份头、非法 Origin、参数 422 和不存在资源的统一信封。
5. 从 `/modeling` 上传完整新加坡 ZIP，等待服务端校验；创建子集实验并查看 epoch、Attempt 和事件。
6. 独立测试完成后发布版本，下载核对摘要，独立目录加载预测；未知 ID 返回 404。
7. 取消实验或重启 Worker 后状态可恢复；不同用户无法访问彼此数据。原卷与旧记录始终保留。
