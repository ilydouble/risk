# SMEsD 模型研究实现

`src/risk_api/modules/benchmark/engine/` 保留第一版 ComRisk-inspired 实现：数据验证与转换、企业属性和司法事件编码、门控关系聚合、超图通道、行业 Beta-Binomial 先验、自监督预训练、训练与消融评估。HTTP 接口和应用级只读加载位于 `modules/benchmark/api/` 与 `service.py`，使用现有 FastAPI、Dishka、Session 和 API 信封。

本仓库附带 474 家匿名测试企业与所选 `no_hyper-seed42` 权重，可以直接推理。完整训练、验证数据及其他消融权重不在仓库中。Python 3.12 由 uv 管理；PyTorch 使用 CPU 专用索引，仅用于 PyTorch 包。执行以下命令时工作目录为 `backend/`。

```bash
uv sync --dev
uv run python -m risk_api.modules.benchmark.cli validate --data data/processed/smesd/test.json
uv run python -m risk_api.modules.benchmark.cli predict --data data/processed/smesd/test.json --model artifacts/smesd-v1/no_hyper-seed42 --ids C00010 --output /tmp/smesd-prediction.json
uv run pytest -q tests/test_model.py tests/test_demo_bundle.py tests/test_benchmark_api.py
```

如需重训，先运行 `uv run python scripts/fetch_smesd.py` 取得固定版本上游数据并核验 SHA-256，再运行 `uv run python -m risk_api.modules.benchmark.engine.smesd` 转换为独立 train/valid/test 快照。使用 `uv run python -m risk_api.modules.benchmark.cli train --data data/processed/smesd --output artifacts/manual-full --epochs 80` 训练单版本；运行 `uv run python -m risk_api.modules.benchmark.engine.benchmark --epochs 80 --seeds 42 43 44` 比较消融。`scripts/run_v1.sh` 串联这些步骤，可能需要较长时间和完整上游数据。本次整合没有重训已选权重。

## 方法与局限

- 本实现独立实现企业自身风险、异构关系和超图聚合思路，并非逐行复现原 ComRisk，也不是完整的标准 GraphSAGE。
- 训练和验证集用于模型拟合、早停、截距校准、阈值选择和版本选择；测试集仅用于报告。原始 2816/721/491 个监督样本跨集有重复，转换后独立公司数为 2816/686/474。
- 行业先验仅进入预测头；训练公司用折外先验。表格基线为逻辑回归与 sklearn HistGradientBoosting，只使用企业数值属性和缺失标志。
- 指标包括 ROC-AUC、PR-AUC、KS、Brier、Lift@10%、Top5% 捕获及 F1/Precision/Recall。`summary.json` 保留多版本实验汇总，只有所选模型的权重随包提供。
- SMEsD 破产分类不是统一未来窗口违约概率。事件时间与关系时间不足以建立严格时点有效性。线性信用分是演示映射，解释是数值特征遮蔽敏感性而非 SHAP 或因果贡献。

数据来源、只读文件清单、API 与再分发权限边界见[基准架构文档](../docs/architecture/benchmark.md)及[演示包说明](docs/demo-bundle.md)。
