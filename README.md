# 企业风险评估实验平台

基于 ComRisk 方法构建的企业风险模型与可交互演示系统。当前使用公开 **SMEsD 匿名企业数据**，已跑通「企业检索 → 企业画像 → 风险评分与解释 → 关系图 → 模型评估」流程。

这是海外企业信用评估项目的第一版方法验证系统，**尚未接入东南亚比赛数据**。当前结果属于公开基准实验，不是生产授信结论，也不是未来 12 个月违约概率。

## 当前功能

| 页面 | 路由 | 已实现内容 |
| --- | --- | --- |
| 实验工作台 | `/` | 当前模型、快照企业数、真实测试指标 |
| 企业检索 | `/search` | 按匿名企业编号或行业搜索、分页 |
| 企业画像 | `/company/:id` | 行业、数值特征、司法事件编码 |
| 评分与解释 | `/score/:id` | 模型概率、分类阈值、演示信用分、特征遮蔽分析、折叠显示评估标签 |
| 企业关系图 | `/graph?id=:id` | 有向一跳关系、企业/个人节点、边明细、关联企业评分跳转 |
| 模型评估 | `/model`、`/model-card` | 当前模型配置及 train/valid/test 实测指标 |

页面通过本地 API 读取真实数据；连接失败、未知编号和无匹配结果有明确提示，不回退到 mock。当前实验页面使用中文，保留原项目的导航与视觉体系。

报告生成、授信决策和批量上传**尚未接入**，对应入口显示未实现状态。旧前端原型及 mock 源码保留在 `frontend/src/pages` 和 `frontend/src/mocks`，当前路由使用 `frontend/src/live`。

## 模型与实测结果

模型采用企业属性与诉讼编码、门控异构关系聚合，并提供超图、折外行业先验和同域遮蔽预训练选项。实现借鉴 ComRisk 方法及 CompanyKG/GraphMAE 思路，并非上游代码的逐行复现，也没有使用 CompanyKG 数据或预训练权重。

SMEsD 去除跨划分重复企业后，训练/验证/测试企业数为 **2,816 / 686 / 474**，分别使用独立图快照。已完成六种配置、三个种子共 18 次实验；按平均验证 BCE 选择架构，使用预先指定的首个种子。

当前演示模型：`ComRisk-Gated-v1`，配置 `no_hyper`，种子 `42`；该配置未启用超图分支。

| 测试指标 | 本次实测 |
| --- | ---: |
| ROC-AUC | 0.7936 |
| PR-AUC（average precision） | 0.8456 |
| KS | 0.4955 |
| Brier | 0.1754 |

指标来自本次保存的训练产物；在其他环境重新训练可能不同，页面以当前加载的产物为准。详见 [实测结果](backend/docs/first-run-results.md) 和 [模型说明](backend/README.md)。

## 快速开始

以下命令面向 macOS/Linux，需 Git、Node.js 和 Python；本次验证环境为 **Node.js 24、Python 3.13、CPU**。首次获取数据和安装依赖需要网络。

仓库只包含代码、依赖锁文件及说明，**不包含原始数据、转换后的数据、模型权重或虚拟环境**。新机器必须先完成数据准备和训练。

### 1. 获取项目与安装依赖

```bash
git clone https://github.com/ilydouble/risk.git
cd risk
npm --prefix frontend ci

python3.13 -m venv backend/.venv
backend/.venv/bin/python -m pip install -r backend/requirements-lock.txt
```

### 2. 首次准备数据和模型

```bash
cd backend
# 从固定上游提交下载 SMEsD，并校验 SHA-256
.venv/bin/python scripts/fetch_smesd.py

# 转换、去重，生成独立 train/valid/test 快照
.venv/bin/python -m comrisk.smesd

# 六配置 × 三种子；输出评估、权重及模型选择记录
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 .venv/bin/python -m comrisk.benchmark --epochs 80 --seeds 42 43 44
cd ..
```

如果本机已有 `backend/data/processed/smesd/` 和完整的 `backend/artifacts/smesd-v1/`，可以跳过这一步。数据来自上游公开仓库，使用前请核对其适用条款；本项目不再分发该数据。

### 3. 启动后端与前端

在项目根目录打开两个终端，分别运行：

```bash
# 终端一：加载选定模型与测试快照，不在请求中训练
backend/.venv/bin/python backend/scripts/serve.py
```

```bash
# 终端二：启动前端
npm --prefix frontend run dev
```

- 演示页面：[http://127.0.0.1:3000](http://127.0.0.1:3000/)
- API 文档：[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

服务默认只监听本机。前端通过 `/api` 同源代理访问 8000 端口；必须同时启动前后端。数据和权重准备好后，本地推理不依赖外网；前端原有字体与图标样式引用外部 CDN，离线时外观可能有所变化。

### 4. 演示与核对

搜索 `C00010` → 打开画像 → 查看评分与解释 → 查看关系图 → 点击关联企业 `C01339` 查看其评分。本次保存模型下，两者风险概率分别约为 **72.69%** 和 **28.53%**。

前后端运行时，可以执行一致性检查：

```bash
backend/.venv/bin/python backend/scripts/check_demo.py
```

该脚本经前端代理读取结果，核对列表、预测、解释、关系及已保存评估指标。完整步骤见 [演示说明](docs/smesd-demo.md)。

## 开发与验证

```bash
# 后端算法及 API 契约测试
cd backend
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 .venv/bin/python -m pytest -q
cd ..

# 前端类型检查与构建
npm --prefix frontend run type-check
npm --prefix frontend run build
```

本次联调通过 13 项后端测试、前端类型检查与构建，并验证了浏览器完整路径、无效编号、无搜索结果以及后端断线后的重试恢复。

构建产物位于 `frontend/out/`。生产部署还需配置 `/api` 反向代理与 SPA 路由回退；当前交付为本地演示，没有生产认证与权限控制。

## API 与配置

| 接口 | 用途 |
| --- | --- |
| `GET /health` | 模型服务状态 |
| `GET /v1/companies` | 编号/行业搜索，支持 `q`、`offset`、`limit` |
| `GET /v1/companies/{id}` | 企业画像及模型预测 |
| `POST /v1/predict` | 按 `company_ids` 查询当前快照预测 |
| `GET /v1/explain/{id}` | 数值特征遮蔽敏感性 |
| `GET /v1/companies/{id}/graph` | 有向一跳关系，标明截断 |
| `GET /v1/model-card` | 模型元数据 |
| `GET /v1/evaluation` | 保存的训练、验证、测试指标 |

可用 `COMRISK_MODEL_DIR` 和 `COMRISK_DATA_PATH` 指定模型及快照；`COMRISK_API_TARGET` 指定 Vite 代理目标；`COMRISK_TORCH_THREADS` 控制后端推理线程数，默认 1。模型与快照必须符合相同 schema 和目标定义。更新数据或权重后需重启后端。

## 目录结构

```text
risk/
├── frontend/
│   ├── src/live/           真实 API 客户端与实验页面
│   ├── src/components/     导航与公共组件
│   ├── src/router/         当前路由
│   ├── src/pages/          保留的旧原型页面
│   ├── src/mocks/          旧演示数据，当前实验路由不使用
│   └── package-lock.json   前端依赖锁定
├── backend/
│   ├── comrisk/            数据适配、模型、训练、解释与 API
│   ├── scripts/            数据获取、训练启动、服务与联调检查
│   ├── tests/              算法与 API 测试
│   ├── docs/               方法、数据来源与实验结果说明
│   ├── data/               本地数据，不提交 Git
│   ├── artifacts/          本地训练产物，不提交 Git
│   └── requirements-lock.txt
├── docs/smesd-demo.md      启动和演示说明
└── README.md
```

## 结果解释与边界

- SMEsD 为公开匿名企业破产基准，不代表海外企业或实际业务的泛化效果；当前未使用新加坡数据。
- 原始事件时间与观察结果有关，图关系缺少完整时间戳，不能声称已经完成严格的时点有效性验证。
- 解释使用单特征替换为训练均值的概率变化，**不是 SHAP、不可相加、不表示因果**，也不覆盖全部模型分支。
- `300 + 550 × (1 − p)` 只是演示信用分映射；实际标签仅供评估核对，不作为推理输入。
- 关系图展示观测结构和处理后的边权，不能据此直接认定风险传播或业务授信建议。

## 参考与后续接入

- [ComRisk 上游项目](https://github.com/shaopengw/ComRisk)：本项目方法与 SMEsD 来源参考；固定数据提交和校验信息见下载脚本。
- [CompanyKG 上游项目](https://github.com/EQTPartners/CompanyKG)：方法结合评估见 [分析文档](backend/docs/companykg-integration.md)。
- [数据来源与替代数据](backend/docs/datasets.md)
- [比赛需求及实现边界](backend/docs/competition-v1.md)
- [后端方法、数据格式与复现说明](backend/README.md)

第三方代码、数据和依赖分别遵循其适用条款。本仓库不附带上游数据及训练权重；竞赛数据应独立管理，不上传公开仓库。
