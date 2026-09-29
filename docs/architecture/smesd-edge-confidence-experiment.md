# SMEsD 边置信度受控实验

## 目的与结论边界

本实验只回答一个机制问题：当候选关系中混入假边，显式的边存在置信度能否提高模型鲁棒性。它不证明 SMEsD 原始边具有真实置信度，也不替代新加坡 V5 的真实数据实验。

原始 `datasets/smesd` 和 `models/baseline` 保持只读。仿真数据、训练日志和模型制品写入独立实验目录。关系强度 `strength` 与存在置信度 `confidence` 是两个变量；前者沿用 SMEsD 原值，后者仅由仿真协议生成。

## 数据生成协议

- 只使用模型实际消费的 0–11 类关系，固定反向对为 `0↔1`、`2↔3`、`4↔5`、`6↔7`、`8↔9`、`10↔11`。
- 以一对正反向边为一个逻辑关系；训练、验证、测试分别独立生成候选关系。
- 假边在同一关系类型内，从真实源端和目标端的经验分布独立重连；拒绝原边、重复边、自环和非法端点。
- 噪声率定义为 `假逻辑关系数 / 原始真逻辑关系数`。
- 假边的关系强度从同类真实边经验分布采样，不用强度暗示真假。
- 置信度档为 0.05、0.20、0.50、0.80；每档混入相应数量真边，使经验真边率接近标称值。未分配的真边置信度为 1.0。
- 标签不参与候选边生成、置信度分配或过滤。生成清单记录协议版本、输入文件哈希、场景文件哈希、边数和经验校准。

## 对照组

| 变体 | 图 | 社区先验 | 置信度处理 | 回答的问题 |
|---|---|---:|---|---|
| `comrisk_oracle` | 仅真边 | 否 | 忽略 | 干净图上限与原版式基准 |
| `comrisk_noisy` | 全部候选边 | 否 | 忽略 | 原版式模型受假边影响程度 |
| `riskgnn_noisy` | 全部候选边 | 是 | 忽略 | 仅加 RiskGNN 社区先验是否足够 |
| `riskgnn_filter` | 置信度≥0.5 | 是 | 过滤后忽略 | 硬阈值方案 |
| `riskgnn_gated` | 全部候选边 | 是 | softmax 后门控 | 主方法 |
| `riskgnn_shuffled` | 全部候选边 | 是 | 关系内打乱 | 收益是否来自正确排序 |
| `riskgnn_inverted` | 全部候选边 | 是 | 反转 | 错误置信度的风险 |

门控发生在每一类关系内部 attention/强度归一化之后：`message = normalized_message × confidence`。因此 confidence 不会被 softmax 再归一化掉。

`comrisk_*` 使用与原始 ComRisk 相同的输入宽度、无社区先验配置和原始 SMEsD 图/超图算子；正式运行前必须在共同 PyG 环境验证参数键、初始化和全 1 置信度输出与原始实现一致。

## 训练与评估

- CPU 共同环境、Adam、学习率 0.01、CosineAnnealingLR、梯度裁剪 0.25，与上一轮同环境比较一致。
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
  --noise-ratios 0.4 --seeds 14 --epochs 500
```

每个组合独立保存 `train.log`、`metrics.json`、`predictions.npz` 和 `model.pt`；根目录持续刷新 `summary.json` 与 `summary.csv`。同一目录再次运行会跳过完整组合；协议配置或源码哈希变化时拒绝混合结果。

多个矩阵完成后，可按同 seed 汇总均值、标准差、配对差值与 bootstrap 95% 区间：

```bash
python models/riskgnn+/summarize_uncertainty_results.py \
  --work-dirs artifacts/uncertainty-reference artifacts/uncertainty-main \
  --output-dir artifacts/uncertainty-analysis
```
