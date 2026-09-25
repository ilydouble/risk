# 前端

`frontend/` 使用 React 19、TypeScript、Vite、React Router、Tailwind、i18next、Recharts；无业务语义的选择器、提示和弹窗基于 Radix Primitives，页面与弹层动画由 Motion 实现。视觉样式与中文/英文切换沿用原页面。

## FSD 依赖方向

```text
app       路由、鉴权入口、全站布局
pages     各路由页面及页面专属组件
features  跨页面场景：认证、工作台布局、演示场景
entities  企业/图谱/评分/文档 API、风险语义、业务类型
shared    HTTP、OpenAPI 生成类型、基础 UI、i18n、工具
```

高层可引用低层，同层需要清楚的所有权；`pages` 之间不互相引用，低层不回引 `app` 或 `pages`。当前没有 `widgets` 层。跨页面遗留演示逻辑归 `features/demo-scenarios`，路由专属显示留在各 `pages`。

## API 调用

`contracts/openapi.json` 是服务端导出的权威契约。`npm run api:generate` 通过 `openapi-typescript` 生成 `shared/api/generated/schema.ts`，并在同一文件导出具名 `RequestXxx`、`ResponseXxx` 类型。使用方直接从该文件导入，不手改生成文件或再建 DTO 转发层。

`/login` 与 `/register` 是公开页面；注册表单进行基本输入校验，并将用户名冲突显示在当前表单。注册成功后跳回登录页，不在前端保存密码。

各业务 API 只声明 `http.post<RequestXxx, ResponseXxx>(url)`，页面使用 `XxxApi.requestXxx(body)`。`@stellarmesh/sdk` 0.3.1 负责传输、信封解包和错误码提取。页面或模块先处理已知错误；全局仅处理会话失效和通用提示，拦截层不抢先弹提示。

## 当前能力边界

原工作台检索、画像、图谱、评分走后端；评分和 SHAP 均为后端演示快照。报告、决策、模型看板、批量评估及首页汇总仍用本地演示逻辑。独立 `pages/benchmark` 通过 `entities/benchmark/api` 访问模型测试快照，跨页面加载与专区布局在 `features/benchmark`，页头标明公开基准与已保存模型。Caddy 提供 SPA 文件并原路径代理 `/api`，Vite 开发也代理同一路径。
