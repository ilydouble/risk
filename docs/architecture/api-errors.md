# API 与错误约定

## 请求与响应

业务接口以 POST 为主，请求体直接使用 `RequestXxx` DTO。成功响应为 `ApiEnvelope[ResponseXxx]`；失败的 `data` 为 `ErrorDetail`。`code` 必须等于实际 HTTP 状态，`internal_code` 为稳定机器码，`message` 为本次消息。请求标识只放在 `X-Request-ID` 响应头。

```json
{"code":200,"internal_code":"SUCCESS","message":"OK","data":{"items":[],"total":0,"page":1,"pageSize":50}}
```

已接通 `auth/login|logout|me`、`company/search|get`、`graph/get`、`score/get`、`document/create-upload|complete-upload|list|create-download`。健康检查和 OpenAPI 保留 GET。每个路由在 FastAPI 声明成功响应及错误响应 DTO，`contracts/openapi.json` 由服务端导出并纳入版本控制。

## 分层错误

1. 后端模块定义稳定的 `AUTH_*`、`COMPANY_*`、`GRAPH_*`、`DOCUMENT_*` 错误；全局 handler 序列化并处理 422 校验、404/405 路由和 500 意外错误。
2. 网关拒绝无效会话、伪造请求或不可用上游时输出同一四字段信封。Redis 故障为 503 `AUTH_STORE_UNAVAILABLE`，过期/缺失会话为 401 `AUTH_SESSION_EXPIRED`。
3. SDK 从 `internal_code` 提取机器码。调用方先处理本操作的已知错误；全局监听统一处理过期会话和未消费的通用错误。不会在 HTTP 拦截层先弹出重复提示。

`X-Request-ID` 贯穿网关与后端；对象存储预签名 PUT/GET 属 S3 字节通道，不套业务信封。默认网关保护业务 POST，删除客户端伪造的身份头并注入可信身份。后端再次校验 Cookie 身份与可信头一致。

## 契约变更顺序

1. 修改后端 `RequestXxx`/`ResponseXxx` 与路由响应声明。
2. 在 `backend/` 执行 `uv run python -m risk_api.export_openapi`。
3. 在 `frontend/` 执行 `npm run generate:api`，更新使用方并运行类型检查。
4. 检查导出结果及生成文件的 Git diff；不可手写相同 DTO。
