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

登录后从侧栏进入 **SMEsD 基准**，或直接访问 `/benchmark`；可按匿名编号检索，查看画像、预测与特征遮蔽敏感性、一跳有向关系及保存的评估指标。随 Git 提供 474 家测试样本；正式模型包需从本仓库 GitHub Release 下载并解压到 `com_risk_model/weights/<版本>/`，默认版本为 `smesd-v1`。缺少模型时工作台仍能启动，基准接口返回 `BENCHMARK_MODEL_UNAVAILABLE` 503。首次推理不需要训练集；完整重训仍需另外取得训练/验证数据。[基准说明](docs/architecture/benchmark.md)列出数据来源、验证命令与展示边界。

模型开发命令、模型包校验和升级步骤见 [模型工程 README](com_risk_model/README.md) 与 [模型产物约定](docs/architecture/model-artifacts.md)。首次下载由开发者手工完成；仓库不会自动下载或训练。

后端业务请求及关键写入输出到容器日志，可用 `docker compose logs -f backend demo-seed` 查看，并按响应头的 `X-Request-ID` 关联请求。本地默认 `RISK_LOG_FORMAT=pretty`；服务器采集日志时设为 `json`。`RISK_LOG_LEVEL` 可调整应用日志级别；日志字段与保留边界见[后端架构文档](docs/architecture/backend.md)。

## 仓库结构

| 路径 | 用途 |
| --- | --- |
| `frontend/` | React + TypeScript + Vite；FSD `app/pages/features/entities/shared`；Caddy 镜像 |
| `backend/` | Python 3.12 + uv；FastAPI、Dishka、SQLAlchemy、Alembic、异步基础设施适配 |
| `com_risk_model/` | 独立 uv 模型工程；训练、本地测试、共享推理 runtime 和下载的只读权重 |
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
# 下载模型后必须运行；缺少或损坏模型直接失败
uv run pytest -q --require-model tests/test_benchmark_api.py tests/test_demo_bundle.py
uv run python -m risk_api.export_openapi
cd ../gateway && go test ./...
cd ../frontend && npm ci
npm run api:generate
npm run demo:generate
npm run lint && npm run type-check && npm run build
```

前端业务请求使用 `@stellarmesh/sdk`，DTO 从 OpenAPI 生成。更改接口时先修改后端并导出契约，再生成前端类型，不手写 DTO。演示企业种子由前端精选案例生成，输出到 `backend/seed/demo/`；生成后检查 Git 差异。详细边界与操作见 [架构导览](docs/architecture/README.md)，协作规则见 [AGENTS.md](AGENTS.md)。
