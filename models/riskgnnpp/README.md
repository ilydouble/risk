# RiskGNN++

本目录独立维护 RiskGNN++ 的模型实现、TACR、四模型对照、测试及论文材料。
Python 包名保留 `riskgnn_pp`。RiskGNN+ 基座及 UK loader 复用 `../riskgnn+/`，
不复制共享源码；运行训练时显式提供该研究目录的 Python 导入路径。

```text
riskgnnpp/
  riskgnn_pp/          # 模型、主观逻辑融合、TACR 与 CP 对照
  riskgnn_benchmark/   # 四模型训练与消融，记录两目录的源码快照
  smesd_benchmark/     # SMEsD 基准数据加载
  run_benchmark.py     # UK / SMEsD 训练入口
  replay_paper.py      # 保存预测复放，只需 NumPy
  tests/              # ++ 的融合与前向/反向契约检查
  docs/               # 论文、实验补充、核验报告与原稿存档
```

## 运行

从仓库根目录运行，训练环境需安装 PyTorch、torch-geometric、NumPy、pandas、scikit-learn、SciPy。

```bash
PYTHONPATH=models/riskgnn+ python models/riskgnnpp/run_benchmark.py --help
PYTHONPATH=models/riskgnn+ python models/riskgnnpp/run_benchmark.py \
  --dataset uk --output models/runs/riskgnnpp-uk-new
python models/riskgnnpp/replay_paper.py --output /tmp/riskgnn-paper-replay.json
python -m pytest -c models/riskgnnpp/pytest.ini models/riskgnnpp/tests
```

通过 `python -m riskgnn_pp.evaluate_conformal_comparison` 调用模块时，
`PYTHONPATH` 同时设置为 `models/riskgnnpp:models/riskgnn+`。
历史训练制品仍在 `models/runs/`，原 manifest 和源码快照保持封存。
新的训练快照收集 ++ 和共享 + 两处源码，不因目录拆分遗漏依赖。

## 分流分析

训练只保存预测；概率重校准与 risk–coverage 分流分析单独复放，可跨多个输出目录合并 seed：

```bash
PYTHONPATH=models/riskgnn+:models/riskgnnpp python models/riskgnnpp/analyze_runs.py \
  --run-dir models/runs/riskgnnpp-uk-20261013 \
  --run-dir models/runs/riskgnnpp-uk-20261013-ext \
  --dataset uk --output models/runs/riskgnnpp-uk-20261013/analysis-10seed
```

输出 `analysis.json` 与 `analysis.md`，含重校准前后指标、AURC 与固定覆盖率风险，
以及逐 seed 配对 t / Wilcoxon / bootstrap 区间。冲突权重 γ 在校准集上按 70% 覆盖风险选取；
该集也用于概率重校准。分析输出中的 `tacr` 键表示冲突引导排序，与保形 TACR 评分不同。

[论文与实验索引](docs/README.md) · [RiskGNN+](../riskgnn+/README.md) · [模型索引](../README.md)
