# RiskGNN 工作台服务

此目录为原研究工程增加 HTTP、Worker、数据适配和模型包能力。
研究开发继续使用`../riskgnn/requirements.txt`、原 Python/CUDA 环境与 `train_*.py` 命令。
服务单独使用 Python 3.12 CPU 环境，不要求研究开发者安装数据库或服务依赖。

## 依赖方向

- `../riskgnn/gnn.py` 是网络实现；服务的模型包装调用 `RiskGNN.forward_batch`。
- `../riskgnn/train_sg_neighbor.py` 提供共同的邻居采样、张量转换与优化步骤。
- 服务维护固定子集、train-only 预处理、检查点选择及可重载产物协议。
- 研究代码不导入 `service`，原脚本参数和默认值保持兼容。
- 当前工作台只开放 `smoke-v1`，全量/GPU/消融实验继续使用原研究命令。

```text
service/
  api/             内部 HTTP 与 DTO
  execution/       Job、Attempt、租约、事件与子进程监督
  adapters/        ZIP、数据校验、固定子集准备
  datasets/        数据协议识别与 Bundle 校验
  analysis/        质量、分布漂移及特征信号
  runners/         可用模型及数据兼容能力
  model/           原网络与采样的薄包装，不另写前向算法
  training/        工作台实验编排与独立测试
  runtime/         模型包加载、图内企业预测
  tools/           静态新加坡概览
  alembic/         执行数据库迁移
  tests/           自动化测试
  docs/            验收与历史来源
```

## 独立服务环境

以下命令均在 `models/` 执行，避免改动研究用的 `.venv`：

```bash
uv venv service/.venv --python 3.12
uv pip sync --python service/.venv/bin/python --torch-backend cpu service/requirements-dev.lock.txt
source service/.venv/bin/activate
```

运行镜像使用 `requirements.lock.txt`；开发锁额外包含 Ruff、mypy、pytest、httpx。
锁文件面向 Linux x86_64 / Python 3.12 / CPU，不用于覆盖研究者的 CUDA 环境。
`requirements.in` 引用 ../riskgnn 的研究依赖，再补服务依赖；无需安装本项目为 Python 分发包。
更新依赖时使用 uv 重新生成两个锁，已有锁作为约束可避免无关升级：

```bash
uv pip compile service/requirements.in -c service/requirements.lock.txt --python-version 3.12 --python-platform x86_64-unknown-linux-gnu --torch-backend cpu --emit-index-url -o service/requirements.lock.txt
uv pip compile service/requirements-dev.in -c service/requirements.lock.txt -c service/requirements-dev.lock.txt --python-version 3.12 --python-platform x86_64-unknown-linux-gnu --torch-backend cpu --emit-index-url -o service/requirements-dev.lock.txt
```

研究依赖升级与旧约束冲突时，明确更新对应约束并做模型回归，不覆盖研究依赖版本。

## 本地训练、测试与导出

激活服务环境后，无需启动 PostgreSQL、对象存储或 HTTP：

```bash
python -m service.cli validate-data --input ~/Downloads/comrisk_export.zip --output runs/sg/validated
python -m service.cli prepare --input runs/sg/validated --output runs/sg/prepared
python -m service.cli train --input runs/sg/prepared --output runs/sg/model --epochs 2
python -m service.cli test --input runs/sg/model
python -m service.cli verify --input runs/sg/model
python -m service.cli predict --input runs/sg/model --ids YOUR_UEN
python -m service.cli export --input runs/sg/model --output runs/exports/model.zip
```

`YOUR_UEN` 使用模型 `ids.json` 内的 ID。测试命令在新进程重载模型。
导出 ZIP 包含权重、固定嵌入、预处理、图与特征、ID、划分及文件摘要。
下载解压后可直接 `verify`、`test`、`predict`；不执行上传 ZIP 里的 Python 脚本。
既有工作台 v1 模型包可继续加载。新实验使用原 RiskGNN 的构造顺序，随机种子相同
也不保证与早期服务独立实现的初始化相同；元数据记录研究代码和服务代码的共同摘要。
本地研究 `.pkl`/预测 `.npz` 不会自动转换或发布，需按完整产物协议接入。

## HTTP 与 Worker

仓库根目录 `docker compose up --build -d` 启动相同镜像的 HTTP 和 Worker。
本机运行需设置 `RISK_GNN_DATABASE_URL`、`RISK_GNN_API_TOKEN`、`RISK_GNN_WORKSPACE`、
`STORAGE_ENDPOINT`、`MODELING_STORAGE_BUCKET`、`AWS_ACCESS_KEY_ID`、`AWS_SECRET_ACCESS_KEY`。

```bash
alembic -c service/alembic.ini upgrade head
python -m uvicorn service.api.app:create_app --factory --port 8001
# 另一个终端，相同环境和 models 工作目录：
python -m service.execution.worker
```

容器内固定 8000；两入口共用模型数据库、Bucket 和持久工作目录。
研究训练不读执行数据库；Alembic 只管理服务的任务、尝试和事件。

## 检查

```bash
ruff check service
mypy --config-file service/mypy.ini service
python -m pytest -c service/pytest.ini service/tests -q
python -m service.export_openapi
```

数据库相关测试设置 `RISK_TEST_DATABASE_URL`，只使用随机临时 schema。
研究脚本不纳入服务格式重写；兼容检查覆盖原入口、采样、前向及完整模型重载。
详见[训练协议](../../docs/architecture/training-profile.md)、
[执行协议](../../docs/architecture/modeling-execution.md)、[模型包](../../docs/architecture/model-artifacts.md)。

历史研究兼容检查见[兼容验收](docs/research-compatibility.md)；本轮迁移见[集成验收](docs/models-integration.md)。

## 数据分析与模型选择

- 上传自动识别 `sg-comrisk-v1` 或 `bundle-v1`，两种协议分别校验，脚本不执行。
- 新加坡全量扫描质量；PSI 按 seed 0 划分各取至多 5,000 行稳定样本，报告注明范围。
- Bundle 复用旧工作台的样本、关系和时间约束、特征信号、PSI 及泄漏提示。
- `/models/capabilities` 返回明确能力；训练输入指定 runnerId。新加坡支持
  `riskgnn-node-edge` / `riskgnn-node-only`，Bundle 目前只提供分析。
- 实验档案保存模型、数据摘要、目标、实际特征、预处理、划分、检查点及实现摘要。
- Docker 构建上下文为 models，复制全部模型源码，排除本地数据、权重、环境与缓存。
  原始基线需要额外编译依赖；RiskGNN+ 真实入口仍需验收，均不静默开放训练。
