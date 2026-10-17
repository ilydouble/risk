# 数据集图谱与助手工具

## 身份与统一入口

- `show_company_graph(dataset_id, company_id, depth=1)`：数据集 ID 必填，深度 1～3。
- 上传数据集使用目录返回的 UUID；共享演示使用固定逻辑数据集 ID `demo-companies`。
- 不再额外传 source；服务端根据明确的数据集 ID 路由，不按企业 ID 猜来源，不自动回退演示。
- `search_companies(keyword)` 仍检索演示企业，结果同时返回 `datasetId`。
- 上传数据集从模型目录、资产目录、企业查询或预测结果取得 `datasetId`，不能填 modelId/runId。
- 语言由 Turn 传入，不要求模型指定；不开放任意 URL、Cypher、坐标或自造节点。

## 数据来源与协议

Adapter → `risk-enterprise-data-v1` → PostgreSQL 标准企业记录 → 局部图接口 → G6。
现有 company/person/edge/hyperedge/event/snapshot 即为复用边界，不增加每数据集专属图谱工具。
共享演示继续读现有 Neo4j 种子，适配为同一展示响应，无须迁移演示数据库。
新增数据集应先通过 Adapter 输出标准记录及来源，验证引用；无关系的数据返回企业节点。
图谱展示不依赖模型服务，也不要求先发布模型。

## 查询边界

`POST /api/v1/graph/dataset` 使用 RequestGetDatasetGraph / ResponseGetDatasetGraph。
请求包含 datasetId、companyId、depth 和 lang，沿用 Session、Origin 和四字段信封。
上传数据集校验账号所有权、协议代际及企业导入状态；从中心企业确定 snapshot。
后续查节点和关系均限定 dataset + snapshot，不跨训练/验证/测试快照拼边。

- 普通关系的相邻实体算一跳，查询包含入边及出边，画布保留原始方向和平行边。
- 同一群组的成员作为一次逻辑扩展，画布以群组节点连接成员，不生成两两普通关系。
- 事件是所属企业的附属证据，不推进下一跳。
- 每次最多 100 个节点、240 条画布连线、100 条源关系记录，每组最多展开 12 个成员。
- 关系按源记录 sequence 排序，节点按记录顺序补齐；群组优先保留当前查询成员。
- PostgreSQL 单语句限时 2 秒，数据集图整个查询限时 6 秒；超时返回 GRAPH_QUERY_TIMEOUT。
- 返回 truncated、truncationReasons、omittedMembers 和 limits；不得将截断图称为完整图。
- 群组未展示数量是成员位置数，不是去重企业数。
- 展示元数据只返回有界摘要：原始属性前 20 个键、值最多 256 字符，以及关系记录序号和文件来源。
- 引用无法解析返回 GRAPH_DATA_INVALID，不凭空补节点。

## 图谱引用与历史

工具直接调用业务服务，不请求自己的 HTTP API；每次调用独立数据库会话。
成功返回 CompanyGraphReference，包含 datasetId/name、companyId、snapshot、depth、
统计、demo 标识及截断原因，不将全部图送进模型上下文。
Projector 仅接受该工具成功且经过类型校验的引用，保存到 ToolItem.graph。
普通文本中的 JSON 不触发图谱渲染；历史 demo 引用缺少新字段时按明确的旧协议解码。

前端根据引用请求固定图接口；旧 `/graph/get` 保留给现有演示页面使用。
引用中的数量是工具执行时统计；预览重新读取当前数据，引用不是冻结的可视化快照。
数据集 snapshot 字段表示输入划分/来源快照，不意味着历史渲染结果永远不变。

## 前端职责

`features/company-graph/ui/DatasetGraphPanel` 供企业详情和助手缩略图共用。
区分企业、人物、群组和事件；仅企业节点提供企业详情跳转。
支持关系过滤、节点/连线选择、来源摘要、加载/重试及截断说明。
人物 ID 不会被当作企业 ID；事件保留来源属性，不把编码擅自解释成法律结论。
`shared/ui/graph/GraphView` 仍只管理通用绘制、布局和交互。

ToolItemView 保持可空 children 插槽；GraphResultCard 内嵌 300px 预览。
IntersectionObserver 控制可见时加载，折叠/离开视区销毁实例，保留占位高度。
再次显示重新请求并重置选择；不改变 Turn/过程区原有折叠行为。

## 展示含义

这是数据集中的来源关系，可能不同于某次训练实际使用的子图。
连线不是预测贡献、风险传导或因果解释；需要训练子图解释时另行定义模型产物查询契约。
