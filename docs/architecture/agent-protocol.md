# Agent Turn / Item 协议 v1

## 类型

Conversation 是用户拥有的对话。Turn 是一次用户输入触发的执行。
Turn 状态：running、completed、failed、cancelled、interrupted。
Item 使用 kind 判别：user_message、reasoning、agent_message、tool_call。
文本 Item 包含 text；工具 Item 包含 toolCallId、name、argumentsText、result。
Item 状态：running、completed、failed、cancelled。
工具结果为 JSON 值，错误是工具 Item 的 failed 状态；不会因此伪造 Turn 成功。

Event 包含 version=1、turnId、sequence、type、item、delta、status、error。
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
