# UK 数据集 ComRisk / RiskGNN / RiskGNN+ 对照

在 `datasets/uk_dataset_v1` 上复刻
[`smesd-edge-confidence-experiment.md`](smesd-edge-confidence-experiment.md) 与
[`triage-comparison.md`](triage-comparison.md) 的三模型对照，但训练**真实**的证据
双分支 RiskGNN+，而不是用分类器熵冒充不确定性。

## 数据

UK 快照（`com_risk_runtime.schema.Dataset` v1，train/valid/test 三个互斥文件）：

- 233,251 家公司（train 139,956 / valid 46,664 / test 46,631），三份不共享公司 ID。
- 7 个数值特征；`n_charges` 等 6 个计数列唯一处理，`age_months` 不取对数。
- 4 种关系：`SAME_ADDRESS` / `EQUITY` / `PREVNAME` / `SAME_NAME`。
- 3 类超边：`sic_section` / `postcode_area` / `director_group`
  （`1_字段说明.md`、`2_和SMEsD的差异.md` 仍写 2 类，以数据和 adapter README 为准）。
- 无 person 节点、无 court events，`risk_data = {}`。
- 正样本率约 3.59%（SMEsD 为 57.6%），因此绝对 AUC 与 SMEsD 不可直接比较。
- 无预训练 metapath2vec：节点表征用 `RandomState(embed_seed).normal(0, 0.1)` 的冻结
  随机投影，三个模型共享。`riskgnn_plus` 的 `company_proj` 硬编码 32 维，故 embed_dim=32。
- `SAME_ADDRESS` 边带 `[0.3, 1.0]` 的证据权重（**不是**校准置信度），其余关系恒为 1.0。

预处理走 adapter 协议 `uk-dataset-v1-train-fit-v1`：对计数列 log1p，随后用**仅训练集**
拟合的中位数填补与均值/标准差标准化。

## 实验设计

三臂为累积消融，除架构外所有设置一致：

| 臂 | 模型 | 社区先验 |
| --- | --- | --- |
| `comrisk` | `RiskGNN` 基座 + `Classifier` | 关 |
| `riskgnn` | `RiskGNN` 基座 + `Classifier` | 开（SIC section 贝叶斯平滑先验） |
| `plus` | `RiskGNNPlus`（节点/图证据头 + DST 融合 + 主分类头），`EvidentialRiskLoss` | 开 |

- UK 无跨 split 稳定的超边名，社区先验按节点 `community` 字段（SIC section）分组；
  训练行用 leave-one-out 特征，验证/校准/测试用组先验并对未见组回退全局均值。
- 类别不平衡用加权损失处理：`--class-weight auto`（默认）对基线用带权 NLL，对
  `plus` 让 `EvidentialRiskLoss` 按真实类加权（`class_weights` 之前声明但未使用，本次
  修复；默认 `None` 不改变 SMEsD 行为）。
- 训练：种子 14/42/2026，250 epoch，Adam lr=0.01，cosine，梯度裁剪 0.25，
  每 5 epoch 按验证集 ROC-AUC 选最优权重。
- 校准集从 valid 折半（`RandomState(42)`），保形 ε=0.05、β=0.2，阈值取
  `ceil((n+1)(1-ε))` 顺序统计量，与 `triage-comparison.md` 一致。
- 报告测试集 ROC-AUC / PR-AUC / ECE / Brier，并对 `plus` 输出冲突分层与保形审计。

### 与 SMEsD 的分流对照差异

- SMEsD 用 `meta_emb.pkl` 预训练嵌入；UK 用随机投影，故只能比较**同一数据集内**的相对差异。
- `run_smesd_experiments.py` 的 “RiskGNN+” 是分类器 + 熵替代，本文的 `plus` 是真实证据模型；
  两者结果不应互相引用。
- UK 混权关系（`SAME_ADDRESS` 非均匀、其余均匀）要求 `HeteGNN.message` 按
  `use_scalar_weights` 标志分支；`comrisk_base` 快照已补上该上游修复（见其 `__init__.py`）。

## 运行

```bash
cd <repo root>
# 冒烟（小图、少 epoch）
python models/riskgnn+/run_uk_experiments.py \
  --output models/runs/uk-smoke-<date> --max-nodes 3000 --epochs 5 --seeds 42

# 完整三种子
python models/riskgnn+/run_uk_experiments.py \
  --output models/runs/uk-comparison-<date>
```

常用开关：`--edge-weights uniform`（权重均匀化敏感性分析）、`--class-weight uniform`、
`--no-standardize`、`--max-nodes`、`--epochs`、`--seeds`、`--threads`。

## 输出

```
<output>/
  manifest.json          # 数据/协议/源码哈希/环境
  source_snapshot/       # 当次运行用到的全部 .py
  seed_<s>/
    <arm>_checkpoint.pt
    predictions.npz      # 各臂 cal/test 概率，plus 的不确定性/冲突/节点/图概率
    training.json        # 最优 epoch、验证 AUC、cal/test 指标
  summary.json           # 三种子 test 指标与保形审计
  results.md             # 对照表
  COMPLETE
```

只在 `summary.json` 与 `results.md` 中汇总，原始预测保留在 `seed_*` 下，便于复核与重放。
输出目录不可复用，避免覆盖既有运行。

## 测试

```bash
cd <repo root>
python -m pytest models/riskgnn+/tests -k uk
```

`uk_benchmark.data` 不依赖 torch，仅验证加载契约（全局索引、split 划分、边映射、
超边分型、预处理、`--max-nodes` 过滤）。
