# Agent 模型连接配置

## 范围与默认行为

`/api/v1/assistant` 使用 Strands OpenAIModel。
`RISK_LLM_THINKING_ENABLED=false`（默认）显式关闭推理；本地调试设为 `true` 开启。
仅接受 true/false（大小写不敏感）；非法值在启动时直接报错。
通过根目录 `.env` 的 `RISK_LLM_CONNECTION_TYPE` 选择接口类型，不根据模型名称猜测。
只接受 `qwen_self_hosted`（默认）和 `minimax`；非法值在后端启动时直接报错。
此选项用于 Agent；旧 `/chat/complete` 和问数兼容接口不使用这套参数映射。

| 类型 | 关闭时 | 开启时 |
| --- | --- | --- |
| `qwen_self_hosted` | `chat_template_kwargs: {enable_thinking: false}` | `chat_template_kwargs: {enable_thinking: true}` |
| `minimax` | `thinking: {type: "disabled"}` | `thinking: {type: "adaptive"}`，同时 `reasoning_split: true` |

参数通过 OpenAI 客户端 `extra_body` 合并到请求体，每次工具调用后的模型请求也会携带。
关闭思考不会关闭工具调用或回答流式输出；不使用 `/nothink` 提示词或 `reasoning_split=false` 代替。
接口必须实际支持对应参数；发送参数不等于已经验证远端实际采用了对应模式。

## 比赛：Qwen 自部署

```dotenv
RISK_LLM_CONNECTION_TYPE=qwen_self_hosted
RISK_LLM_THINKING_ENABLED=false
RISK_LLM_URL=http://172.16.4.3:8080/v1/chat/completions
RISK_LLM_MODEL=Qwen3.6-35B-A3B
RISK_LLM_API_KEY=你的内网令牌
```

适用于接受 `chat_template_kwargs.enable_thinking` 的 Qwen 自部署兼容端点。
模型名称应使用服务端实际暴露的 ID。比赛方若有网关参数限制，需核对其接口约定。
阿里云百炼使用顶层 `enable_thinking`，不属于当前 `qwen_self_hosted` 类型。

## 本地调试：MiniMax-M3

```dotenv
RISK_LLM_CONNECTION_TYPE=minimax
RISK_LLM_THINKING_ENABLED=true
RISK_LLM_URL=https://api.minimax.io/v1/chat/completions
RISK_LLM_MODEL=MiniMax-M3
RISK_LLM_API_KEY=你的MiniMax令牌
```

国内端点使用 `https://api.minimax.cn/v1/chat/completions`，按密钥所属平台选择。
填写原生模型 ID `MiniMax-M3`，不要使用 LiteLLM 的 `minimax/` 前缀。
MiniMax-M3 支持开关思考；M2.x 和 M3.1-Flash-Preview 不在此非思考配置的支持范围。
开启时用 `reasoning_split=true` 请求分离推理，Strands 将 `reasoning_content` 桥接到现有推理 Item。
开关控制模型请求，不根据普通回答中的文字猜测推理；最终展示取决于端点实际返回的字段。
推理会占用生成 token 预算；如出现长度截断，可在现有界面适当增大 maxTokens。
当前 Strands OpenAIModel 能投影推理流，但 Chat Completions 历史格式化会丢弃 reasoningContent。
本开关不改变该行为；工具续轮的真实效果需单独验收，不能将模拟流测试当成完整推理上下文兼容证明。

## 配置生效与记录

- API key 填原始令牌，不加 `Bearer `；OpenAI 客户端自动生成认证头。
- URL 填完整的 `/v1/chat/completions` 地址。
- 前端自定义连接可以覆盖 URL、模型名和密钥，但连接类型和推理开关始终由 `.env` 决定。
- 切换供应商时一起修改类型和连接信息；建议本地调试选择前端“使用后端默认模型”。
- 连接类型和实际 `thinking` 布尔值随新 Turn 配置入库并参与幂等判断；密钥不入库。
- 旧 Turn 不重写；更改配置后创建新 Turn。
- 原有推理 Item、持久化和 UI 保留，展示上游明确返回的推理，即使关闭时端点仍返回该字段。
- 当前 HTTP 客户端不读取运行时代理环境变量；`BUILD_*_PROXY` 仅用于构建。

首次更新代码后，在根目录构建并重建后端：

```bash
docker compose up -d --build --no-deps backend
```

之后仅修改 `.env` 时，重建容器以重新注入环境变量：

```bash
docker compose up -d --no-deps --force-recreate backend
```

真实端点验收应覆盖“普通回答”和“工具调用后继续回答”，分别检查开关参数生效、推理字段和回答完整性。
本地模拟端点测试只证明参数传递、工具循环及消息协议，不代替远端服务验收。

## 上游说明

- [Qwen3.6 非思考模式](https://huggingface.co/Qwen/Qwen3.6-35B-A3B#instruct-or-non-thinking-mode)
- [MiniMax OpenAI 兼容接口](https://platform.minimax.io/docs/api-reference/text-openai-api)
