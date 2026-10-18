# UK 财务模型服务与助手接入

## 边界

模型服务持有固定底座、LoRA、运行缓冲区和冻结输入协议；业务后端负责账号权限、
企业记录、部署版本登记与预测历史；智能助手只选择已授权记录并调用工具。
助手使用的 Qwen/MiniMax 对话模型与此财务评分模型独立配置。

## 代码归属

- `models/uk_decision/src/uk_decision_runtime/`：训练与推理共用的底层加载和缓冲区读写。
  这是独立小包，不依赖 FastAPI 或模型服务。
- `models/service/src/model_service/modules/decision/`：输入/产物契约、校验、评分、校准、
  生命周期、CLI 和 HTTP。HTTP 与命令行调用同一个 Predictor。
- `scripts/`：兼容命令入口，不维护另一份预测实现。
- `backend/src/risk_api/modules/decision/`：权限、数据来源、部署模型与预测记录。
- 助手工具读取上述业务服务，不接收模型路径、任意 URL 或模型自行编写的财务特征。

## 常驻推理

启动时校验受信 Release 清单、模型包和全部底座文件，恢复训练保存的运行缓冲区，
使用固定候选顺序初始化 JevForge 并预热。每个模型服务实例仅加载一次。
Dishka 管理生命周期；专用单线程执行器串行评分，不阻塞 HTTP 事件循环。
请求取消或超时不会提前释放计算资源；新请求在实际计算结束前得到繁忙响应。
部署保持一个 HTTP worker，避免重复占用显存；训练 Worker 不加载该常驻模型。

模型未配置、加载失败或 GPU 不可用时，仅财务模型接口返回稳定的 503 错误；
其他模型工作台功能正常启动。就绪状态可查询；日志记录版本、请求 ID 和故障，不记录原始财务输入。

## 输入

直接输入沿用版本冻结的 `state.features`，仅用于明确提供财务资料的 API/CLI 预览。
企业预测读取账号拥有的数据集中的准确企业/观察记录，再由模型侧完成输入转换。
首版企业转换支持 `uk-research-v2` 原始财务属性及其声明的类别编码，
以及 `uk-financial-jsonl-v1` 直接提供的财务观测。
不对普通 CSV、旧 UK 七维图特征、ACRA 或 SMEsD 自动猜字段、补零或宣称兼容。
类别无法无损恢复时省略并报告；标签、审计标识、关系和目标信息不会输入财务模型。
旧七维 UK 数据必须明确返回数据不兼容，不能替换为“财务缺失”探针。

每次结果区分原始候选分数与校准分数，包含模型/输入摘要、版本、设备、精度和限制。
缺少正式校准文件时校准分数为空。分类目标仍是匹配研究队列中的未来 12 月正式破产观察标签。

## 版本与持久化

从 Release 安装的部署模型单独登记，不伪造本地训练 Run，也不改变已有图模型发布历史。
版本由完整 manifest 摘要确定，名称相同而内容不同的产物不可冒用同一版本身份。
预测记录按账号保存输入快照、来源、模型身份、结果、时间和请求 ID；重试使用相同请求键。
同一请求键配不同输入明确冲突；其他账号不能读取已有预测。
同时保存实际评分输入的序列化文本和 SHA-256，避免 JSONB 键排序丢失提示词原始顺序。

## 上传同事提供的 full 数据

目录包含三份 financial JSONL、sample-index.jsonl 和 manifest.json；
索引绑定企业注册编号、观测期与原始划分。它不是旧 UK 七维图数据。

```bash
./scripts/package-dataset --preset uk-financial \
  --data-dir /path/to/full --dataset-version 20261018
```

默认输出 `models/runs/datasets/uk-financial-20261018.zip`。在工作台上传并等待校验、企业导入。
服务扫描全部文件、核对摘要、字段、标签、索引和统计；127,646 条是观测数，不是去重企业数。
该适配器只支持浏览和财务推理，不提供 GNN 训练。原标签不进入模型输入。
数据专用规则见 [uk_financial/README.md](../../../models/riskgnn/dataset_adapters/uk_financial/README.md)。

## 助手与业务 API

1. `financial_risk_catalog()`：部署版本、就绪状态、当前账号的兼容数据集。
2. `financial_risk_companies(dataset_id, keyword, page)`：返回准确 recordId、companyId、观测期。
3. `predict_company_financial_risk(dataset_id, record_id)`：读取真实输入、计算并保存，返回结构化卡片。

同一企业可能有多个观测期；助手须选择用户要求的观测，不猜 ID 或财务值。
检索优先精确匹配观测 ID/企业编号；名称按前缀检索，使用索引避免扫描所有财务属性。
卡片显示来源、版本、原始/校准分数和限制，引用保存在 Turn Item 中，刷新可重放。
主卡片突出企业、财务观测月份及观测期后 12 个月的“破产风险参考分”，
由原始事件候选分数乘以 100 展示为 0–100 分，不增加风险等级或改变模型计算。
主卡片说明参考分不代表实际发生概率；模型版本、特征数、原始/校准分数、记录 ID、
输入摘要及设备精度等限制放入默认收起的“模型与计算详情”，支持中英文。
不把财务输入快照发送给对话模型。GNN 的 enterprise_risk_* 工具继续独立使用。

业务接口均为 Session 保护的 POST `/api/v1/decision/`：
`catalog`、`companies`、`predict`、`preview-input`、`get-prediction`、`list-predictions`。
preview-input 仅用于明确输入的 API/CLI 调试，不作为让助手编造财务数据的工具。
后端通过内部 HTTP `/internal/v1/decision/status|predict|predict-record` 调用模型服务，
传递 Request ID 和服务令牌；业务后端不安装 Torch。

## 部署与验收

CPU 为默认开发构建；CUDA 使用互斥 uv 依赖组及 Compose 覆盖，Torch 固定 2.7.1，
分别锁定 CPU 与 CUDA 12.8 wheel。
权重目录只读挂载，服务启动不下载模型。配置要求 CUDA 时不自动回退到 CPU。
GPU 容器需要宿主 NVIDIA 驱动和 Container Toolkit；构建镜像与下载权重在联网环境提前完成。

`.env` 选择已经完整安装的目录；默认 `uk-financial-0.6b-v1`，本机保留旧调试目录时可选新目录：

```dotenv
DECISION_ENABLED=true
DECISION_MODEL_DIRECTORY=uk-financial-0.6b-v1-verified
DECISION_CPU_THREADS=4
DECISION_TIMEOUT_SECONDS=60
```

```bash
# CPU：默认 float32；只改本服务无需重建训练 Worker
docker compose up --build -d riskgnn backend frontend
# CUDA：自动选择 cuda / bfloat16，Worker 保持 CPU
docker compose -f compose.yaml -f compose.gpu.yaml up --build -d
```

仅 HTTP 服务挂载 `models/weights/`；训练 Worker 显式关闭常驻财务模型。
镜像不包含本机权重或 full 数据，构建上下文通过 Dockerfile.dockerignore 排除它们。
现场离线交付使用 `docker image save`/`load` 传递已构建镜像，另传完整权重目录及 `.env`。
提前核对镜像 CPU 架构、驱动/GPU 和版本摘要；现场不运行 uv sync 或在线下载。

验收覆盖真实权重工程探针、HTTP 鉴权/错误、输入映射、记录与请求幂等、助手工具和卡片。
本机已用同事提供的真实 test financial JSONL 完成 CPU 与 CUDA 推理。
正式 calibration.json 和服务器固定参考输出仍未取得，尚不能验收服务器数值复现或校准指标。

2026-10-18：完整财务包 127,646 条观测已实际完成直传、全量校验、企业导入、CPU 评分和持久化；
直接 JSONL 与导入记录的输入摘要和 CPU 分数一致。浏览器验证历史卡片及中英文。
助手端到端使用本地 SSE 测试上游驱动真实 Strands、工具和财务模型，不代表已验收外部对话模型。
CPU/CUDA 镜像均已构建；本机 Python CUDA 验收通过，但 Docker 缺少 NVIDIA runtime，
GPU 容器未验收。目标机须先配置 Container Toolkit，不能仅据镜像构建成功判断 GPU 可用。
