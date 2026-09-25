# 风控工作台

面向海外企业信用评估的内部演示工作台。当前已接通登录、企业检索、企业画像、Neo4j 关系图谱、评分及文件上传/下载。**企业、评分和解释均为种子演示快照，未运行真实模型或接入正式征信数据。** 报告、授信决策、模型看板和批量评估保留前端演示逻辑。界面沿用原视觉并支持中英文切换。

## 本地启动

需要 Docker Compose。复制示例环境变量并启动：

```bash
cp .env.example .env
docker compose up --build -d
docker compose ps -a
```

打开 `http://localhost:18080`。默认本机演示账号 `demo`，示例密码 `demo-change-me`；可在 `.env` 设置 `DEMO_USER`、`DEMO_PASSWORD`。网关诊断端口为 `18081`，RustFS API/Console 为 `19000/19001`，都只绑定本机。共享环境请先更换所有示例凭据。

Compose 启动 PostgreSQL 18、Redis、RustFS 1.0.0 GA、Neo4j Community、FastAPI 后端、Go 网关和 Caddy 前端；项目名固定为 `risk`，服务键使用 `postgres`、`backend` 等功能名，容器名如 `risk-rustfs-1`。一次性容器创建对象存储 Bucket/应用凭据、图谱约束和演示种子；后端每次启动先执行 Alembic 迁移。数据存于命名卷，重复启动不清空。可选构建代理通过 `.env` 的 `BUILD_HTTP_PROXY`、`BUILD_HTTPS_PROXY`、`BUILD_NO_PROXY` 配置。

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
npm run lint && npm run type-check && npm run build
```

前端业务请求使用 `@stellarmesh/sdk`，DTO 从 OpenAPI 生成。更改接口时先修改后端并导出契约，再生成前端类型，不手写 DTO。详细边界与操作见 [架构导览](docs/architecture/README.md)，协作规则见 [AGENTS.md](AGENTS.md)。
