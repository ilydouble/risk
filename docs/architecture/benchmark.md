# SMEsD 公开基准

## 数据与模型

`com_risk_model/data/processed/smesd/test.json` 是 474 家匿名企业及关联节点的只读快照，继续随 Git 提交。
正式包放在 `com_risk_model/weights/<版本>/`，只跟踪该目录的 `.gitkeep`；当前选择 `smesd-v1`。
启动时校验实际所选目录中的 manifest、metadata、metrics 和 weights，并预计算测试集预测。
数据留在文件，不写入 PostgreSQL 企业表或 Neo4j 演示图。

来源为 [ComRisk 项目](https://github.com/shaopengw/ComRisk) 固定提交
`a80524b3b67436cd2f74755f6ffa08a554ff2d02` 的 SMEsD。转换去除跨划分重复企业，
训练/验证/测试企业数为 2816/686/474；仓库只包含测试快照。训练与本地推理入口在
[模型工程](../../com_risk_model/README.md)，完整重训需另行取得训练与验证数据。

```bash
cd com_risk_model
uv sync --dev
uv run python -m testing.cli validate --model weights/smesd-v1 \
  --data data/processed/smesd/test.json
uv run python -m testing.cli predict --model weights/smesd-v1 \
  --data data/processed/smesd/test.json --ids C00010
uv run pytest -q --require-model
cd ../backend
uv run pytest -q --require-model tests/test_benchmark_api.py tests/test_demo_bundle.py
```

模型下载、格式和挂载升级见[产物约定](model-artifacts.md)。仓库不自动下载或训练。
研究文档、18 次历史实验汇总及原清单保存在 `com_risk_model/docs/`；历史路径只用于追溯，
不参与当前加载。迁移保留了现有权重、元数据、指标及快照的原始字节。

## 服务边界

FastAPI 的基准 Service 是 Dishka 应用级对象。专用单工作线程加载模型与快照、计算解释；
加载失败仅基准接口返回统一 503，原工作台仍可注册、登录与访问。网关保护全部基准 POST，
后端再次校验 Session。查询和图谱只读取测试包；搜索使用公共分页，批量预测保留输入顺序。

前端 `/benchmark` 与原 `/company` 等页面分开。样本 ID 如 `C00010` 无真实公司名称，
不映射为八家种子企业的 `C-1001` 等 ID。`C00010` 概率约 `0.726873`、原始一跳边 16 条、
保存的测试 ROC-AUC 约 `0.793637`，用于回归核验。

## 解释和授权边界

目标是公开 SMEsD 破产分类，不是固定未来窗口违约概率，也不能证明东南亚企业泛化。
300–850 分为 `300 + 550 × (1 − p)` 的线性演示映射，未验证为业务评分卡。
解释将单个数值特征置为训练均值，表示敏感性；它不是 SHAP、可加贡献或因果影响。
图谱显示原始一跳有向关系及边权，不推断业务含义或风险传播路径。
原数据事件时间与关系时间不足以证明严格时点有效性。

上游样本虽可公开下载，尚未核实明确的再分发许可；保留出处和校验清单不构成第三方授权。
对外分发数据或模型前仍需确认其许可。
