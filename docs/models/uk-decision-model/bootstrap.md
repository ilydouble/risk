# 首次启动：UK 财务模型与智能助手

本次交付基线为 `uk-financial-0.6b-v1`，只作团队版本约定，不增加状态或检查机制。
流程是下载模型与数据 → 启动服务 → 上传财务数据 → 助手检索、预测并保存。
不需要创建训练实验，也不需要在现场微调。

## 1. 准备环境

- 拉取包含本次交付代码的仓库；以下命令均从仓库根目录执行。
- 当前部署基线为 Linux x86_64、Docker Compose、uv、GitHub CLI。
- 私有仓库先执行 `gh auth login`；联网阶段需访问 GitHub、公开 Hugging Face 和构建依赖源。
- CPU 可直接运行。NVIDIA GPU 另需宿主驱动及 Container Toolkit。
- Apple Silicon 原生环境尚未纳入服务锁文件；同事可使用部署好的 Linux 服务联调。

## 2. 一次安装交付物

```bash
./scripts/uk-decision install --with-base
```

命令自动从同一 GitHub Release 下载完整 LoRA 模型包与配套财务数据集，
从公开 Hugging Face 下载固定 revision 的 Qwen3-0.6B 底座。
Release 尚未上传时会返回实际下载错误；发布前使用 [本地附件安装](release.md)。

安装完成后：

| 路径 | 用途 |
| --- | --- |
| `models/weights/uk-financial-0.6b-v1/` | 完整 LoRA、校准、协议、运行状态及 `base/`，供服务只读挂载 |
| `datasets/uk-financial-20261018/` | 已解压的财务 JSONL、索引及来源清单 |
| `datasets/uk-financial-20261018.zip` | 第 5 步上传工作台的文件，保留包内契约 |

可加 `--destination /path/to/model`、`--dataset-destination /path/to/data`。
自定义模型安装路径时同步调整 Compose 的权重挂载；常规使用保持默认目录即可。
不需要解压、移动 LoRA 子文件，也不要把底座与 LoRA 合并后另存。

## 3. 配置

首次使用复制 `.env.example` 为 `.env`；已有 `.env` 保留，补齐以下配置：

```dotenv
DECISION_ENABLED=true
DECISION_MODEL_DIRECTORY=uk-financial-0.6b-v1
DECISION_DEVICE=cpu
DECISION_DTYPE=float32
DECISION_CPU_THREADS=4
DECISION_TIMEOUT_SECONDS=60
```

智能助手的对话模型与上述财务模型分别配置。比赛自部署接口示例：

```dotenv
RISK_LLM_CONNECTION_TYPE=qwen_self_hosted
RISK_LLM_URL=http://your-llm-host:8080/v1/chat/completions
RISK_LLM_MODEL=Qwen3.6-35B-A3B
RISK_LLM_API_KEY=your-bearer-token
RISK_LLM_THINKING_ENABLED=false
```

本地 MiniMax 配置见 [Agent 模型连接](../../architecture/agent-model-config.md)。
容器中的 `localhost` 指容器自身；对话接口应填写容器可访问的真实地址。
宿主端口和可选构建代理按 `.env.example` 配置，默认页面为 `http://localhost:18080`。

## 4. 启动

CPU：

```bash
docker compose up --build -d
docker compose ps -a
```

NVIDIA CUDA：

```bash
docker compose -f compose.yaml -f compose.gpu.yaml up --build -d
docker compose -f compose.yaml -f compose.gpu.yaml logs --tail=100 riskgnn
```

GPU 覆盖文件选择 CUDA 镜像、设备与 bfloat16；CPU Worker 继续负责上传校验，不加载财务模型。
模型服务在 Compose 中仍使用 `riskgnn` 服务名，通过内部 HTTP 提供推理。
首次启动自动迁移数据库和初始化存储。财务模型加载失败不会阻止其他业务启动，
因此容器 healthy 之后还要确认下方工具目录返回模型就绪。

## 5. 上传财务数据

1. 打开页面，自助注册并登录。
2. 进入模型工作台的数据集页，上传 `datasets/uk-financial-20261018.zip`。
3. 等待直传和 Worker 全量校验完成，在企业数据区域完成导入。
4. 查看企业编号、财务观测月份和记录。127,646 是观测数，同一企业可能有多个月份。

该数据集只用于浏览和已部署财务模型推理，不创建 RiskGNN 训练实验。
普通 Companies House CSV、旧 UK 七维图数据和 SMEsD 不能自动替代本次财务输入。

## 6. 助手预测与结果保存

在智能助手中依次提出：

1. “列出可用的财务风险模型与我上传的兼容数据集。”
2. “在这份财务数据中查找企业 08876383，列出可用观测月份。”
3. “使用 2024-03 这条观测评估它的财务风险。”

工具链为 `financial_risk_catalog` → `financial_risk_companies` → `predict_company_financial_risk`。
工具选择准确的 `recordId`；数据集 UUID 和观测 UUID 来自检索结果，无需手写。
如该企业不在你实际上传的数据里，选择检索返回的其他企业和月份。

结果卡片显示破产风险参考分、观测月份和已保存状态，详情包含原始/校准分数、模型和预测记录。
刷新会话后应仍显示该结果。参考分适用于匹配研究队列，不是企业总体实际违约概率。
助手不接收原始财务输入，也不会调用外部接口自动补齐某家企业的财务资料。

## 7. 现场离线准备

在联网环境准备：相同代码、Compose、已构建镜像、完整权重目录、财务数据 ZIP 和配置。
镜像用 `docker image save` 导出、现场 `docker image load` 导入。
CPU 使用 `docker compose up -d --no-build --pull never`；GPU 同时带上两个 `-f` 参数。
现场对话模型端点也必须可达；0.6B 财务模型不承担通用对话。

发布前验收至少完成一次空目录安装、模型就绪、数据校验与导入、助手预测、刷新记录。
当前已验证本机 CPU、CUDA 及禁网 CPU 模型容器；整套比赛环境仍需在目标机器验收。
训练服务器参考输出未齐，全量训练指标来源及数值边界见 [模型说明](model-card.md)。
