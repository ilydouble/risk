# 新加坡数据与训练协议

## sg-comrisk-v1

直接接收 comrisk_export ZIP，支持文件位于根目录或统一顶层目录。
压缩包不超过 512 MiB，解压总量不超过 2 GiB，成员最多 128 个；拒绝路径穿越、重复文件、
符号链接和加密成员。Parquet 分批读取；原始业务行不导入 PostgreSQL。

必需文件：company_attr.parquet、edges.parquet、label.parquet、id_map.parquet、
splits_5seed.parquet、feature_config.json、export_meta.json。
ID 映射使用 company_id_str / company_id_int；特征协议为 2.0 的 A_no_priors。
扫描包内所有 Parquet row group，校验企业唯一性、行序索引、边端点、标签掩码与五组冻结划分，
记录每个文件长度、SHA-256 和完整统计。其余脚本与说明保留为附件，不执行。
校验后的 ZIP 按内容指纹另存到 datasets 前缀，后续任务只读取这一固定副本。
本轮只用自带 edges.parquet，不混入 singapore_graph_data，不自动重建图或使用超边分支。

## sg-node-edge-train-fit-v1 / smoke-v1

固定六特征：由适配器的 FEATURES 常量约束，必须与 A_no_priors 的声明一致。
不使用标签来源、企业年龄、社区风险先验或其他列。
缺失计数字段补 0；address_trust 的缺失填充值仅在训练划分拟合并保存。
不把修改后的预处理结果声称为历史实验分数复现。

- 使用 seed 0 的冻结划分，保留 train / val / test 身份。
- 按原 split 和标签比例，稳定 SHA-256 排序选 2,000 个有标签目标。
- 加入最多两跳、每节点四个邻居的确定性上下文；保存实际 ID、关系与划分。
- 关系按研究 node_edge 入口双向化、单位权重；固定嵌入作为模型 buffer 保存。
- 默认两轮、batch size 64、五层 fanout 2、一个采样进程、CPU 两线程。
- 验证集损失选择检查点；测试集只在新进程独立加载后计算最终指标。
- 预测使用逐目标确定性邻域，输入顺序和同批其他企业不改变结果。

输出 ROC-AUC、PR-AUC、KS、Brier、Precision、Recall、F1、混淆矩阵及逐企业预测。
0.5 是固定分类阈值，不基于测试集优化。少量正样本会使指标波动，不能用于生产授信决策。
新加坡标签描述企业困境状态，静态图实验不等于严格的未来违约预测。

网络前向、邻居采样及优化步骤复用原 gnn.py / train_sg_neighbor.py；服务只固定
本节实验协议和产物格式。原研究入口保留全量、GPU 与消融参数。

## 数据分析

新加坡质量指标扫描全部企业，PSI 使用 seed 0 中 train/val/test 各最多 5,000 行，
按企业 ID 的 SHA-256 稳定抽样；抽样数随报告返回，分析不改变训练划分。
Bundle v1 按原声明的 train/validation/test 分析；信号与相关性只在训练划分计算。
样本、边、时间和摘要校验复用旧工作台契约；不恢复旧的 GNN 网络实现。
node-only 配置将模型包中的训练图置为空，保留原图规模与实际使用规模的区别。
