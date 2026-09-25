# 比赛第一版企业风险模型

本目录实现赛题十八项目的 **M3 评分算法原型**：企业属性与诉讼编码、门控关系聚合、超图、社区先验、自监督预训练、训练评估和本地预测 API。使用公开 SMEsD 进行方法验证，尚未接入格兰德东南亚数据。前端已接入真实企业检索、画像、评分解释、关系图与评估指标；演示流程见 [前后端说明](../docs/smesd-demo.md)。

## 快速运行

本次验证环境为 Python 3.13、CPU。虚拟环境、数据与模型不随 Git 提交；新机器需先安装、获取数据并训练。所有下列命令从 `backend/` 执行。

```bash
# 首次在新机器安装
uv venv .venv --python 3.13
uv pip install --python .venv/bin/python -r requirements-lock.txt

# 首次获取公开数据（需要网络）：
.venv/bin/python scripts/fetch_smesd.py

# 转换：保留三个独立快照，去除跨集重复企业
.venv/bin/python -m comrisk.smesd

# 训练一个完整模型
.venv/bin/python -m comrisk train --data data/processed/smesd --output artifacts/manual-full --epochs 80

# 三随机种子、六版本消融，自动生成报告
.venv/bin/python -m comrisk.benchmark --epochs 80 --seeds 42 43 44

# 验证算法与 API
.venv/bin/python -m pytest -q

# 启动按验证集选择的模型，默认只监听本机
.venv/bin/python scripts/serve.py
```

API 文档：http://127.0.0.1:8000/docs 。启动后不依赖外网。完整重跑脚本：`bash scripts/run_v1.sh`。

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/v1/model-card
curl -X POST http://127.0.0.1:8000/v1/predict \
  -H 'Content-Type: application/json' \
  -d '{"company_ids":["C00010"]}'
curl http://127.0.0.1:8000/v1/explain/C00010
```

公司 ID 以 `data/processed/smesd/test.json` 或 `artifacts/smesd-v1/predictions.json` 中实际值为准，非真实公司名称。可通过 `COMRISK_MODEL_DIR`、`COMRISK_DATA_PATH` 指定其他模型与数据快照。

## 方法与开源工作的关系

- **ComRisk**：独立实现“自身风险＋异构关系＋超图”的方法。保留案由/法院/结果 embedding 与分段时间衰减、超图归一化 Laplacian；原代码为参考，未复制代码。
- **门控聚合**：关系内 attention，关系间 attention，再用每个节点每个通道的 sigmoid gate 融合邻域。无固定 node-ID embedding，支持同 schema 新节点推理。这是 ComRisk-inspired 门控关系模型，**不是逐行复现 ComRisk，也不是标准 GraphSAGE 的完整实现**。
- **CompanyKG/GraphMAE 思路**：在训练期 SMEsD 图上做遮蔽企业属性重建，预训练后微调。未使用 CompanyKG 全量数据或预训练权重，也不是 eGraphMAE 的严格复现。
- **社区先验**：按行业超边类别计算 Beta-Binomial 风险先验，矩估计平滑强度并限制 [2,100]。训练企业用折外值；先验仅进入最终预测头，不参与图传播，减少标签通过邻域回流。尚未实现 Louvain 或国别社区。
- **校准**：验证集拟合单一 logit 截距；保留未校准指标。相同验证集还用于早停和阈值选择，因此其校准成绩不能当独立检验，最终看测试集。

## 数据与评估

原始 2,816/721/491 个监督样本存在跨集重复。按最早划分保留，最终为 **2,816/686/474**。训练、验证、测试分别使用独立图快照；训练时不读取验证/测试标签、特征或图做参数更新。验证用于早停、校准和模型选择。

转换同时完成：资本取 log1p、关系取 0–11 类、移除非正边权、边权 log1p、重复边合并、去除无属性公司端点、保留匿名个人节点、超边成员去重。详见 `data/processed/smesd/audit.json`。

原始节点总数 3,976 是公司数，不是监督样本总数。未使用 `meta_emb.pkl`，因为其预训练可见范围不适合作为严格隔离基准的默认输入。

评估输出：ROC-AUC、PR-AUC（average precision）、KS、Brier、Lift@10%、Top5%捕获、F1/Precision/Recall、校准曲线、训练曲线、基线与消融。基线为逻辑回归与 sklearn HistGradientBoosting；**并非 XGBoost**。这些表格基线仅使用三个企业属性及缺失标记；`self_only` 还使用诉讼，适合作为检验图增益的更公平基线。

六个版本：`full`、`self_only`、`no_graph`、`no_hyper`、`no_prior`、`pretrained`。按三种子的平均验证 BCE 选架构，默认使用第一个预先指定的种子，不按测试分数挑模型。`summary.json` 和各版本 `metrics.json` 是可复现的评估数据，不硬编码达标结果。

### 必须随结果说明的限制

- SMEsD 为中国中小企业公开基准，不是比赛东南亚数据，破产分类不是统一 12 个月违约概率。
- 原数据事件距破产/存续观察点的月份定义具有结果相对性，关系又没有完整时间戳；不能声称已完成真实业务 PIT 验证。
- 测试集破产率较高，与商业风控低坏账率不同。若测试阳性率为 p，Lift 最大约 1/p，Top5%捕获上限约 0.05/p；不能照搬申报书的绝对阈值。
- `credit_score=300+550*(1-p)` 仅为演示映射，输出携带标记，不是经过业务验证的授信评分卡。
- 局部解释为“将单个属性置为训练均值”的敏感性分析，不是 SHAP、不是因果贡献，数值不要求相加等于总分。图边仅为原始结构证据。
- 新节点可免重训推理，但不等于已验证跨国泛化。全图 CPU 前向不适合百万节点在线服务；本版本没有邻居采样、延迟 SLA 或生产认证。
- 尚未实现 Co-Correcting、弱标签构造、国家/时间划分器、完整 5C、报告智能体和授信规则引擎，不能据此宣称整个 SRS 已验收。

## 接入比赛数据

`comrisk/data.py` 定义严格 JSON schema（额外字段和非有限值拒绝）。

- `nodes`：id、kind（company/person）、community、features、label、split。
- `feature_names`：数值特征顺序；缺失用 null，特征顺序必须一致。
- `edges`：source、target、relation、正 weight。方向为 source → target，不自动生成反向边。
- `hyperedges`：kind、members，仅可引用公司。
- `events`：company、cause（0–10）、court（0–3）、result（0–3）、age_months（非负）。不存在诉讼数据可传空列表，不能伪造类别映射。
- `relation_names`、`hyperedge_types`：明确有序词表。
- `target_description`：写明实际标签定义，预测时必须与模型一致。

独立快照目录包含 train.json/valid.json/test.json；公司集合必须不重叠。若比赛任务需要同一企业跨期验证，应新增公司-时点样本协议和 PIT ETL，不能通过更换 ID 绕过当前约束。所有历史边、事件、财务属性应由 ETL 按评估截止时间过滤；当前格式不替代这一步。

新企业推理：构建包含其节点及可用邻居的 Dataset，调用 `Predictor(...).predict(dataset, ids)`；服务启动加载的固定快照仅供批量查询。格兰德数据请置于独立目录，不与公开 benchmark 混合，且不得上传公开仓库。

## 产物

- `artifacts/smesd-v1/summary.md` / `summary.json`：18 次实验结果与选择依据。
- 各版本 `weights.pt`：仅 state_dict，安全 weights_only 加载。
- `metadata.json`：特征 schema、训练预处理、社区统计、校准器、种子、数据 hash。
- `metrics.json`：实际评估结果。
- `docs/competition-v1.md`：比赛需求和实现边界。
- `docs/first-run-results.md`：本次实测摘要。

## 引用与许可

- ComRisk / SMEsD: Wei et al., Information Sciences, 2024, DOI 10.1016/j.ins.2023.120081；https://github.com/shaopengw/ComRisk 。本次固定提交 a80524b3b67436cd2f74755f6ffa08a554ff2d02；上游未见明确 LICENSE，不随代码再分发其数据。
- CompanyKG: https://github.com/EQTPartners/CompanyKG ，代码 MIT；数据独立条款尚未核实，本版本未导入该数据。
- 自监督方法是借鉴思路的独立实现，未复制上游模型文件，不声称原创基础算法。
- 第三方依赖版本见 requirements-lock.txt，各自许可随发行包。公开模型与竞赛数据用途应分别管理。
