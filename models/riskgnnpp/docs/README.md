# RiskGNN++ 研究文档

| 材料 | 入口 |
| --- | --- |
| 假设性论证版本（含三张插图） | [When to Trust Relational Evidence](riskgnnpp-paper-hypothetical.md) |
| 插图、矢量文件与再生成说明 | [论文插图](figures/README.md) |
| 当前英文论文工作稿 | [RiskGNN++ 论文](riskgnn_plus_plus_paper.md) |
| 数据、协议、消融与复现命令 | [实验补充](riskgnn-plus-plus-experiments.md) |
| 实现一致性、引用和待证事项 | [中文核验报告](riskgnn-plus-plus-review.md) |
| 逐 seed 复放指标与输入哈希 | [复放结果 JSON](riskgnn-plus-plus-replay.json) |
| 整理前原稿 | [原稿存档](archive/riskgnn-plus-plus-original-20261013.md) |

实现位于 `../riskgnn_pp/`：`model.py`、`fusion.py`、`conformal_triage.py`。
保存预测复放入口为 [replay_paper.py](../replay_paper.py)，训练制品保留在 `models/runs/`。
RiskGNN+ 的历史论文和实验见[其文档索引](../../riskgnn+/docs/README.md)。
