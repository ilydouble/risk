# ComRisk 模型工程

Python 3.12 + uv。模型工程和 `../backend/` 各自维护虚拟环境与锁文件，共用可安装的
`runtime/` 包。CPU Torch 沿用锁定版本；scikit-learn 仅在模型开发环境安装。

| 目录 | 职责 |
| --- | --- |
| `training/` | 数据准备、拟合、预训练、消融、离线指标及模型导出 |
| `testing/` | 开发者主动执行的校验、推理、解释与评估 CLI |
| `tests/` | pytest 自动化测试，默认只从这里收集 |
| `runtime/` | 网络、输入结构、应用预处理/先验、预测、解释和产物校验 |
| `data/` | 本地数据；仅 474 家企业的 `processed/smesd/test.json` 随 Git 提交 |
| `runs/` | 忽略的实验、检查点与导出结果 |
| `weights/` | 下载的正式模型包；只跟踪 `.gitkeep` |
| `docs/` | 研究文档、实验汇总与历史来源记录 |

所有下列命令均在本目录运行。`testing/` 不属于 pytest 测试目录。

## 软件冒烟测试

```bash
uv sync --dev
uv run python -m training.cli demo --nodes 100 --output runs/smoke/data.json
uv run python -m training.cli train --data runs/smoke/data.json \
  --output runs/smoke/run --epochs 3 --patience 2 --hidden 8 --pretrain-epochs 2
uv run python -m training.cli export --run runs/smoke/run --version smoke-v1 \
  --data runs/smoke/data.json --output runs/smoke/exports
uv run python -m testing.cli predict --model runs/smoke/exports/smoke-v1 \
  --data runs/smoke/data.json --ids C00010 C00001 C00010
uv run python -m testing.cli explain --model runs/smoke/exports/smoke-v1 \
  --data runs/smoke/data.json --id C00010
uv run python -m testing.cli evaluate --model runs/smoke/exports/smoke-v1 \
  --data runs/smoke/data.json
```

导出默认写入 `runs/exports/`，同时生成版本目录和 `<版本>.tar.gz`；已有版本不会被覆盖。
合成数据只验证软件行为，不代表真实模型效果。

## 训练与消融

```bash
uv run python -m training.cli fetch
uv run python -m training.cli prepare
uv run python -m training.cli train --data data/processed/smesd \
  --output runs/manual-full --epochs 80
uv run python -m training.cli benchmark --epochs 80 --seeds 42 43 44
```

`fetch` 显式下载固定上游提交并核验 SHA-256，导入模块不会触发下载。
`prepare` 用受限 pickle 解析器转换原始数据并去除跨集重复公司。
完整训练集与验证集不随 Git 提交；`training/run_v1.sh` 串联下载、转换、测试与消融，
可能耗时较长。普通启动和 HTTP 请求不会触发这些步骤。

`train --help` 列出原有训练参数，支持门控全模型、去图、去超图、自身分支、去先验和预训练。
预处理与先验仅在训练集拟合；校准截距和阈值在验证集选择。离线指标计算由训练和本地评估共用。

## 正式权重与本地推理

Git 仅提供测试快照；从仓库 GitHub Release 手工下载模型包，解压到 `weights/<版本>/`。
默认 `smesd-v1/` 内应有 `weights.pt`、`metadata.json`、`metrics.json`、`manifest.json`。
当前迁移保留本机原有选中权重；其他开发者需先取得对应附件，本轮没有发布 Release。

```bash
uv run python -m testing.cli validate --model weights/smesd-v1 \
  --data data/processed/smesd/test.json
uv run python -m testing.cli predict --model weights/smesd-v1 \
  --data data/processed/smesd/test.json --ids C00010
uv run python -m testing.cli explain --model weights/smesd-v1 \
  --data data/processed/smesd/test.json --id C00010
uv run python -m testing.cli evaluate --model weights/smesd-v1 \
  --data data/processed/smesd/test.json
```

`validate --data ...` 可单独检查数据结构；指定 `--model` 后同时检查模型包与快照对应关系。
推理/解释/评估使用已经导出的包，所选快照必须与包内清单一致。
发布和挂载流程见[模型产物约定](../docs/architecture/model-artifacts.md)。
历史实验及数据来源见 [docs/demo-bundle.md](docs/demo-bundle.md)。

## 方法与局限

这是 ComRisk-inspired 独立实现，包含企业自身风险、异构关系与超图聚合，非逐行复现原论文。
预处理和先验仅拟合训练集；训练企业使用折外行业先验，仅进入预测头。
基线为逻辑回归和 HistGradientBoosting；原划分去重后的训练/验证/测试企业数为 2816/686/474。
校准、阈值和版本选择使用验证集，测试集只报告结果；不宣称严格的时间点有效性。
SMEsD 破产分类不等于固定未来窗口违约概率；线性演示分数不是评分卡，特征遮蔽不是 SHAP。
上游数据与模型再分发许可尚未核实，保留历史来源不代表重新授权。

## 开发检查

```bash
uv run ruff check .
uv run mypy
uv run pytest -q
# 正式权重验收：缺少或损坏文件直接失败
uv run pytest -q --require-model
```

网络结构和推理逻辑仅在 `runtime/src/com_risk_runtime/` 维护。
runtime 不依赖训练模块、scikit-learn、FastAPI、Dishka 或数据库。
模型元数据沿用格式 2；正式包的清单与推理接口版本均为 1。

真实权重回归标记为 `model_integration`；普通测试在没有下载权重时明确跳过。
`--require-model` 同样支持后端验收；可用 `BENCHMARK_MODEL_DIR`、`BENCHMARK_DATA_PATH`
和 `BENCHMARK_MODEL_VERSION` 指定待验收的包及快照。完整训练数据未取得时，其划分检查单独跳过。
