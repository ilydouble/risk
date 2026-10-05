# 模型工程研究文档

本目录保存模型工程的历史调研记录、实验汇总和来源清单，与 [`docs/architecture/`](../../docs/architecture/)
的系统架构文档分开维护。模型从 0 开始的环境、命令和契约见[模型工程说明](../README.md)。

| 文档 | 内容 |
| --- | --- |
| [demo-bundle.md](demo-bundle.md) | SMEsD 来源、转换去重、字节保留迁移与历史清单 |
| [first-run-results.md](first-run-results.md) | 公开 SMEsD 上第一版各消融配置的实测结果 |
| [datasets.md](datasets.md) | 候选数据集调研、SMEsD 本地文件与上游划分说明 |
| [competition-v1.md](competition-v1.md) | 赛题要求、第一版模型范围与已实现/差异对照 |
| [companykg-integration.md](companykg-integration.md) | CompanyKG 作为表示学习/检索模块的结合评估 |

原样保留的原始记录：

- `smesd-v1-summary.json`：18 次历史实验汇总。
- `legacy-demo-bundle-manifest.json`：合并时的来源与 SHA-256，旧路径仅用于追溯。
