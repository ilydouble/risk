# 数据准备与训练配置

## 边界

数据适配器负责读取、划分、语义校验和预处理；RiskGNN CLI 负责训练与模型产物。
model-service 仅执行操作、监督进程、记录状态/事件、上传产物。
专用字段和接入说明下沉到适配器目录，避免架构文档重复维护。

| 数据集 | 准备配置 | 默认目标上限 | 专用说明 |
| --- | --- | --- | --- |
| ACRA | sg-node-edge-train-fit-v1 / smoke-v1 | 2,000 | [ACRA](../../models/riskgnn/dataset_adapters/acra/README.md) |
| SMEsD V5 JSON | smesd-json-v5-train-fit-v1 | 4,000 | [SMEsD](../../models/riskgnn/dataset_adapters/smesd/README.md) |
| UK v1 | uk-dataset-v1-train-fit-v1 | 2,000 | [UK](../../models/riskgnn/dataset_adapters/uk_dataset_v1/README.md) |

config.target_count 可设 6–20,000；校验始终覆盖整个包，不因子集训练降低校验范围。
不生成合成演示样本，不重划分已有数据；数量不足时保留全部目标。
旧 Bundle 协议、分析和生成器已经移除。

## 模型配置

当前部署一个 RiskGNN，以 node_edge 作为工作台首版配置：

- ACRA 维持双向、单位边权的原配置，便于原结果回归。
- SMEsD / UK 保留方向及原 weight；显式 confidence 独立传入，不从权重猜测。
- SMEsD 人物采用人物投影并保留固定嵌入，仅企业参与监督与预测。
- 两个 JSON 数据集保留 isolated_snapshots；即使人物 ID 重复也不跨快照合并。
- 超图及事件分支未启用；JSON 子集证据保存在 evidence.json，完整数据绑定上传包。
- 实验档案列出 usedInputs、retainedOnlyInputs 和 edgePolicy，页面展示使用范围。

权重、置信度和人物的处理复用 gnn.py；采样复用 train_sg_neighbor.py，
epoch / 优化循环共用 training_engine.py。原研究脚本的命令与默认行为保持兼容。
固定张量及真实 ACRA 子集的改动前后预测用于验证研究入口未漂移。

## 训练与评估

- CPU 两线程，单计算进程；默认两轮，允许 1–20 轮。
- batch size 64，五层 fanout 2；节点准备默认两跳、每个中心四个邻居。
- 验证集损失选择检查点；测试集只在独立进程重载后计算最终报告。
- 当前使用未加权交叉熵、固定阈值 0.5，不通过测试集调阈值。
- 预测为逐目标确定性邻域，输入顺序或同批其他企业不改变结果。
- 报告 ROC-AUC、PR-AUC、KS、Brier、Precision、Recall、F1、混淆矩阵及逐企业预测。

固定子集、类别不平衡和小测试集都会影响指标；本版证明链路可重放，不宣称完整研究复现。
新加坡/英国是登记困境状态，SMEsD 是破产状态；都不自动等同于未来授信违约概率。

## 数据分析与验收

ACRA 质量扫描全部企业，PSI 使用每个划分最多 5,000 行确定性样本。
SMEsD / UK 按公司分析质量、划分和漂移，人物不算监督样本。
校验与准备不执行 ZIP 中脚本，也不在上传阶段加载 Pickle。

```bash
cd models
uv run --project service pytest service/tests --require-datasets -q
```

测试使用本地真实数据或其固定子集，可设 RISK_DATASETS_ROOT。
普通无数据环境明确跳过数据集集成测试；--require-datasets 模式缺文件直接失败。
数据库恢复测试另外需要 RISK_TEST_DATABASE_URL，不影响模型侧独立验收。
