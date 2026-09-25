# SMEsD 前后端演示

本版本使用已有 `no_hyper-seed42` 模型与去重后的 SMEsD 测试快照（474 家企业），未使用新加坡数据，也没有重训模型。

## 启动

仓库已附带演示需要的 SMEsD 测试快照与模型产物。新检出目录先按根 README 安装 Python 与前端依赖，即可启动，无需重新训练。完整训练数据不随包提供。

终端一，在项目根目录：

```sh
backend/.venv/bin/python backend/scripts/serve.py
```

终端二，在项目根目录：

```sh
npm --prefix frontend ci
npm --prefix frontend run dev
```

打开 http://127.0.0.1:3000 。前端 `/api` 代理到本机 8000 端口。不要只启动前端；后端不可用时会显示错误和重试按钮，不会使用虚构结果。端口占用时启动失败，不自动切换端口。前后端均仅监听本机地址。

`npm --prefix frontend run build` 生成 `frontend/out`。生产部署须单独配置 `/api` 反向代理及 SPA 路由回退；当前交付为本地开发演示。

## 演示顺序

1. 首页查看真实测试指标：AUC 0.7936、PR-AUC 0.8456、KS 0.4955、Brier 0.1754。
2. 企业检索输入 `C00010`，打开企业画像：行业、三个输入特征和 16 条司法事件编码。
3. 评分与解释：概率 72.69%，验证集选定阈值 49.40%；展开真实标签用于结果核对。
4. 关系图：16 条真实一跳边，区分企业和个人，保留源节点、目标节点、关系编码和模型边权。
5. 点击关联企业 `C01339` 并查看评分：概率 28.53%，解释同步切换。
6. 模型档案查看 train/valid/test 指标及原始 JSON。

## API

| 接口 | 用途 |
|---|---|
| GET /v1/companies?q=&offset=0&limit=20 | 按编号/行业搜索与分页 |
| GET /v1/companies/{id} | 画像、真实预测、数值特征、事件与评估标签 |
| POST /v1/predict | 原有预测接口，企业列表与详情在启动时用相同模型推理 |
| GET /v1/explain/{id} | 特征遮蔽敏感性 |
| GET /v1/companies/{id}/graph | 最多30条一跳边，可调limit，标明截断 |
| GET /v1/evaluation | 从当前模型目录读取实测指标 |

列表与详情预测缓存绑定服务启动时的模型及快照；更新权重或快照后重启后端。

## 验证

```sh
cd backend
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 .venv/bin/python -m pytest -q
cd ..
npm --prefix frontend run type-check
npm --prefix frontend run build
backend/.venv/bin/python backend/scripts/check_demo.py
```

最后一条要求前后端正在运行，核对代理接口返回的列表、预测、解释、关系和保存的指标是否一致。默认使用本项目选定的 SMEsD 模型与474企业测试快照。

## 展示边界

- 匿名企业编号没有伪造名称、国家、财报。
- 数值解释为训练均值遮蔽分析，不是 SHAP，不可相加，只涵盖三个数值输入；不代表因果或所有模型分支的贡献。
- 风险概率针对该公开数据集标签，不是未来12个月违约概率；300–850演示信用分只是线性映射。
- 图显示观测到的关系，不是经过验证的风险传播路径。边权已为模型处理后的值。
- 真实标签折叠显示仅用于评估，不是推理输入。
- 报告生成、授信决策及批量上传显示“尚未接入”，不输出静态伪结果。旧演示页面源码保留在 `frontend/src/pages`；当前路由使用 `frontend/src/live`。
- 实验界面为中文；没有宣称实现原前端全部功能或生产部署。
