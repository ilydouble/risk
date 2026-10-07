# SMEsD 边置信度不确定性实验

本目录研究噪声边置信度对 RiskGNN 风险预测的影响，包含场景合成、图嵌入预训练、
配对训练、矩阵调度和汇总分析。它保持独立研究入口。统一模型服务位于 `../service/`；当前能力列表将本目录标为
待验收，目录进入镜像不代表其中每个实验已提供训练或发布接口。

## 结构

```
riskgnn+/
  <5 个顶层脚本>          # 文档中固定的 CLI 入口，仅转发到包内 main()
  smesd_uncertainty/       # 合法包名的实现包
    protocol.py            # 变体注册表、图/嵌入构造
    simulation.py          # 合成场景生成
    training.py            # 单场景训练与指标
    pretraining.py         # metapath2vec 预训练
    matrix.py              # 多场景矩阵调度与 manifest
    summary.py             # 配对汇总与 bootstrap 区间
    comrisk_base/          # 冻结的历史 RiskGNN 基座（vendor）
  tests/
```

顶层脚本名保持不变，因为 `docs/architecture/smesd-edge-confidence-experiment.md`
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
