# 单模型工作台服务

服务负责 HTTP、任务队列、租约、取消、事件与产物管理。
当前默认部署 RiskGNN+，通过 `python -m riskgnn.workbench_cli` 启动模型侧进程。
数据适配、load/split、训练、测试和预测均位于 `../riskgnn/`，服务不导入模型代码。

## 目录

```text
src/model_service/
  app.py / dependencies.py   应用装配和生命周期
  shared/                   配置、数据库、日志、HTTP 与上传外层契约
  modules/
    jobs/                   任务 API、执行记录及页面流程组合
    artifacts/              产物记录查询
    models/                 当前运行时声明与预测 API
  execution/
    contracts/              执行请求、结果、事件与错误，按职责分文件
    runtime.py              固定模型 CLI 的根目录与声明文件
    process.py              启动模型 CLI、采集事件、终止进程组
    executor.py             操作恢复和产物上传
    worker.py               领取任务与租约监督
```

没有 ModelAdapter 抽象或可执行插件注册；数据适配抽象在模型目录的 dataset_adapters/base.py。
上传包必须含 risk_dataset_contract.json，服务只解释外层身份与版本。

## 环境与运行

服务使用 Python 3.12、uv 和 CPU Torch，原研究 requirements 与 Python/CUDA 环境独立。
JevForge 以本地路径依赖安装，源码及固定版本见 [第三方来源](../vendor/jevforge/UPSTREAM.md)。
镜像同时 COPY 服务和全部模型源码；HTTP 与 Worker 共用镜像、数据库和持久工作目录。
HTTP 进程不导入 Torch，模型运算仅在子进程中执行。

以下命令在 models/ 下执行：

```bash
uv sync --project service --locked
uv run --project service alembic -c service/alembic.ini upgrade head
uv run --project service python -m model_service.cli serve
# 另一终端，同一环境：
uv run --project service python -m model_service.execution.worker
```

本机需设置 RISK_GNN_DATABASE_URL、RISK_GNN_API_TOKEN、RISK_GNN_WORKSPACE、
STORAGE_ENDPOINT、MODELING_STORAGE_BUCKET 及对象存储凭据。
MODEL_CODE_ROOT 指向 models/；仓库可编辑安装自动使用源码位置，镜像设置为 /app/models。
协议中的本地路径均规范为绝对路径，不依赖子进程工作目录恰好与父进程相同。

业务后端通过内部 HTTP 调用，模型服务只在 Compose 内部监听 8000，不发布宿主机端口。
研究 CLI 使用自己的本地数据，不需要启动数据库、对象存储或 HTTP。

## 协议与破坏性升级

- 当前模型 runtime_id=riskgnn、runtime_version=3，执行 contract_version=2。
- 数据包清单 contract_version=1，与执行协议独立。
- 新模型产物为 riskgnn-plus-model-v1；历史 riskgnn-model-v2 可继续预测，测试报告独立输出。
- 业务 V0007 将已有记录标记为旧代次并停止旧投递，新记录使用代次 2。
- 模型库 V0002 取消原型阶段的待执行/运行任务，清除旧租约。
- 旧原型协议不兼容；本次 RiskGNN v2 模型保留预测，旧训练配置需新建 Plus 实验。
- 完整模型、超图、资源和校准边界见[RiskGNN+ 工作台](../../docs/architecture/riskgnn-plus-workbench.md)。

部署用仓库根目录的 docker compose up --build -d。升级时需重建并重启后端、模型 HTTP 和 Worker。
不使用 down -v 清理历史卷。

## 检查

```bash
uv run --project service ruff check --config service/pyproject.toml service
uv run --project service mypy --config-file service/pyproject.toml service/src/model_service
uv run --project service pytest service/tests -q
uv run --project service python -m model_service.export_openapi
```

数据库相关测试设置 RISK_TEST_DATABASE_URL，使用随机临时 schema。
研究 CLI 的数值回归确保共用训练循环没有改变原命令的输出。
新服务和模型接入模块统一使用顶部 import；不使用延迟导入规避模块边界。

更多文档：

- [数据集 ZIP 契约](../../docs/architecture/dataset-contract.md)
- [数据适配器与模型 CLI](../../docs/architecture/dataset-adapters.md)
- [实验参数、配置快照与实际执行规模](../../docs/architecture/experiment-configuration.md)
- [执行协议](../../docs/architecture/model-execution-contract.md)
- [任务恢复](../../docs/architecture/modeling-execution.md)

## 真实数据集适配

模型侧支持 ACRA、SMEsD V5 JSON、UK v1；专用文档分别位于
[acra](../riskgnn/dataset_adapters/acra/README.md)、
[smesd](../riskgnn/dataset_adapters/smesd/README.md)、
[uk_dataset_v1](../riskgnn/dataset_adapters/uk_dataset_v1/README.md)。
服务不导入数据适配器。旧 Bundle 与合成演示包已停止支持。
本地数据默认在仓库 datasets/，可用 RISK_DATASETS_ROOT 覆盖；
完整验收运行 `uv run pytest --require-datasets`，缺少真实数据直接失败。
