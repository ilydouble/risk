# 模型版本

本目录保存彼此隔离的模型实现：

| 目录 | 定位 |
| --- | --- |
| `baseline/` | 上游 ComRisk Git 提交 `a80524b3…` 的原始实现，使用 SMEsD |
| `riskgnn/` | RiskGNN 百万节点研究实现、邻居采样实验与[研究文档](riskgnn/docs/README.md) |
| `riskgnn+/` | RiskGNN+ 证据学习、SMEsD/UK 对照与[研究文档](riskgnn+/docs/README.md) |
| `riskgnn+/riskgnn_pp/` | 最新 RiskGNN++ 与 TACR 实现、[论文和实验材料](riskgnn+/riskgnn_pp/docs/README.md) |

`service/` 是统一模型服务，提供数据校验与分析、执行管理、模型包及推理入口。
业务后端通过内部 HTTP 调用服务；研究目录保持自己的 requirements 和 CLI。
当前开放 `riskgnn-node-edge` 与 `riskgnn-node-only` 的新加坡 smoke-v1 协议，
Bundle v1 支持分析。基线和 RiskGNN+ 源码随镜像提供，尚未接入的能力不会开放训练。
本地数据放在 `datasets/`，训练数据与模型产物通过对象存储或挂载输入；不打进镜像。
见[服务说明](service/README.md)与[能力边界](../docs/architecture/modeling-workbench.md)。
