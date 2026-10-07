# CompanyKG 与 ComRisk 的结合评估

核对日期：2026-09-25。已阅读 v1 数据加载器、GraphSAGE 训练/模型、eGraphMAE 模型，及官方 v2 README、Zenodo 发布页。未下载全量图、未运行 CompanyKG 实验，以下为设计建议而非效果结论。

## 结论

适合作为企业表示学习、自监督预训练、相似企业检索模块；不能替代风险监督标签，也不能直接将 CompanyKG 节点拼接到 SMEsD。

## 已核实事实

- 用户指定仓库 https://github.com/EQTPartners/CompanyKG 为 1.x；该仓库指向 https://github.com/llcresearch/CompanyKG2 。本地阅读 v1 提交 e9bf7855c23c0d515d300b2900b33b6155601a01。
- v2 README：约 117 万公司、5106 万加权边、15 类关系。Zenodo 对基础无向图记载 50,815,503 边，与 README 统计口径不同；实际实现以文件 shape 和版本为准。
- 节点特征为企业描述文本 embedding，提供 msbert、simcse、ada2、pause。
- 任务：SP 相似预测、SR 相似排序、CR 竞争对手检索；v2 增加 EP 边预测。没有提供与这些任务等价的破产/违约标签。
- 公开文件目录没有企业注册号/名称映射表；loader 的 nodes_id 为 0..N-1。未找到与 SMEsD 或美国匿名财务数据的可用实体对齐键，不能假定可直接关联。
- benchmarks 提供 GraphSAGE、GRACE、MVGRL、GraphMAE、eGraphMAE。
- v1 GraphSAGE 用邻居采样、边正负样本和 BCE 训练；eGraphMAE 用包含边特征的 EGAT 编码器与遮蔽节点属性重建损失。
- v1 `to_pyg()` 仅返回 x 和双向 edge_index，未传递 edges_weight。加载边权路径会 `.to_dense()`，全量加载内存需要单独估算。
- 代码 LICENSE 为 MIT；数据在 Zenodo 另有 LICENSE.txt。本轮该文件获取失败，尚未核实数据条款，不能用代码许可替代。
- v2 文件总量约 15.3GB（含全部向量版本）；edges 813MB + edges_weight 约 1GB + PAUSE 299.5MB，选一个较小向量版本的原始文件也约 2.1GB，训练内存明显高于文件大小。

## 最适合当前项目的分阶段方案

### A. 先迁移训练方法，不拼接数据（优先）

在 SMEsD 的训练期图上增加自监督目标：遮蔽属性重建或关系类型感知的链路预测，然后使用同一编码器及输入 schema 微调破产分类器。训练期自监督数据仍需遵守观察时间；未来图边也会泄漏。

对照：现有 ComRisk-inspired 基线 vs 加入同域预训练的同架构模型。相同 split、特征和训练预算，多随机种子评估 ROC-AUC、PR-AUC、KS、Brier。仅有相似度提升不代表风险预测提升。

### B. 外部 CompanyKG 预训练（有条件）

单独保留语义编码分支，在 CompanyKG 子图预训练，再迁移共享编码器；需要目标企业使用同一文本 embedding 模型/预处理、相容的关系语义、特征维度适配及无未来信息的版本。

当前 SMEsD 主要是资本/企业年龄/诉讼输入，与 CompanyKG 文本向量不同。输入投影改变后不能简单 load_state_dict；不同关系编号也没有共同含义。仅迁移参数是一项需要验证的实验，不是现成数据补全手段。

### C. 产品能力扩展

公司描述 → 语义/关系编码 → 相似公司 Top-K，可服务同业对照与候选关联发现。风控评分另用财务/诉讼/真实关系和风险标签。相似关系不能作为股权、担保或供应链传染关系的事实证据；检索结果也不是风险标签。

## 代码落点（尚未实现）

- `com_risk_model/runtime/src/com_risk_runtime/model.py`：提取可复用 encode 接口，保留 self/graph/hyper 三分支；可选语义分支需显式缺失 mask。
- 新增预训练模块：train-only 属性 mask 或 typed link prediction，正确排除正边/反向边以避免负采样与链路泄漏。
- 数据适配器：保留多维关系权重，不能简单 argmax 成单关系；为图采样创建专门张量数据路径，避免百万节点 JSON/全图训练。
- 预训练与风险指标分开记录，不使用 CompanyKG 的相似标签训练 bankruptcy head。

## 来源

- https://github.com/EQTPartners/CompanyKG
- https://github.com/EQTPartners/CompanyKG/blob/main/src/companykg/kg.py
- https://github.com/EQTPartners/CompanyKG/tree/main/benchmarks/src/ckg_benchmarks
- https://github.com/llcresearch/CompanyKG2
- https://zenodo.org/records/11391315
