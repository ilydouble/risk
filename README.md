# 风控工作台

React 工作台、Go Session 网关、FastAPI 业务 API 与独立 RiskGNN+ 模型服务组成的 Monorepo。
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

安装 `uv` 后，从仓库根目录打包已解压的数据，无需安装模型服务环境：

```bash
./scripts/package-dataset --preset smesd \
  --data-dir datasets/comrisk_export_v5/smesd --dataset-version v5
```

默认输出 `models/runs/datasets/smesd-v5.zip`，自动生成契约；已有输出不会覆盖。
`--output` 可指定其他位置，`--json` 提供自动化摘要。更多预设见[打包指南](models/riskgnn/dataset_adapters/PACKAGING.md)。

1. 打开「模型训练工作台」，选择包含数据集契约的 ACRA、SMEsD JSON 或 UK ZIP（上限 512 MiB）。
2. 浏览器预览文件索引，直传对象存储；Worker 全量扫描并校验数据协议。
3. 校验通过后填写目标企业总数与训练轮数，创建 RiskGNN+ 实验；同一 ZIP 可重复用于不同配置。
4. 查看阶段、epoch 曲线、Attempt 和增量事件；刷新页面可继续查看。
5. 校验后的数据集详情可导入真实企业数据，浏览原始属性、关系、超边和事件。
6. 新进程独立测试结束后，发布不可变模型版本；下载模型包或预测该图内企业，并在企业数据列表关联结果。

ACRA / UK 默认最多 2,000 个目标，SMEsD 默认最多 4,000 个，保留原划分和有限图上下文。
创建时保存请求值、最终值和声明快照；重试/重新运行沿用原配置，详情另列实际执行规模。
参数边界、默认值及历史兼容见[实验配置](docs/architecture/experiment-configuration.md)。
当前 RiskGNN+ 消费所选子图的普通边、超边及已有事件，实验档案明确列出参与训练和仅保留的数据。
核心接入、资源边界与历史兼容见[RiskGNN+ 工作台](docs/architecture/riskgnn-plus-workbench.md)。
困境分类分数不是授信违约概率。发布不会切换生产模型，也不会上传 GitHub Release。
旧 SMEsD 链接显示停用说明，旧 Bundle 记录和对象保留，不转换成新版本。
旧 Bundle 协议与合成数据生成器已删除；原始基线及各模型研究入口保持独立。

协作者准备新数据集时，先阅读[数据集 ZIP 接入流程](docs/architecture/dataset-zip-onboarding.md)，
其中列出当前协议、交付材料、自检命令和新增模型适配的分工。

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
uv run --project service pytest service/tests -q --require-datasets
uv run --project service python -m model_service.export_openapi
cd ../frontend
npm ci
npm run api:generate
npm run lint && npm run type-check && npm run build
```

PostgreSQL 契约测试需设置 `RISK_TEST_DATABASE_URL`，在随机临时 schema 中执行后清理。
详细命令见[模型服务](models/service/README.md)、[本地开发](docs/architecture/local-development.md)和
[架构索引](docs/architecture/README.md)。每次提交前必须运行后端 Ruff、mypy。

模型/数据接入：参见[模型执行协议](docs/architecture/model-execution-contract.md)和
[数据适配器与 CLI](docs/architecture/dataset-adapters.md)。执行消息类型位于 `model_service` 内，数据适配器位于 `models/riskgnn/dataset_adapters/`，
模型研究脚本保持原使用方式；工作台不统一规定数据集的 load、split 或训练算法。

新数据包必须包含 [risk_dataset_contract.json](docs/architecture/dataset-contract.md)。此次升级使旧工作台记录和模型失效，需按新契约重新上传；原研究脚本及企业演示功能保留。

## 智能助手

`/chat` 已接入 Strands Agents 1.60.0，支持持久会话、流式回答、公开推理片段、工具过程和停止执行。
沿用智能体模型设置，默认使用 `RISK_LLM_*`；端点须支持 OpenAI 兼容流式工具调用。
本轮提供只读 `current_time` 工具；工作台问数仍是独立的受控查询功能，尚未接为 Agent 工具。
更新后重建后端和前端，后端启动自动迁移到 V0009；旧数据保留。
详见[Agent 架构](docs/architecture/agent-conversation.md)和[消息协议](docs/architecture/agent-protocol.md)。
