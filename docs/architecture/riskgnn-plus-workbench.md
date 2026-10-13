# RiskGNN+ 工作台接入

## 当前模型

默认工作台算法为 RiskGNN+，复用 `models/riskgnn+/riskgnn_plus/model.py` 与
`EvidentialRiskLoss`，不是重命名旧 node_edge，也不使用缺少超图的 forward_batch。
模型侧集成代码在 `riskgnn_plus/workbench/`；原 ComRisk / RiskGNN / + / ++ 研究入口保留。

通用运行器 ID 仍为 riskgnn，表示既有执行入口；runtime_version 升为 3，
执行 contract_version 仍为 2。默认配置显式冻结 algorithm=riskgnn-plus。
页面按真实 algorithm 展示名称，历史 RiskGNN 记录不会改名。

## 输入与超图

适配器继续负责字段映射、标签、原划分和训练集拟合的预处理。
Plus 准备层在已有目标与两跳普通图上下文上生成诱导超图和事件输入：

| 数据 | 超图 | 事件 |
| --- | --- | --- |
| SMEsD JSON | industry / area / qualify | cause / court / result / age_months |
| UK JSON | sic_section / postcode_area / director_group | 原数据没有事件，不补造 |
| ACRA | 可选 hypergraph_industry / area / qualify.parquet | 本适配不解释可选风险附件 |

每条超边只保留所选公司成员，不为了凑群组制造节点；人物不加入企业超边。
ACRA 缺可选文件时对应 incidence 为空，并在使用范围中体现；不是声称数据有超图。
采用原 HyperGNNVectorized 的单位超边权重；超边/成员置信度仅保留证据，不解释成校准概率。
普通图沿用适配器的方向与权重策略；显式 edge confidence 不作为本次 Plus 的外部输入。

快照分别完整前向，人物索引保持快照隔离，BatchNorm 训练统计不读取验证/测试快照。
使用 torch.func.functional_call 共享同一组可训练参数和运行统计，各快照只替换图大小与固定输入。
ACRA 沿用静态传导图，既有划分不变。调用结果按目标 ID 返回，批次和顺序不改变预测。

## 训练与资源

- CPU 两线程；默认两轮，允许 1–20 轮，目标数量默认值沿用适配器声明。
- 每轮对准备后的训练图完整前向，普通关系五层、向量化超图、RiskInfo 事件和双证据头均执行。
- EvidentialRiskLoss：分类头 CE + 融合/节点/图证据项 + 退火 KL；类别权重只按训练目标拟合。
- Adam lr=0.01、余弦退火、梯度裁剪 0.25；验证分类头 CE 选检查点，测试集不参与选模。
- 固定企业/人物嵌入使用可重放随机初始化，保存于上下文，不宣称使用研究预训练嵌入。
- 单准备图最多 100,000 节点、500,000 成员关联，超出明确失败并要求降低 target_count。

这是实际 RiskGNN+ 核心在有界诱导子图上的工作台配置，不是全量赛题或论文实验复现。
比赛全量规模、GPU、嵌入预训练与赛方输入输出仍需按正式规范确定，不能用小子集指标代替比赛结果。

## 产物与诊断

新格式 riskgnn-plus-model-v1 包含：

- weights.pt：分类、图/超图、事件编码、双证据头、融合门控和 BatchNorm 状态。
- context.npz：特征、图、划分、快照、固定嵌入与各类型超图成员索引。
- risk_events.json：节点局部映射所需的原始事件编码。
- ids.json、metadata.json、evidence.json（有时）、manifest.json：身份、配置、使用范围及摘要。

独立 evaluate / predict 进程重载，evaluate 不修改模型产物。
源码指纹包含适配器、工作台、Plus 实现及实际使用的 vendor 基座。

主预测 probability 来自 primary_classifier，阈值固定 0.5；另输出：

| 字段 | 含义 |
| --- | --- |
| fusedProbability | DST 融合证据的正类概率 |
| uncertainty | 融合证据不确定性 |
| conflict | 节点与图证据冲突 |
| nodeProbability / graphProbability | 各分支证据概率 |

主分类概率与融合证据概率分开，不互相替代。当前未拟合概率或保形校准，
不输出自动授信/拒贷决定，不声称保形覆盖保证。独立测试报告明确记录 not_fitted。
结果继续通过既有业务 API 存储并关联标准企业数据，前端显示不确定性与冲突。

## 兼容和操作

历史 riskgnn-model-v2 仍可预测/下载，使用旧网络路径；新模型不覆写历史权重。
旧实验配置不能静默重跑为 Plus：需选同一数据集创建新实验，冻结新算法配置。
未携带配置的旧排队任务明确拒绝，不默认冒充新的 Plus 实验。

重新构建 backend、riskgnn、riskgnn-worker、frontend 后，在模型工作台创建新实验。
服务进程只管理 HTTP/传输/执行，不导入 Torch；监督器为子进程加入受信任的 riskgnn+ 包路径。
本地直接调用时，从 models/ 设置 PYTHONPATH=riskgnn+，使用 runtime_version=3。
新模型仍绑定训练图；任意新企业/新图推理和正式比赛容器入口不属于此次接入。
