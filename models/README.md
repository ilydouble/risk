# 模型版本

本目录保存彼此隔离的模型实现：

| 目录 | 定位 |
| --- | --- |
| `baseline/` | 上游 ComRisk Git 提交 `a80524b3…` 的原始实现，使用 SMEsD |
| `riskgnn/` | RiskGNN 百万节点研究实现、邻居采样实验与[研究文档](riskgnn/docs/README.md) |
| `riskgnn+/` | RiskGNN+ 证据学习、SMEsD/UK 对照与[研究文档](riskgnn+/docs/README.md) |
| `riskgnnpp/` | 最新 RiskGNN++ 与 TACR 实现、[论文和实验材料](riskgnnpp/docs/README.md) |

`service/` 是统一模型服务，提供数据校验与分析、执行管理、模型包及推理入口。
业务后端通过内部 HTTP 调用服务；研究目录保持自己的 requirements 和 CLI。
当前工作台默认 RiskGNN+，使用有界诱导子图的普通关系、超图和已有事件进行证据学习。
新产物为 riskgnn-plus-model-v1；历史 RiskGNN 模型继续独立重载。
详见[工作台接入与限制](../docs/architecture/riskgnn-plus-workbench.md)。
