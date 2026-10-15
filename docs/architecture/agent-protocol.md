# Agent Turn / Item 协议 v1

## 类型

Conversation 是用户拥有的对话。Turn 是一次用户输入触发的执行。
Turn 状态：running、completed、failed、cancelled、interrupted。
Item 使用 kind 判别：user_message、reasoning、agent_message、tool_call。
用户、推理、回答分别声明为 UserMessageItem、AgentReasoningItem、AgentMessageItem，均包含 text。
工具 ToolItem 包含 toolCallId、name、argumentsText、result。
拆分类型保留既有 kind 与 JSON 字段，历史 Item 无需数据迁移。
Item 状态：running、completed、failed、cancelled。
工具结果为 JSON 值，错误是工具 Item 的 failed 状态；不会因此伪造 Turn 成功。

Event 包含 version=1、turnId、sequence、type、item、delta、status、error，以及终态 finishedAt、durationMs。
事件 type：turn_started、item_updated、item_delta、turn_completed、turn_failed、turn_cancelled、turn_interrupted。
item_updated 携带完整 Item 当前快照，前端按 id 替换，重复事件按 sequence 忽略。
item_delta 包含 itemId、field（text 或 argumentsText）与追加文本。
服务端约每 120 ms 合并 token 后持久化；开始与完成使用完整 Item，期间发送追加增量。
Item 快照与增量事件同事务提交，避免长回答造成事件存储平方增长。
事件均使用 Pydantic 定义并进入 OpenAPI，前端从生成文件导入类型。
未来协议不兼容变更递增 version；不把 Strands 原始事件直接发送给浏览器。

## HTTP

普通 POST 使用既有四字段信封，前缀 `/api/v1/assistant`：

- `/conversations/create`、`/conversations/list`、`/conversations/get`
- `/turns/create`、`/turns/cancel`
- `/turns/events`：请求 turnId、afterSequence，返回 `text/event-stream`

SSE 是唯一不使用信封包裹的成功响应；建立连接前的错误仍使用错误信封。
SSE `id` 为 sequence，`event: turn_event`，`data` 为 Event JSON。
订阅立即发送注释，空闲每约 10 秒发送心跳，避免网关等待首包超时。
终态事件发送后关闭。重连以最后已处理序号订阅；不会重新执行 Turn。
请求使用现有 Cookie、Origin、X-Request-ID 策略；每次读取都校验所有权。
前端使用 fetch POST 流，因为 EventSource 无法提交现有 POST DTO。
重连、切换会话、组件销毁应关闭旧订阅；取消执行使用独立 API。

## 限制与异常

生成请求失败时前端保留 requestKey，网络重试不会重复执行。
会话忙返回 409；不存在或不属于当前用户均返回 404。
上游异常只返回稳定码和安全消息，不向前端暴露密钥、原始上游 body。
服务不可用不影响其他业务；不将断流当成成功。

## 推理展示

Strands 的 reasoningText 映射为 AgentReasoningItem，普通 data 映射为 AgentMessageItem。
每个 Turn 内连续的 reasoning、tool_call 合并为独立过程区，遇到 Agent 或用户消息结束分段。
所有 Item 保持服务端顺序；AgentMessageItem 始终显示，不跨 Turn 合并、不生成空过程区。
过程区使用首个 Item ID 作为稳定标识；流式追加只扩充当前分段，避免重建组件丢失折叠选择。
Turn 正在执行且过程区位于末尾时默认展开；出现下一条消息或 Turn 结束后默认收起。
用户手动选择优先，后续增量和状态更新不覆盖选择；不同过程区和 Turn 的状态均独立。
历史过程区默认收起。没有过程项时不显示空折叠区。
ReasoningItemView 直接展示 Markdown，避免推理再套一层折叠；工具参数与结果保留卡片展开操作。
过程区标题展示状态与推理、工具数量；整轮耗时由 Turn 的服务端计时字段提供。
不解析正文中的推理标签。
仅展示上游实际提供的推理文本；本协议不要求所有模型返回推理，也不规定供应商专属参数。

## Turn 耗时与整轮折叠

- `createdAt` 为后端接受并创建 Turn 的时间；`finishedAt` 为服务端首次确认终态的时间。
- 两个时间使用 PostgreSQL 时钟，`durationMs` 为非负毫秒差，与终态及终态事件在同一事务保存。
- 完成、失败、取消、中断均记录时间，重复终态请求不覆盖；恢复中断计到服务端确认中断时刻。
- 此耗时是 Turn 生命周期，包含调度、模型、工具及结束处理，不代表纯模型计算耗时。
- 运行快照的 `elapsedMs` 由服务端计算；终态快照返回持久化 `durationMs` 作为 `elapsedMs`。
- 浏览器仅在执行中从该快照起用 `performance.now()` 每秒递增，刷新后重新获取服务端基准。
- SSE 终态事件同时携带 `finishedAt` 和 `durationMs`，客户端停止递增并采用服务端值。
- V0010 仅新增可空字段；旧终态记录不补猜测值，显示“耗时未记录”。旧事件缺少字段仍可读取。
- UserMessage 始终显示在顶部，不参与整轮折叠；其下为耗时折叠按钮和水平分隔线。运行中的 Turn 初次显示时展开，完成时保持当前状态；加载已结束的历史 Turn 时默认保留 UserMessage 和最后一条 AgentMessageItem。
- 手动选择优先；隐藏而非卸载内部过程区，展开后保留各段的选择。没有 Agent 回答时默认展开以便排查。
