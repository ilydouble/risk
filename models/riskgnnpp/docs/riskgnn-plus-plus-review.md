# RiskGNN++：论文整理与核验报告

日期：2026-10-13。主稿：[RiskGNN++](riskgnn_plus_plus_paper.md)。

[原稿完整存档](archive/riskgnn-plus-plus-original-20261013.md)保留原文，仅清理行尾空白，便于比较及恢复；
该存档沿用原稿长度，正文、实验补充和核验报告分别控制在 200 行以内。

## 1. 本轮定位与范围

最新实现位于独立目录 `models/riskgnnpp/`，模型包为 `riskgnn_pp/`：

- `model.py`：关系证据头、冲突/度数折扣、多源融合、度数证据预算。
- `fusion.py`：主观逻辑映射、两两冲突、折扣与逐源融合。
- `conformal_triage.py`：新增的 RiskGNN++ V2 / TACR，最后修改于 2026-10-13 01:57。
- `evaluate_conformal_comparison.py`：概率 CP / 证据 CP / TACR 对照入口，最后修改于 01:58。
- `riskgnn_benchmark/training.py`：共享训练入口，`run_benchmark.py` 为启动脚本。

目录拆分前，`model.py` 对 UK/SMEsD 训练快照的唯一区别是新增一行 TACR 导入；前向算法相同。
拆分前 `fusion.py` 和训练入口的 SHA-256 与两组 manifest 一致。
独立目录整理后清理了未使用导入并统一格式，训练入口新增跨目录源码快照收集；
历史制品保持原样，当前源码哈希以新运行记录为准。
最新 TACR 尚未包含于训练源码快照，故本轮将其作为保存预测上的后处理复放。
原始模型、训练脚本、检查点和预测均未修改。

## 2. 已整理的内容

- 标题、摘要和贡献围绕“关系证据融合 + 冲突引导分流”，删除稿件状态中的已投稿暗示。
- 分离分类质量、同模型固定预算排序、保形预测集三个问题。
- 根据实现补齐自节点池化、超图分支、辅助 graph head、冲突组合方式和损失权重。
- 区分折扣系数 `gamma_d` 与保形系数 `gamma_c`，避免同符号表示不同超参数。
- 度数预算明确用于训练和推理，均值是当前 forward 的节点度数均值。
- PR-AUC 注明实际为 AP；相对百分比与绝对百分点分开。
- 保留主性能表数值，新增分流标准差；补充 SMEsD 的负面校准结果。
- 图依赖保证、传染因果机制及领先性结论改列为待证主张，保留在下表供作者补证。
- 原 ASCII 曲线把不同预算数值画成平线，容易误读；以带预算的数值表替代。

## 3. 原稿主张与待证事项

下表记录原稿主张，避免把尚未验证的研究想法静默丢失。
`[PENDING VERIFICATION]` 表示本轮没有足够证据，不表示主张必然错误。

| 原稿主张或数值 | 本轮核验 | 稿件处理 / 补证要求 |
| --- | --- | --- |
| “distribution-free coverage” under non-exchangeable graphs | 代码只是修改 score 后取标准分位数 | 条件性说明；需可交换性论证或新的依赖定理 |
| “Graph Bernstein / dyadic bound”、PAC risk guarantee | docstring 声称存在，实际无对应实现；`max_degree` 未用 | [PENDING VERIFICATION] 补定理、假设和实现 |
| “first provably reliable”、state-of-the-art | 未提供证明或全面基线检索 | [PENDING VERIFICATION] 先不作已证贡献 |
| “edge confidence collapse” due to projection absorption | 86.06/86.07 不足以证明不可识别或普遍吸收 | [PENDING VERIFICATION] 单独控制传播层数、权重和归一化 |
| 高度节点导致证据无穷大、u 趋零 | 数学关系成立，实际训练的因果链未证 | 将 Evidential Inflation Trap 保留为待验证机制 |
| conflict 是 pristine/uncorrupted contagion detector | 只观察到模型错误关联，heterophily 相关较弱 | 使用“分歧/错误集中信号” |
| 14.2–82.1× 错误集中 | 与 UK summary 的 ++ composite conflict 一致 | 保留，但不能配旧二分支冲突公式解释 |
| 21.93% EDL / 5.00% Softmax at 50% | 对应 **plus**，不是 ++ | 模型归属在补充文档中明确 |
| TACR 30% 预算 7.36%，比 Softmax 少 1.04pp | 固定 0.6 系数在 plus 上得 7.44%，++ 上得 6.85% | [PENDING VERIFICATION] 原列参数与来源；新表用可复放 ++ 数值 |
| UK CP coverage 93.88% / 94.97% | 与原 summary 的 94.05% / 94.78% 不符 | 使用明确协议的新复放，旧值待追溯 |
| SMEsD 95.38% “Guaranteed” | 数值为 evidence CP；TACR 为 95.45% | 保留数值来源，去掉保证标签 |
| SMEsD 消融 coverage 94.20% / 94.45% | summary 未保存消融 audits | [PENDING VERIFICATION] 补消融预测重放 |
| “phase transition”、homophily、shell-company explanation | 没有同配率、相变检验或壳公司真值 | 列为机制假设，不能由两数据集反推 |
| “industry-standard 20–40%”、防止数千笔错误 | 无行业或业务成本依据 | [PENDING VERIFICATION] 补来源和外推假设 |
| Graph / HGNN 已替代评分卡，EDL 已成标准范式 | 无系统性证据 | [PENDING VERIFICATION] 不作为摘要前提 |
| 社区先验只用训练标签 | 代码支持，训练采用 leave-one-out | 明确描述，不承诺发布划分本身无重叠 |
| 企业状态标签即贷款违约、图为供应链 | manifest 不足以验证此等价关系 | [PENDING VERIFICATION] 数据字典、预测期限、关系语义 |

此外，`docs/给老师_论文复核.md` 中“基准率跨过 50% 必然导致冲突与违约关联翻转”
是机制推测，两个数据集不足以证明该阈值规律；本轮未修改该文件，也未将其写入 ++ 的结论。

## 4. 参考文献核对

已纠正 TMC（ICLR 2021，而非 NeurIPS）、Jürgens 等（ICML 2024，而非 NeurIPS）、
Graph CP（ICML 2023，完整题名为 *Conformal Prediction Sets for Graph Neural Networks*）。
Bengs 的原稿条目“Pitfalls of Evidential Deep Learning”改为可追溯的 2022 预印本题名。
对应论文链接列在主稿 References。

[PENDING VERIFICATION] ComRisk 和 RiskGNN 的准确原始文献、实现版本与复现差异；
原稿 ComRisk 的作者/题名/会议组合暂未核实，不补造引用。
[PENDING VERIFICATION] TEF、HeteGNN 等补充相关工作、研究新颖性和完整文献覆盖。
这轮是稿件与实现一致性复核，未进行系统综述。

## 5. 写作检查记录

采用一般学术标准，未指定期刊。以下是编辑自评，不是投稿质量认证。

| 维度（1–5） | 原稿 | 整理后 | 主要变化 |
| --- | ---: | ---: | --- |
| 语法与句法 | 4 | 4 | 保留可读表达，减少口语与混杂强调 |
| 学术语气 | 2 | 4 | 区分相关、假设、证明，弱化宣传措辞 |
| 连贯性 | 2 | 4 | 按任务拆开三类证据链 |
| 简洁性 | 2 | 4 | 去掉重复贡献和失真示意图 |
| 术语 | 2 | 4 | AP、CP、TACR、primary/fused、冲突定义统一 |
| 结构与格式 | 2 | 4 | 表格顺序、交叉链接、方法与实验补充分开 |
| 论证清晰度 | 1 | 4 | 明确模型归属与未证机制；结论限定在实测范围 |
| 投稿规范 | 1 | 2 | 尚缺目标模板、完整引用、作者声明和数据声明 |

本轮未以检测器分数为目标，也未声称改变任何 AI 检测结果。

## 6. 后续优先级

1. **优先锁定实验协议**：明确正类、预测时间点、去重敏感性、先验和类权重；固定 score 参数。
2. **补 UK 组件消融**：当前 UK 只有四模型主对照，尚不能分解折扣与度数预算作用。
3. **验证机制**：按度数与类别检查 evidence strength，比较有无类权重和共享图表示。
4. **补评价边界**：概率校准基线、逐 seed 配对改善、错误放行/拒绝、图依赖不确定性。
5. **最后做投稿排版**：确定会议/期刊后再转 LaTeX、补图、补 BibTeX 和声明。
