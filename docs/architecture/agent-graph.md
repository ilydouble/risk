# Agent 企业图谱工具

## 工具与数据边界

- `search_companies(keyword)`：按企业名称或注册号查询，关键词 1～100 字符，最多返回 10 条及总数。
- `show_company_graph(company_id, depth=2)`：ID 必须来自查询结果或用户明确选择，深度限定 1～3。
- 多条企业匹配时要求用户选择；系统提示不允许模型猜 ID 或虚构工具执行结果。
- 语言通过创建 Turn 的 `lang`（zh/en）传递，不作为模型工具参数。
- 当前查询的是八家演示企业及 Neo4j 演示子图，不是新加坡真实样本或训练数据。
- 不开放 Cypher、任意 URL、布局或模型生成的节点与边。
- Agent 仅向已认证用户开放；当前演示企业为共享只读数据，真实私有数据接入需另加所有权校验。

## 后端调用与持久化

`CompanyGraphTools` 位于 `assistant/tools/`，由 Dishka 注入会话工厂与 Neo4j 驱动。
每次工具调用独立打开和关闭数据库会话，避免并行工具共用会话或捕获过期 HTTP 请求资源。
工具直接复用 CompanyService、GraphService，不通过 HTTP 调用自身接口。
Strands 1.60 不支持 Annotated 内的 Pydantic Field；工具显式使用参数模型生成 inputSchema，并在执行入口验证。

图谱成功返回 `CompanyGraphReference`：

```json
{
  "kind": "company_graph",
  "companyId": "C-1001",
  "depth": 2,
  "lang": "zh",
  "title": "北辰精密制造有限公司",
  "summary": {"nodeCount": 15, "edgeCount": 14},
  "demo": true
}
```

工具返回小型 JSON 引用，不将全部图数据送入模型上下文。
Projector 只接受 `show_company_graph` 的成功结构化结果，并经 Pydantic 校验后写入 `ToolItem.graph`。
普通回答中的 JSON、其他工具结果、失败或非法引用不会生成图谱卡片。
原始工具结果仍保留用于检查。`graph` 随 Item 快照和事件保存，刷新历史后可再次展示。
该字段可空，旧 Item 无需数据库迁移；OpenAPI 与前端生成类型同步维护。
企业不存在、图谱缺失、参数非法、基础设施不可用均作为失败工具结果，不生成可用图谱卡片。

## 前端

`ToolItemView` 只显示通用工具状态、参数和原始结果，提供可空的 `children` 交互插槽。
插槽位于原始参数/结果的 details 外；无需展开原始 JSON 即可操作附加内容。
聊天页 `TurnProcess` 选择业务渲染器，仅为成功且带 graph 引用的工具传入 `GraphResultCard`。
卡片来自 `features/company-graph/`，直接内嵌 300px 高的 G6 预览，展示名称、深度和演示标识。
前端固定调用 `GraphApi.requestGetGraph({companyId, depth, lang})`，使用当前界面语言。
请求继续经过网关、Session 与 Origin 校验；不请求工具指定的任意 URL。
面板保留加载、错误重试、缩放、拖动、重置及节点选择详情。
图谱 feature 通过 IntersectionObserver 按可视性加载面板，折叠或滚出视口时卸载并销毁实例。
保留预览占位高度，避免卸载改变列表高度；再次显示重新请求，视口和节点选择重置。
Turn 和过程区仍保持各自原有折叠规则，不因预览加载而改变。

企业图谱页面和内嵌预览共用 `features/company-graph/ui/CompanyGraph` 的业务展示适配。
`shared/ui/graph/GraphView` 仍仅接收通用节点、边及样式，不依赖企业 DTO 或 Agent 协议。
聊天页面不引用图谱页面组件。G6 通过懒加载面板按需加载。

## 当前数据而非快照

卡片中的数量是工具执行时对应语言的统计；预览显示时重新查询当前数据，并显示实际数量。
不同语言或后续数据变更可能导致两者不同。图谱引用不是不可变快照。
后续如需要固定历史视图，再加入数据版本或快照机制，不用客户端缓存假装历史一致。
