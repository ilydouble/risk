# 风控工作台

面向海外企业信用评估的内部演示工作台。当前已接通自助注册、登录、企业检索、企业画像、Neo4j 关系图谱、评分及文件上传/下载。原工作台的八家企业、评分和解释仍为种子演示快照；报告、授信决策、模型看板和批量评估仍为前端演示。另有独立 `/benchmark` 专区，使用 SMEsD 匿名测试快照与已保存的模型权重展示真实预测和离线评估。两套企业编号互不映射，基准结果不代表正式征信数据或未来违约概率。界面沿用原视觉并支持中英文切换。

## 本地启动

需要 Docker Compose。复制示例环境变量并启动：

```bash
cp .env.example .env
docker compose up --build -d
docker compose ps -a
```

默认打开 `http://localhost:18080`。`.env` 可用 `FRONTEND_HOST_PORT`、`GATEWAY_HOST_PORT`、`RUSTFS_API_HOST_PORT`、`RUSTFS_CONSOLE_HOST_PORT` 改变四个宿主机端口；容器内端口固定，映射仍只绑定本机。登录页可自助注册，注册后再登录；新环境不预置账号。共享环境请先更换基础设施的示例凭据，并另行设计开放注册的准入与防滥用策略。

Compose 启动 PostgreSQL 18、Redis、RustFS 1.0.0 GA、Neo4j Community、FastAPI 后端、Go 网关和 Caddy 前端；项目名固定为 `risk`，服务键使用 `postgres`、`backend` 等功能名，容器名如 `risk-rustfs-1`。一次性容器创建对象存储 Bucket/应用凭据、图谱约束，并为新环境补入八家精选演示企业；后端每次启动先执行 Alembic 迁移。数据存于命名卷，重复启动不清空；现有卷中的旧演示记录仍会保留。可选构建代理通过 `.env` 的 `BUILD_HTTP_PROXY`、`BUILD_HTTPS_PROXY`、`BUILD_NO_PROXY` 配置。

登录后从侧栏进入 **SMEsD 基准**，或直接访问 `/benchmark`；可按匿名编号检索，查看画像、预测与特征遮蔽敏感性、一跳有向关系及保存的评估指标。随仓库提供 474 家测试样本及所选权重，首次启动无需下载训练集；完整重训仍需另外取得训练/验证数据。[基准说明](docs/architecture/benchmark.md)列出数据来源、验证命令与展示边界。

后端业务请求及关键写入输出到容器日志，可用 `docker compose logs -f backend demo-seed` 查看，并按响应头的 `X-Request-ID` 关联请求。本地默认 `RISK_LOG_FORMAT=pretty`；服务器采集日志时设为 `json`。`RISK_LOG_LEVEL` 可调整应用日志级别；日志字段与保留边界见[后端架构文档](docs/architecture/backend.md)。

## 仓库结构

| 路径 | 用途 |
| --- | --- |
| `frontend/` | React + TypeScript + Vite；FSD `app/pages/features/entities/shared`；Caddy 镜像 |
| `backend/` | Python 3.12 + uv；FastAPI、Dishka、SQLAlchemy、Alembic、异步基础设施适配 |
| `gateway/` | Go 网关；Session 校验、可信身份注入、统一网关错误 |
| `infra/` | RustFS 与 Neo4j 一次性初始化脚本 |
| `contracts/openapi.json` | 后端导出的权威 HTTP 契约 |
| `docs/architecture/` | 架构、错误约定与本地开发说明 |

## 验证与契约生成

```bash
cd backend
uv sync --dev
uv run ruff check src alembic tests
uv run mypy src/risk_api
uv run pytest -q tests
uv run python -m risk_api.export_openapi
cd ../gateway && go test ./...
cd ../frontend && npm ci
npm run api:generate
npm run demo:generate
npm run lint && npm run type-check && npm run build
```

前端业务请求使用 `@stellarmesh/sdk`，DTO 从 OpenAPI 生成。更改接口时先修改后端并导出契约，再生成前端类型，不手写 DTO。演示企业种子由前端精选案例生成，输出到 `backend/seed/demo/`；生成后检查 Git 差异。详细边界与操作见 [架构导览](docs/architecture/README.md)，协作规则见 [AGENTS.md](AGENTS.md)。
