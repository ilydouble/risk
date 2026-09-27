# 元数据驱动风险建模工作台

`/modeling` 是用户数据的真实离线实验链路，与产品演示评分和 `/benchmark` SMEsD
公开基准互相隔离。它不发布模型、不接生产授信，也不会把企业经营风险称为贷款违约概率。

## 输入契约

系统只接收 ZIP Bundle v1，不提供字段映射。外部适配脚本负责把原始申请、还款、征信、
工商及关系数据转换为：

```text
metadata.json                 必需
samples.csv|parquet           必需
nodes.csv|parquet             可选
relations.csv|parquet         可选
events.csv|parquet            可选
hyperedges.csv|parquet        可选
```

`samples` 是唯一训练入口，一行是一笔贷款申请或一个企业观察时点。每行固定包含
`sample_id`、`entity_id`、`observation_time`、`graph_snapshot_id`、`split`、`target`，
其余训练字段必须在 metadata 中声明类型和 `application`、`bureau`、`financial`、
`registry` 等特征组。metadata 同时声明任务语义、正类、预测窗口、文件大小与 SHA-256。

图组件使用外部生成的 `graph_snapshot_id`。Worker 校验节点与端点引用、样本实体和事件时间；
没有合法图快照时只允许表格模型。静态实验图会显示“不支持严格未来预测”的提示。

## 异步数据流

```mermaid
sequenceDiagram
  participant UI as 四阶段工作台
  participant API as FastAPI
  participant PG as PostgreSQL
  participant S3 as RustFS
  participant W as 本地 Worker
  UI->>API: 创建 ZIP 上传票据
  UI->>S3: 预签名 PUT
  UI->>API: 确认上传
  API->>PG: queued analyze_bundle
  W->>PG: SKIP LOCKED 领取任务
  W->>S3: 下载并安全校验 Bundle
  W->>PG: 写入聚合画像，dataset=ready
  UI->>API: 创建比较实验
  API->>PG: queued train_experiment
  W->>S3: 读取 Bundle、写入模型制品 ZIP
  W->>PG: 写入变体指标，experiment=completed
  UI->>API: 轮询进度和结果
```

PostgreSQL只保存清单、聚合画像、状态与指标；不保存或返回客户原始行。ZIP 校验拒绝路径穿越、
符号链接、加密包、重复文件、哈希错误及超限压缩。任务采用租约，过期可恢复，最多执行三次。

## 分析、RiskGNN 与评估基线

分析阶段输出字段质量、标签/划分分布、单变量信号、相关性、PSI、泄漏提示，以及图节点、关系、
度、孤立样本、连通分量和超边画像。推荐特征只在 train 划分计算；填补、缩放、类别词表和选择
规则随实验制品保存。

正式模型只有 RiskGNN。数据包编码层把动态样本/节点/事件字段投影为节点表示，随后统一调用
`com_risk_runtime.RiskGNNCore` 完成关系内/关系间注意力、超图拉普拉斯传播以及自身风险与传染
风险门控融合。训练界面提供三种方案：标准训练、附带HGB基线、完整消融。

RiskGNN内部配置为：

1. `gnn_self_only`：仅自身属性和事件，用于内部消融；
2. `gnn_no_hyper`：增加门控异构关系传播；
3. `gnn_full`：增加可学习超边传播。

`logistic_regression`、`hist_gradient_boosting` 和 `graph_stats_hgb` 仍可在对照/消融方案中运行，
但被标记为评估基线，不属于模型家族，不自动发布，也不与 RiskGNN 共同组成集成模型。

RiskGNN 使用事件类别 Embedding、数值投影、时间衰减、关系类型和正边权，按验证集 BCE 早停。
所有变体报告 ROC-AUC、PR-AUC、KS、Brier、Precision、Recall、F1、混淆矩阵和校准分箱。
制品保存在 RustFS，`manifest.json` 对每个模型文件记录大小和 SHA-256，`autoPublished=false`。
每次实验另生成一份稳定的训练配置档案，明确数据指纹、编码、图、训练与评估协议，以及不同
数据集之间不迁移权重的边界，详见[数据集训练配置档案](training-profile.md)。

## 本地命令

模型工程内生成两种可验收样例：

```bash
cd com_risk_model
uv run python -m workbench.demo --output runs/loan.zip --task loan_application --with-graph
uv run python -m workbench.demo --output runs/entity.zip --task entity_snapshot --with-graph
uv run python -m workbench.worker          # 连续领取任务
uv run python -m workbench.worker --once   # 最多领取一个任务
```

完整开发拓扑、环境变量和端到端步骤见[本地开发](local-development.md)，领域口径见
[建模领域模型](modeling-domain.md)。
