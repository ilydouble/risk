# 架构导览

本仓库是单仓库工作台，首版可演示登录、企业检索、画像、关系图谱、评分与企业文件上传/下载。

```mermaid
flowchart LR
  Browser[浏览器] --> Caddy[Caddy / 静态前端]
  Caddy -->|/api 原路径| Gateway[Go 网关]
  Gateway -->|可信身份头| API[FastAPI]
  Gateway --> Redis[(Redis Session)]
  API --> Redis
  API --> PG[(PostgreSQL 18 / risk)]
  API -->|内部 HTTP| Model[RiskGNN]
  Model --> ModelDB[(PostgreSQL / riskgnn)]
  Worker[RiskGNN Worker] --> ModelDB
  Worker --> RustFS
  API --> Neo4j[(Neo4j Community)]
  API -->|预签名 URL| Browser
  Browser -->|对象字节| RustFS[(RustFS)]
```

| 主题 | 文档 |
| --- | --- |
| Python 分层、迁移与种子 | [后端](backend.md) |
| FSD、SDK 与页面边界 | [前端](frontend.md) |
| DTO、信封与错误处理 | [API 与错误](api-errors.md) |
| Compose、Session 与对象存储 | [基础设施](infrastructure.md) |
| 命令与验收 | [本地开发](local-development.md) |
| 旧模型迁移与停用 | [迁移说明](modeling-migration.md) |
| 数据集、实验、独立测试与发布 | [模型实验工作台](modeling-workbench.md) |
| 参数声明、配置快照、重试与实际规模 | [实验配置](experiment-configuration.md) |
| 协作者交付数据 ZIP、自检与新增适配 | [数据集接入流程](dataset-zip-onboarding.md) |
| 上传包身份、版本与适配器选择 | [数据集 ZIP 契约](dataset-contract.md) |
| 模型侧数据扩展与本地 CLI | [数据适配器](dataset-adapters.md) |
| 单模型 CLI 输入输出、事件与产物 | [模型执行协议](model-execution-contract.md) |
| 建模术语、不变量与适配边界 | [建模领域模型](modeling-domain.md) |
| 新加坡企业聚合与调试样本 | [新加坡企业概览](singapore-overview.md) |

原工作台评分和解释仍为演示；新加坡概览为固定统计，独立模型工作台执行真实子集训练。

- [执行与恢复](modeling-execution.md)：Outbox、租约、取消、Attempt 和事件。
- [训练协议](training-profile.md)：完整 ZIP 校验、特征边界与固定子集。
- [模型产物](model-artifacts.md)：封存、独立加载、发布与下载。

## 研究与后续设计

- [企业关系建图](../../models/riskgnn/docs/graph-construction-design.md)与[关系不确定性](../../models/riskgnn/docs/relation-uncertainty-design.md)
- [数据与规模证据](../../models/riskgnn/docs/comrisk-data-and-scale-evidence.md)、[置信度证据](../../models/riskgnn/docs/comrisk-confidence-channel-evidence.md)
- [SMEsD 受控实验](../../models/riskgnn+/docs/smesd-edge-confidence-experiment.md)
- [RiskGNN+ 研究文稿](../../models/riskgnn+/docs/riskgnn-plus-paper.md)，与当前服务开放能力分开验收
- [RiskGNN++ 研究工作稿](../../models/riskgnnpp/docs/riskgnn_plus_plus_paper.md)、[实验复现补充](../../models/riskgnnpp/docs/riskgnn-plus-plus-experiments.md)与[论文核验报告](../../models/riskgnnpp/docs/riskgnn-plus-plus-review.md)
