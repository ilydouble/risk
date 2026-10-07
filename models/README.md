# 模型版本

本目录保存彼此隔离的模型实现：

| 目录 | 定位 |
| --- | --- |
| `baseline/` | 上游 ComRisk Git 提交 `a80524b3…` 的原始实现，使用 SMEsD |
| `riskgnn/` | 历史 RiskGNN 百万节点研究实现和邻居采样实验 |
| `riskgnn+/` | SMEsD 边置信度不确定性实验（场景合成、预训练、配对训练与汇总） |

`service/` 是统一模型服务，提供数据校验与分析、执行管理、模型包及推理入口。
业务后端通过内部 HTTP 调用服务；研究目录保持自己的 requirements 和 CLI。
当前开放 `riskgnn-node-edge` 与 `riskgnn-node-only` 的新加坡 smoke-v1 协议，
Bundle v1 支持分析。基线和 RiskGNN+ 源码随镜像提供，尚未接入的能力不会开放训练。
本地数据放在 `datasets/`，训练数据与模型产物通过对象存储或挂载输入；不打进镜像。
见[服务说明](service/README.md)与[能力边界](../docs/architecture/modeling-workbench.md)。
