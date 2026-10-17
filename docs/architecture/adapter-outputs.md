# 数据集适配器输出边界

## 执行链

上传 ZIP → 模型服务执行 CLI inspect → Adapter 校验 → 企业导出 → 保存产物 → 业务后端导入。
本轮以新 Adapter 基线为准，不提供历史任务回填、旧输出回退或自动重跑。
旧数据不会因代码更新自动删除；新上传继续走校验与导出链。

## 职责

- DatasetAdapter 必须实现 inspect、prepare、enterprise_records。
- inspect 返回 InspectionResult，提供完整、类型化的源文件索引、规模、特征与目标定义。
- registry 补入数据契约和兼容性，验证源摘要后输出 ValidatedDataset。
- enterprise_records 返回 EnterpriseRecord 流，由 Adapter 负责字段、身份、快照和关系语义。
- 公共导出器验证记录、计数和容量，原子发布 JSONL，并返回 EnterpriseExportSummary。
- CLI 输出 InspectionOutput，runtime.json 的结果 Schema 由该类型生成，服务同步验证。
- model-service 负责进程、状态、事件和产物，不直接导入数据集适配器。
- 业务后端独立校验文件摘要、契约、结构及引用，再按事务导入，不依赖模型 Python 包。

## 协议与扩展

类型声明在 models/riskgnn/dataset_adapters/contracts/，按校验摘要和企业产物拆分。
仅允许声明的公共字段；数据集专有元数据放 metadata 或节点 properties 等明确扩展位置。
标准企业交换格式仍为 risk-enterprise-data-v1，上传契约及 HTTP DTO 不变。
这不是统一训练数据格式；load、split、特征编码、图构建和训练算法继续归模型侧。

## 验证与文档

单元测试约束接口完整性、错误输出和原子发布；生产者/消费者契约测试直接检查后端解析。
ACRA 真实子集及 SMEsD/UK 文件验证校验、导出、数量与 prepare 特征一致性；
CLI 测试验证独立进程执行。
详细字段、示例和新增 Adapter 要求见
[Adapter 输出契约](../../models/riskgnn/dataset_adapters/OUTPUT_CONTRACT.md)。
