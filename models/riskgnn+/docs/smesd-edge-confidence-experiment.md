# SMEsD 边置信度受控实验

## 目的与结论边界

本实验只回答一个机制问题：当候选关系中混入假边，显式的边存在置信度能否提高模型鲁棒性。它不证明 SMEsD 原始边具有真实置信度，也不替代新加坡 V5 的真实数据实验。

原始 `datasets/smesd` 和 `models/baseline` 保持只读。仿真数据、训练日志和模型制品写入独立实验目录。关系强度 `strength` 与存在置信度 `confidence` 是两个变量；原始真边保留 SMEsD 强度，新增假边使用中性强度1，置信度仅由仿真协议生成。

## 数据生成协议

- 只使用模型实际消费的 0–11 类关系，固定反向对为 `0↔1`、`2↔3`、`4↔5`、`6↔7`、`8↔9`、`10↔11`。
- 以一对正反向边为一个逻辑关系；训练、验证、测试分别独立生成候选关系。
- 假边在同一关系类型内，从真实源端和目标端的经验分布独立重连；拒绝原边、重复边、自环和非法端点。
- 噪声率0.40定义为新增假关系数/原真关系数：保留全部真边，再额外新增约40%假边，不模拟删边。
- 原真边均为`q=1.0`。新增假边的`strength=1.0`，每条假边的置信度独立服从`Uniform(0.05, 0.20)`。不为假边伪造金额型关系强度。
- 标签不参与候选边生成、置信度分配或过滤。生成清单记录协议版本、输入文件哈希、场景文件哈希、两类扰动边数和置信度组成。

## 对照组

| 变体 | 图 | 社区先验 | 置信度处理 | 回答的问题 |
|---|---|---:|---|---|
| `comrisk_oracle` | 仅真边 | 否 | 忽略 | 干净图上限与原版式基准 |
| `comrisk_noisy` | 全部候选边 | 否 | 忽略 | 原版式模型受假边影响程度 |
| `riskgnn_noisy` | 全部候选边 | 是 | 忽略 | 仅加 RiskGNN 社区先验是否足够 |
| `riskgnn_filter` | 置信度≥0.5 | 是 | 过滤后忽略 | 硬阈值方案 |
| `riskgnn_embed` | 全部候选边 | 是 | 仅embedding加权 | 隔离预训练贡献 |
| `riskgnn_gated` | 全部候选边 | 是 | embedding加权+softmax后门控 | 主方法 |
| `riskgnn_shuffled` | 全部候选边 | 是 | 关系内打乱 | 收益是否来自正确排序 |
| `riskgnn_inverted` | 全部候选边 | 是 | 反转 | 错误置信度的风险 |

门控发生在每一类关系内部 attention/强度归一化之后。五层传播每层默认使用 `confidence^(1/5)`，避免把同一置信度完整重复相乘五次；旧版每层完整乘 confidence 的pilot作为独立历史消融保留。

`comrisk_*` 使用与原始 ComRisk 相同的输入宽度、无社区先验配置和原始 SMEsD 图/超图算子；正式运行前必须在共同 PyG 环境验证参数键、初始化和全 1 置信度输出与原始实现一致。

## 场景化图嵌入

- 每个场景先在 GPU 上按固定无监督 epoch 重训 MetaPath2Vec，再冻结嵌入训练下游 GNN；不再沿用与图不匹配的原始 `meta_emb.pkl`。
- ComRisk、`riskgnn_noisy`和filter使用均匀随机游走；当前RiskGNN按 `P(e|v,r) ∝ q_e^alpha` 加权正随机游走，默认 `alpha=1`，负采样不把低q边误当作确定负边。
- `riskgnn_embed`只在embedding使用q；gated在embedding与传播使用q；shuffled/inverted在两个阶段同步使用对应的负对照q。
- 预训练合并 train/valid/test 的无标签拓扑，保持原始实现的转导设定；训练、验证、测试标签均不进入随机游走、loss 或 checkpoint 选择。该结果不能表述为严格时点外推。
- 原脚本的 `> company_count` 边界已修正为 `>= company_count`。新入口只写实验目录，并记录原始数据、场景、源码、图和输出嵌入哈希，拒绝覆盖 `datasets/smesd/meta_emb.pkl`。
- 固定最终无监督 epoch 作为嵌入 checkpoint，不再使用原脚本的验证标签准确率选择嵌入。

## 训练与评估

- 共同 CUDA 环境、同一 GPU、Adam、学习率 0.01、CosineAnnealingLR、梯度裁剪 0.25；CPU 固定嵌入结果只保留为历史实验 A，不与 GPU 端到端实验 B 混合汇总。
- 所有成对变体使用相同仿真 seed、训练 seed、初始化顺序、划分和 epoch 数。
- 按验证集 ROC-AUC 选 checkpoint；并列时取验证损失更低者。测试集不参与选模或阈值选择。
- 分类阈值只在验证集按最大 F1 选择，然后固定用于测试集。
- 主报告：ROC-AUC、PR-AUC、Brier；辅助报告：Accuracy、Precision、Recall、F1。
- 先导实验固定噪声率 0.40、仿真/训练 seed 14。正式矩阵候选为噪声率 0、0.20、0.40、0.60、0.80，五个配对 seed 14、42、2026、3407、9991，每组 500 epochs。

主假设是：噪声率大于 0 时，`riskgnn_gated` 相对 `riskgnn_noisy` 和 `comrisk_noisy` 提高测试 ROC-AUC/PR-AUC并降低 Brier；`riskgnn_shuffled` 的收益应显著减弱，`riskgnn_inverted` 应恶化。结果按同 seed 配对差值、均值、标准差和 bootstrap 置信区间汇总，不只比较单次最好结果。

## 运行入口

生成单个场景：

```bash
python models/riskgnn+/simulate_smesd_uncertainty.py \
  --data-dir datasets/smesd --output-dir artifacts/scenario \
  --noise-ratio 0.4 --seed 14
```

运行可恢复矩阵：

```bash
python models/riskgnn+/run_uncertainty_matrix.py \
  --data-dir datasets/smesd --work-dir artifacts/uncertainty-pilot \
  --noise-ratios 0.4 --seeds 14 --embedding-epochs 20 --epochs 500 \
  --retrain-embeddings --embedding-confidence-alpha 1 \
  --confidence-gate-exponent 0.2 --device cuda --hyper-impl scipy
```

每种图拓扑独立保存 `meta_emb.pkl`、`metapath2vec.pt`、`pretrain.log` 和嵌入清单；每个下游组合保存 `train.log`、`metrics.json`、`predictions.npz` 和 `model.pt`。根目录持续刷新 `summary.json` 与 `summary.csv`。同一目录再次运行会跳过完整组合；协议配置或源码哈希变化时拒绝混合结果。

多个矩阵完成后，可按同 seed 汇总均值、标准差、配对差值与 bootstrap 95% 区间：

```bash
python models/riskgnn+/summarize_uncertainty_results.py \
  --work-dirs artifacts/uncertainty-reference artifacts/uncertainty-main \
  --output-dir artifacts/uncertainty-analysis
```
