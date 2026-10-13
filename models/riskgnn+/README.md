# SMEsD 边置信度不确定性实验

本目录研究噪声边置信度对 RiskGNN 风险预测的影响，包含场景合成、图嵌入预训练、
配对训练、矩阵调度和汇总分析。它保持独立研究入口。统一模型服务位于 `../service/`；工作台已接入本目录的真实 RiskGNN+ 核心、超图/事件与可重载产物，
见[接入说明](../../docs/architecture/riskgnn-plus-workbench.md)；各独立研究实验不自动成为服务接口。

## 结构

```
riskgnn+/
  <顶层脚本>              # 文档中固定的 CLI 入口，仅转发到包内 main()
  smesd_uncertainty/       # 合法包名的实现包
    protocol.py            # 变体注册表、图/嵌入构造
    simulation.py          # 合成场景生成
    training.py            # 单场景训练与指标
    pretraining.py         # metapath2vec 预训练
    matrix.py              # 多场景矩阵调度与 manifest
    summary.py             # 配对汇总与 bootstrap 区间
    comrisk_base/          # 冻结的历史 RiskGNN 基座（vendor）
  uk_benchmark/            # UK 数据集三臂对照（data.py / training.py）
  tests/
```

顶层脚本名保持不变，因为 `models/riskgnn+/docs/smesd-edge-confidence-experiment.md`
以 `python models/riskgnn+/<脚本>.py` 的形式引用它们。目录名含 `+`，不是合法
Python 标识符，因此实现统一放在 `smesd_uncertainty/` 子包内，脚本运行时以所在
目录为 `sys.path[0]` 直接 `import smesd_uncertainty`，不再修改 `sys.path` 去访问
兄弟目录 `models/riskgnn/`。

## vendor 基座

`smesd_uncertainty/comrisk_base/` 是 `models/riskgnn/{gnn,utils}.py` 的只读快照，
用于切断跨目录裸导入。来源与哈希记录在该子包的 `__init__.py`，同步时需显式更新；
除 `gnn.py` 的内部导入改为 `from .utils import *` 外与来源一致。

## 运行

```bash
cd <repo root>
python models/riskgnn+/simulate_smesd_uncertainty.py --help
python models/riskgnn+/run_uncertainty_matrix.py --help
python models/riskgnn+/summarize_uncertainty_results.py --help
```

训练、预训练与矩阵调度依赖 `torch` 和 `torch-geometric`；场景合成、协议与汇总
仅依赖 `numpy`/`pandas`，其测试可直接运行：

```bash
python -m pytest models/riskgnn+/tests
```

`matrix.py` 会把包内各源文件的 sha256 写入 `matrix_manifest.json`；源码变化会
使旧实验工作目录被拒绝复用，这是预期的安全行为。

## 证据学习与 Table 3 分流对照

新增 `run_triage_comparison.py` 训练真实双分支证据模型与配对 ComRisk，
`evaluate_triage_comparison.py` 从保存的预测重放概率/保形/固定预算分流比较。
协议、校准边界、历史脚本的熵替代问题及命令见
[复核分流对照](docs/triage-comparison.md)。

默认保留上游原论文划分；去重仅作敏感性分析。
原划分三种子实测见[补充实验结果](docs/triage-comparison-results.md)。

## UK 数据集对照

新增 `run_uk_experiments.py`，在 `datasets/uk_dataset_v1` 上复刻
ComRisk / RiskGNN / RiskGNN+ 三臂对照，但训练真实证据双分支模型而非熵替代。
实现位于 `uk_benchmark/`（`data.py` 加载契约不依赖 torch，`training.py` 负责训练与评估）。
协议、数据差异与运行方式见
[UK 对照](docs/uk-comparison.md)，实测结果见
[UK 对照结果](docs/uk-comparison-results.md)。

## 研究文档

- [RiskGNN+ 文档索引](docs/README.md)：原稿、受控实验与分流对照。
- [RiskGNN++ 文档索引](../riskgnnpp/docs/README.md)：最新方法论文、实验复放与核验报告。

RiskGNN++ 已独立到 `../riskgnnpp/`；四模型训练入口和论文复放入口也归该目录。
本目录保留 RiskGNN+ 与共享基座，训练制品统一保留在 `models/runs/`。
