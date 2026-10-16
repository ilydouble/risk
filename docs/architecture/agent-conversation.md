# Agent 会话与执行

## 边界

- 单一框架：Strands Agents 1.60.0，Python 3.12，OpenAI 兼容模型端点。
- `modules/assistant/runtime.py` 负责 Strands、模型和工具装配；不建立框架插件体系。
- `tools/` 按业务领域组织工具，`example_tools.py` 放通用链路示例；runtime 显式选择可用工具。
- `protocol/` 定义与框架无关的 Conversation、Turn、Item 和 Event。
- Repository 管持久化；Service 管执行、取消、超时和恢复；HTTP 层只做鉴权、DTO 和 SSE。
- `/chat` 改为持久会话界面。原 `/chat/complete` 与问数接口保留兼容，不能称为 Agent。
- 工具包括服务器时间、数据资产目录、只读问数和准备方案保存/试运行/结果查询；训练、推理及文档检索尚未接入。
- 正式企业导入由界面结果卡片明确确认，助手没有导入工具；详见[案例转换与企业导入](preparation-conversion.md)。

## 执行与恢复

1. 创建 Conversation；用户是唯一所有者。
2. 提交 Turn（用户文本、幂等 requestKey、模型配置）；事务保存用户 Item 和开始事件。
3. 应用拥有后台执行任务，SSE 仅订阅数据库事件；关闭页面不等于取消。
4. Strands 执行模型与工具循环，事件转换后先落库，再供订阅者读取。
5. 完成、失败、取消均保存终态；停止按钮发显式取消请求。

每个 Conversation 同时只能有一个 running Turn，数据库行锁串行化提交。
相同 requestKey 重试返回原 Turn；不同请求内容使用相同 key 返回冲突。
执行任务每 2 秒更新租约，租约 60 秒。其他实例只回收过期任务；回收后旧执行者不能写入。
服务关闭取消本实例任务；进程被杀后过期任务标为 interrupted，用户可重新发送。
不自动重放工具或模型调用，避免重复副作用；首版不提供持久执行队列。
最多执行 180 秒、12 轮 Strands 循环；同一进程最多 8 个活动 Turn。
工具内部问数规划另受50秒总预算及最多一次修正规则约束，仍计入整个 Turn 的180秒期限。

## 持久化

新增四张表：assistant_conversations、assistant_turns、assistant_items、assistant_events。
事件与 Item 快照、Turn 状态在同一事务更新；事件序号在 Turn 内严格递增。
首版列表最多返回最近 100 个会话，详情返回最近 100 个 Turn；旧记录仍保留。
Item 快照用于历史展示，事件用于恢复订阅。首版不清理事件；上线前按保留政策归档。
每次模型调用只重建最近完成 Turn 的用户文本和回答，限制 32,000 字符。
工具审计和推理展示不自动作为下一轮历史；不把客户端历史当成权威记录。
模型 URL、名称及 token 上限记录在 Turn；API key 仅存在本次执行内存，不入库、不写日志。

## UI

用户消息独立显示；回答支持 Markdown；推理与工具卡片可折叠。
只显示模型端点明确提供的 reasoning 内容，不编造思考、不展示内部系统提示。
工具显示名称、参数、结果、执行状态；参数接收完成与工具执行完成是两个状态。
侧栏选择持久会话，刷新恢复当前 Turn；连接错误和执行失败分别展示。
界面采用现有配色，参考 Codex 的简洁消息流、折叠过程和底部输入区。

## 资料

- https://pypi.org/project/strands-agents/1.60.0/
- https://strandsagents.com/docs/user-guide/sdk/streaming/
- https://openai.com/index/introducing-the-codex-app/

## 工作台问数工具

- `workbench_catalog` 返回当前账号的数据集/模型选择和语义字段目录。
- `workbench_ask` 接受自包含问题及可选 dataset_id/model_id，复用 DataQAService。
- 账号由鉴权后的 Turn 执行上下文绑定，不允许模型传入或更换账号。
- 每次工具调用创建并关闭独立数据库会话，不沿用已结束的 HTTP 请求资源。
- 问数规划使用本轮助手选择的模型连接；密钥仅存在执行内存。
- 原有字段白名单、账号隔离、范围校验、只读事务、超时和行数限制继续生效。
- 工具返回真实行、摘要、SQL、计划、警告和截断标记，现有工具卡片保存并展示结果。
- 错误以失败工具结果返回稳定码和安全消息，禁止暴露原始异常；不会自动放宽范围。
- 每次问数独立执行；助手需在追问中补全条件，范围不明时先澄清。
- 问数统一从 `/chat` 进入；独立菜单和页面已移除，旧地址 `/data-qa` 替换跳转到 `/chat`。
