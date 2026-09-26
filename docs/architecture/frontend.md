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

## 公共图谱组件

`shared/ui/graph/` 封装 AntV G6 5.1.1，两个图谱页面统一使用 `GraphView`。公共层只接收展示数据，不引用业务 DTO、不计算风险路径、不暴露 G6 实例。

```tsx
import { GraphView } from "@/shared/ui/graph";

<GraphView
  nodes={[{ id: "a", label: "企业 A" }, { id: "b", label: "企业 B" }]}
  edges={[{ id: "a-b-1", source: "a", target: "b", label: "持股" }]}
  centerId="a"
  selectedId={selectedId}
  onSelect={setSelectedId}
  height={620}
/>
```

- 节点支持 `color / size / opacity`，边支持 `color / width / dashed / opacity`；边 ID 必须唯一，允许同端点多条关系。中心节点使用较大默认尺寸；点击空白回调 `null`，移出数据集的选择会清除。
- 使用 G6 Canvas、`d3-force` 和配套拖拽；内置平移、缩放、重置视图及双语提示。平行边按曲线分开绘制，保留方向和全部关系。
- 组件负责容器尺寸监听、实例释放及错误重试，兼容 StrictMode。拓扑变化才重新布局；语言、颜色和选择变化只重绘，保留位置和视口。重置视图只执行适配。
- 企业页面负责风险颜色、路径虚线与弱化、详情联动；基准页面按关系内容和重复序号生成边 ID，保留关系列表、权重和截断说明。两套数据不混合。
- 企业 API 接受 1–3 跳查询，前端直接传递所选跳数并展示返回结果。基准数据与语言无关，切换语言只更新文案，不重新请求或清空图谱。
- 当前使用圆形与文字等基础样式；自定义图标节点和精细视觉留待后续。G6 随两个懒加载图谱路由加载。
