# 工作台数据所有权

| 存储 | 所有者 | 内容 |
| --- | --- | --- |
| risk PostgreSQL | 业务 API | 用户、数据集归属、Run 配置、模型版本、Outbox |
| riskgnn PostgreSQL | 模型服务 | Job、Attempt、租约、事件、校验结果、产物索引 |
| risk-modeling Bucket | 模型链路 | uploads 暂存、datasets 固定副本、artifacts 模型包 |
| model-workspace 卷 | HTTP / Worker | 校验缓存、Attempt 工作目录、待上传结果、预测缓存 |
| Neo4j | 原企业演示 | 企业关系演示图，不写入训练快照 |

模型服务以任务 ID 幂等接收操作，不实现用户登录；业务 API 负责全部用户授权。
内部服务令牌不发给浏览器，模型服务不暴露宿主机端口。
业务后端和模型服务分别迁移各自数据库；原旧表保留，不把旧实验转换为新模型版本。
原始 Parquet 行按文件协议读取，不建立万能业务大表。
