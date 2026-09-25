# SMEsD 公开基准

## 数据与模型

`backend/data/processed/smesd/test.json` 是 474 家匿名企业及关联节点的一份只读测试快照。`backend/artifacts/smesd-v1/no_hyper-seed42/` 保存选定权重、预处理/阈值元数据及训练评估产物；`backend/docs/demo-bundle-manifest.json` 固定文件大小与 SHA-256。启动时校验清单、schema 和权重，并预计算固定测试集预测。数据留在文件，不写入工作台的 PostgreSQL 企业表或 Neo4j 演示图。

来源为 [ComRisk 项目](https://github.com/shaopengw/ComRisk) 固定提交 `a80524b3b67436cd2f74755f6ffa08a554ff2d02` 的 SMEsD。转换去除了原划分之间重复的企业，训练/验证/测试企业数为 2816/686/474；仓库只包含最后一份测试快照。数据转换、训练、消融评估和预测命令保留在 `risk_api.modules.benchmark`，完整重训需先取得未提交的训练与验证数据。

```bash
cd backend
uv sync --dev
uv run python -m risk_api.modules.benchmark.cli validate --data data/processed/smesd/test.json
uv run python -m risk_api.modules.benchmark.cli predict --data data/processed/smesd/test.json --model artifacts/smesd-v1/no_hyper-seed42 --ids C00010 --output /tmp/smesd-prediction.json
uv run pytest -q tests/test_model.py tests/test_demo_bundle.py tests/test_benchmark_api.py
```

需要重训时，先运行 `uv run python scripts/fetch_smesd.py`，再运行 `uv run python -m risk_api.modules.benchmark.engine.smesd` 转换；用 `risk_api.modules.benchmark.cli train` 训练，或用 `risk_api.modules.benchmark.engine.benchmark` 跑多个随机种子的消融。不会在 HTTP 请求中训练模型。

## 服务边界

FastAPI 的基准 Service 是 Dishka 应用级对象。专用单工作线程加载权重与快照、计算解释；加载失败仅基准接口返回统一 503，原工作台仍可注册、登录与访问。网关保护全部基准 POST，并在后端再次校验 Session。查询和图谱只读取测试包；搜索使用公共分页，批量预测保留输入顺序。

前端 `/benchmark` 与原 `/company` 等页面分开。样本 ID 如 `C00010` 无真实公司名称，也不能映射为八家种子企业的 `C-1001` 等 ID。测试集上 `C00010` 概率约 `0.726873`、原始一跳边 16 条、保存的测试 ROC-AUC 约 `0.793637`，用于回归核验。

## 解释和授权边界

模型目标是公开 SMEsD 的破产分类，**不是**固定未来窗口的违约概率，也不能证明东南亚企业泛化。300–850 分是 `300 + 550 × (1 − p)` 的线性演示映射，未验证为业务评分卡。解释将单个数值特征置为训练均值，表示敏感性；它不是 SHAP、可加贡献或因果影响。图谱显示原始一跳有向关系及边权，不推断业务含义或风险传播路径。原数据事件时间与关系时间不足以证明严格时点有效性。

上游样本虽可公开下载，本仓库尚未核实明确的再分发许可；保留出处和校验清单不构成对第三方数据的授权。对外再分发前需单独确认数据许可。
