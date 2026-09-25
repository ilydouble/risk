# 海外企业信用评估与授信决策系统

面向跨境金融 / 贸易授信场景的**内部风控工作台**。目标用户是信贷审批人员、风控分析师与业务经理。

核心价值：把「查企业 → 看画像 → 查关联图谱 → 看评分依据 → 出报告 → 给授信决策 → 验证模型 → 批量评估」串成一条完整链路，让授信决策**有据可依、可解释、可复现**。

界面采用浅色专业风（瓷白底、宝蓝主色、墨蓝字、金色点缀），全站支持**中英文双语**运行时切换。

> 本仓库当前包含前端工程（`frontend/`），使用前端 mock 数据驱动，REST 接口层按约定预留，便于后续替换为真实后端。

## ✨ 主要功能

| 模块 | 路由 | 说明 |
| --- | --- | --- |
| 总览看板 | `/` | 覆盖企业数、风险分布、今日评估量、系统状态、评估趋势 |
| 企业检索 | `/search` | 中英文名称 / 注册号模糊搜索，结果分组与筛选 |
| 企业画像 | `/company/:id` | 工商信息卡 + 变更时间线 + 风险标签 + 5C 雷达图 |
| 图谱关系 | `/graph` | 力导向图（2–3 跳、风险染色、节点下钻、传导路径高亮） |
| 评分详情 | `/score/:id` | 信用分 / 风险分位 / 违约概率 + SHAP 瀑布图 + 社区对比 |
| 报告页 | `/report/:id` | 流式生成正文、句末引用角标、悬浮证据卡 |
| 决策单 | `/decision/:id` | 授信额度、账期、结算方式、缓释建议、命中规则 |
| 模型档案 | `/model-card` | 模型身份 / 架构链路 / 训练数据 / 全局特征重要度 / 版本演进 / 漂移监控 / 治理合规 |
| 评估看板 | `/model` | AUC/KS/Lift/Brier、校准曲线、消融实验、跨国外推衰减（均带「复现」） |
| 批量评估 | `/batch` | 上传名单（CSV/TXT）→ 批量评分排序 → 结果筛选与 CSV 导出 |

全局能力：演示模式开关（一键初始化 + 预置案例）、顶部全局搜索、左侧分组导航、企业画像横向子页 Tab、报告生成进度条。

## 🛠 技术栈

- **框架**：React 19 + TypeScript + Vite
- **路由**：React Router v7
- **样式**：Tailwind CSS 3 + PostCSS
- **图表**：Recharts
- **国际化**：i18next + react-i18next（中 / 英，记忆于 localStorage）
- **图标**：lucide-react、Font Awesome、Remix Icon
- **工程化**：ESLint（含自定义规则）、unplugin-auto-import、路径别名 `@ → src`

## 🚀 快速开始

要求 Node.js ≥ 18。进入前端目录安装依赖：

```bash
cd frontend
npm install
```

启动本地开发服务器（默认端口 `3000`）：

```bash
npm run dev
```

浏览器打开 http://localhost:3000 即可访问。

## 📦 常用脚本

在 `frontend/` 目录下执行：

| 命令 | 说明 |
| --- | --- |
| `npm run dev` | 启动开发服务器（Vite，端口 3000） |
| `npm run build` | 生产构建（输出至 `out/`） |
| `npm run preview` | 预览生产构建产物 |
| `npm run lint` | ESLint 代码检查 |
| `npm run type-check` | TypeScript 类型检查 |

## 📁 目录结构

```
risk/
├── frontend/                 前端工程
│   ├── src/
│   │   ├── components/       通用组件（base 基础组件 / feature 业务组件）
│   │   ├── pages/            各页面（overview / search / company / graph …）
│   │   ├── constants/        导航、状态语义等常量
│   │   ├── context/          全局上下文（演示模式等）
│   │   ├── hooks/            自定义 Hooks（useLang 等）
│   │   ├── i18n/             国际化基础设施与中英词条
│   │   ├── mocks/            演示 mock 数据
│   │   ├── router/           路由配置
│   │   ├── theme/            主题 / 调色板
│   │   └── types/            全局类型定义
│   ├── index.html
│   ├── vite.config.ts
│   └── package.json
├── frontend/project_plan.md  详细设计与开发计划
└── README.md
```

## 🎨 设计规范：状态色语义

全站状态色（连接状态 / 系统服务 / 风险等级 / 存续与上线状态）统一采用「蓝 · 赭金 · 红」三色语义：

- **钴蓝**：低 / 正常 / 已连接 / 已上线 / 存续
- **赭金**：中 / 降级 / 演示 / 需关注
- **红**：高 / 中断 / 告警

状态点、状态标签、悬浮提示均有唯一封装组件（`StatusDot` / `StatusPill` / `Tooltip`），色值统一来自 CSS 变量 `--risk-low/medium/high`，禁止硬编码。

## 🌐 国际化

全站中 / 英双语，顶栏可运行时切换，选择记忆于 localStorage（key `credit-lang`），默认中文。词条按语言与命名空间分文件存放于 `src/i18n/local/{zh,en}/[namespace].ts`。

## 📄 数据与后端

当前阶段使用前端 mock 数据，暂不接入数据库；REST 接口约定已在服务层预留，后续可平滑替换为真实接口。更多设计细节见 [`frontend/project_plan.md`](frontend/project_plan.md)。
