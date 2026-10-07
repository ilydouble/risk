# 风控工作台

React 工作台、Go Session 网关、FastAPI 业务 API 与独立 RiskGNN 模型服务组成的 Monorepo。
保留注册登录、企业检索、画像、图谱及文件直传。八家企业的评分、解释、报告和授信决策仍是演示内容。
`/overview` 是新加坡数据的静态统计；`/modeling` 执行真实数据校验、子集训练、独立测试与模型发布。

## 启动

```bash
cp .env.example .env
# 按本机需要设置端口、凭据和 BUILD_* 构建代理
docker compose up --build -d
docker compose ps -a
```

默认访问 http://localhost:18080 ，先自助注册再登录。已有 `.env` 可继续使用，新增配置有本地默认值。
Compose 默认启动 `riskgnn` HTTP 服务和 `riskgnn-worker`；模型服务不发布宿主机端口。
PostgreSQL 内独立创建 `riskgnn` 数据库与用户，RustFS 内创建 `risk-modeling` Bucket 和专用应用凭据。
业务 API 不安装 Torch，不导入模型代码。原业务数据与对象不迁移、不删除。

## 第一条模型链路

1. 打开「模型训练工作台」，选择同事的 `comrisk_export` ZIP（上限 512 MiB）。
2. 浏览器预览文件索引，直传对象存储；Worker 全量扫描并校验数据协议。
3. 校验通过后选择 RiskGNN 自身特征或自身特征与图关系，默认 `smoke-v1`、2 轮、CPU。
4. 查看阶段、epoch 曲线、Attempt 和增量事件；刷新页面可继续查看。
5. 新进程独立测试结束后，发布不可变模型版本；下载模型包或预测该图内企业。

首版只训练固定 2,000 个有标签目标及其有限图上下文，不做全量训练。
困境分类分数不是授信违约概率。发布不会切换生产模型，也不会上传 GitHub Release。
旧 SMEsD 链接显示停用说明，旧 Bundle 记录和对象保留，不转换成新版本。
Bundle v1 可重新上传做数据分析；原始基线和 RiskGNN+ 等待模型包与研究链路适配。

## 目录

| 目录 | 职责 |
| --- | --- |
| `frontend/` | React、FSD、SDK HTTP、OpenAPI 生成类型、G6、Recharts |
| `backend/` | 用户权限、数据集归属、实验与模型版本、可靠投递 |
| `models/` | 模型研究主线；`service/` 提供 HTTP、Worker、数据分析与模型包 |
| `gateway/` | Go Session 鉴权、Origin 校验、请求 ID |
| `infra/` | 数据库、Bucket、CORS、图谱约束初始化 |
| `contracts/` | 业务和模型服务各自导出的 OpenAPI |
| `docs/architecture/` | 服务边界、数据协议、运行状态与本地开发 |

## 检查

```bash
cd backend
uv sync --dev
uv run ruff check src alembic tests
uv run mypy src/risk_api
uv run pytest -q
uv run python -m risk_api.export_openapi
cd ../models
uv sync --project service --locked
uv run --project service ruff check service
uv run --project service mypy --config-file service/pyproject.toml service
uv run --project service pytest service/tests -q
uv run --project service python -m service.export_openapi
cd ../frontend
npm ci
npm run api:generate
npm run lint && npm run type-check && npm run build
```

PostgreSQL 契约测试需设置 `RISK_TEST_DATABASE_URL`，在随机临时 schema 中执行后清理。
详细命令见[模型服务](models/service/README.md)、[本地开发](docs/architecture/local-development.md)和
[架构索引](docs/architecture/README.md)。每次提交前必须运行后端 Ruff、mypy。
