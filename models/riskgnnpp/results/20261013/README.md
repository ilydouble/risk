# RiskGNN++ 实验结果归档

运行日期：2026-10-13；归档日期：2026-10-14。本次只归档已有文件，未重跑实验。

## 论文使用的十种子分析

| 数据集 | 分析报告 | 机器可读结果 |
| --- | --- | --- |
| UK | [十种子分析](riskgnnpp-uk-20261013/analysis-10seed/analysis.md) | [JSON](riskgnnpp-uk-20261013/analysis-10seed/analysis.json) |
| SMEsD | [十种子分析](riskgnnpp-smesd-20261013/analysis-10seed/analysis.md) | [JSON](riskgnnpp-smesd-20261013/analysis-10seed/analysis.json) |

每个数据集的原始运行含 14、42、2026 三个种子；`-ext` 运行补充 7、21、77、101、314、555、888。
`analysis-10seed` 合并两批运行，不能把单个目录的 `summary.json` 当作十种子汇总。
`analysis` 是较早的三种子分析，保留用于追溯。

## 保存范围

四组运行均保留 `manifest.json`、`summary.json`、`results.md`、`COMPLETE`，
以及逐种子 `training.json`；已有的 `analysis` 和 `analysis-10seed` 报告也一并保存。
[归档清单](archive-manifest.json)记录每个文件的来源、字节数与 SHA-256，内容按字节原样复制。
配置中的本地路径和历史版本哈希保留其原始含义；运行时路径仍指向本地 `models/runs/`。

模型权重、逐企业预测数组、原始数据集和运行时源码快照不包含在本次 Git 归档中。
本归档支持核对报告与配置，不是可独立重放全部分析的完整训练制品包。
重放仍需本地预测数组，见[实验补充](../../docs/riskgnn-plus-plus-experiments.md)。

## 解释边界

[当前实证稿](../../docs/riskgnn_plus_plus_paper.md)区分原始 AP、校准后 AP、复核排序与共形集合覆盖。
报告中的历史字段名与表述保持原样；`tacr` 排序字段不等于共形 TACR 评分。
[假设性论文](../../docs/riskgnnpp-paper-hypothetical.md)中的待证结论不是本归档的实验结果。

本次同时保存的[早期给老师复核文档](../../../../docs/给老师_论文复核.md)为 2026-10-12 的历史讨论，
其中关于基准率跨越 50% 导致方向翻转等机制陈述尚未确立，应结合后续[核验报告](../../docs/riskgnn-plus-plus-review.md)阅读。
