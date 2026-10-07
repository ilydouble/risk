# 数据集 ZIP 接入工作台流程

适用对象：数据提供方、模型开发者、工作台维护者。
本流程对应 `models/service/` 当前实现；协议或能力调整时同步更新本文。

## 1. 先确定接入目标

| 输入与目标 | 当前支持情况 | 接入方式 |
| --- | --- | --- |
| 现有 `comrisk_export.zip` | 校验、分析、训练、测试、发布、下载、预测 | 遵循 [sg-comrisk-v1](dataset-sg-comrisk-v1.md) |
| 通用二分类样本及可选图数据 | 校验和分析 | 遵循 [Bundle v1](dataset-bundle-v1.md)，训练需另接 runner |
| `新加坡图数据.zip`：nodes/edges/hyperedges | 暂无直接适配 | 交付字段与图语义说明，按第 5 节新增适配 |
| 新数据源、新特征或新模型 | 不会自动接入 | 先确认协议，再实现数据适配和模型调用 |

当前只有 `riskgnn-node-edge`、`riskgnn-node-only` 支持新加坡 `smoke-v1` 训练。
ComRisk 原始基线和 RiskGNN+ 源码已进入镜像，但工作台尚未开放其训练与发布。
**ZIP 校验通过、模型能训练、模型包能独立推理，是三个分别验收的结果。**

新数据的含义如果与现有协议不同，应定义新协议或协议版本；不要只改表名、补假标签，
或把任意六个字段改名成新加坡特征来通过校验。

## 2. 明确分工与交付材料

| 负责人 | 负责交付 |
| --- | --- |
| 数据提供方 | 抽取/清洗脚本、ZIP、字段字典、标签与划分定义、数据来源及版本 |
| 模型开发者 | 可调用的模型入口、依赖版本、训练参数、评估口径与完整产物所需信息 |
| 工作台维护者 | 协议校验、数据准备、runner、模型包加载、HTTP/Worker 接入与验收 |

研究者继续使用自己模型目录的 requirements、Python/CUDA 环境和训练脚本。
服务侧独立维护 uv 环境；数据 ZIP 内的 Python 文件不会被工作台执行。
需要执行的适配代码应进入仓库，由维护者审核、测试后随服务镜像发布。

每次交付请附一份说明，可使用下面的清单；**说明文件可单独交付**，不要违反协议的包内文件限制。

- 数据集名称、版本、协议版本、生成日期、来源、可使用/共享范围、已知缺口。
- ZIP 文件名、字节数、SHA-256；各表行数、字段类型、单位、缺失值含义。
- 样本粒度与稳定 ID；标签定义、正例含义、标签观察窗口、正负例数量。
- train/validation/test 的划分方法、随机种子、各类数量、避免时间或主体泄漏的方法。
- 图的节点类型、边方向/类型/权重、快照时点、构图方法；有无人物、事件和超边。
- 可复现的数据生成命令；一份小型有效样本和完整数据包；目标模型及希望开放的能力。

数据内容改变后交付新版本、新 ZIP 和新摘要；服务按上传内容指纹绑定实验。
原始数据保存在对象存储，PostgreSQL 保存归属、任务及结果元数据，无需导入业务大表。

## 3. 按协议打包并本地自检

| 限制 | sg-comrisk-v1 | Bundle v1 |
| --- | --- | --- |
| 压缩包大小 | 最大 512 MiB | 最大 512 MiB |
| 解压总量 / 单个成员 | 最大 2 GiB / 1 GiB | 最大 2 GiB / 1 GiB |
| 单个成员压缩比 | 不超过 200 倍 | 不超过 200 倍 |
| ZIP 成员数量 | 最多 128，含目录项 | 最多 6 个普通文件 |
| 目录结构 | 根目录或一层统一目录 | 全部文件直接位于 ZIP 根目录 |

两种协议都拒绝重复文件、加密成员和链接。使用普通 ZIP；不要夹带虚拟环境、权重或嵌套压缩包。
优先用 Parquet 明确字段类型，尤其是带前导零的企业 ID。容量超限时先协商分片/流式协议，
当前工作台不会自动合并多个 ZIP；压缩体积也不能代表分析或训练所需内存。

以下命令使用服务的 Python 3.12 / Linux x86_64 CPU 环境，从仓库根目录开始，
不依赖数据库或对象存储；服务环境不会改动研究环境。环境详情见[服务说明](../../models/service/README.md#独立服务环境)。

```bash
cd models
uv sync --project service --locked
mkdir -p runs
DATASET_CHECK_DIR="$(mktemp -d "$PWD/runs/dataset-check.XXXXXX")"
uv run --project service python -m service.cli validate-data \
  --input /path/to/dataset.zip --output "$DATASET_CHECK_DIR/validated"
```

将输入路径替换为待交付 ZIP。每次使用新的输出目录，避免旧文件影响校验。
成功后检查 `validated/validation.json`：`protocol`、`sha256`、`files`、`counts`、
`analysis`、`supportedRunnerIds`。进程非零退出表示未通过；保存完整错误供维护者定位。
Bundle 当前的 `supportedRunnerIds` 为空列表，表示仅支持分析。

仅对已适配的新加坡数据继续执行训练冒烟检查：

```bash
uv run --project service python -m service.cli prepare \
  --input "$DATASET_CHECK_DIR/validated" --output "$DATASET_CHECK_DIR/prepared"
uv run --project service python -m service.cli train \
  --input "$DATASET_CHECK_DIR/prepared" --output "$DATASET_CHECK_DIR/model" \
  --runner-id riskgnn-node-edge --epochs 2
uv run --project service python -m service.cli test --input "$DATASET_CHECK_DIR/model"
uv run --project service python -m service.cli export \
  --input "$DATASET_CHECK_DIR/model" --output "$DATASET_CHECK_DIR/model.zip"
```

`test` 在新进程加载模型。当前准备阶段使用 seed 0，要求训练/验证/测试各含两类标签；
最多抽取 2,000 个有标签目标并加入有限图上下文。校验扫描全量数据，训练不是全量训练。
两轮冒烟结果用于证明链路可运行，模型效果需要另行评估。

## 4. 在工作台完成一次验收

1. 上传 ZIP，等待服务端校验；核对协议、文件摘要、统计、划分和分析报告。
2. 选择可用模型配置并创建实验，核对所选数据集和参数；无可用 runner 时先做第 5 节。
3. 查看阶段、epoch 指标、Attempt 和事件；刷新页面后状态与记录应仍可读取。
4. 独立测试成功后发布模型版本，核对数据指纹和实验档案。
5. 下载完整模型包，校验摘要并在独立目录加载；参考[离线使用](model-artifacts.md#下载和离线使用)。
6. 使用“填入模型内企业”测试预测，核对 HTTP 与离线结果、输入顺序和未知 ID 的行为。

由维护者另外验证跨用户权限、失败重试与取消。当前推理只接受模型绑定图内的企业。
发布只创建不可变模型版本，不会切换生产模型或自动上传 GitHub Release。

## 5. 新数据协议或新模型需要补哪些代码

以下由工作台维护者与模型开发者共同完成。可以沿用现有协议时，不必重复实现。

| 接入点 | 需要实现或核对 |
| --- | --- |
| `datasets/dispatch.py`、`adapters/` | 明确的格式识别、schema/ID/标签/划分校验、文件摘要及数据准备 |
| `analysis/` | 质量、缺失、标签分布、漂移与图统计；注明全量或抽样范围 |
| `runners/registry.py` | 数据协议与模型的兼容关系；完成验收后才开放 trainable |
| `cli.py`、`execution/worker.py` | 将新协议路由到对应准备/训练/测试流程，沿用任务、租约、取消和事件 |
| `model/`、`training/`、`runtime/` | 调用研究模型、保存必要状态、独立重载与批量推理 |
| API 与前端 | 复用现有 DTO；需要新字段或错误码时更新 OpenAPI、生成类型和中英文界面 |

表中路径相对 `models/service/`。**只在能力目录里增加模型名称不足以完成接入**：
当前准备与训练流程仍有新加坡协议约束，必须同步完成执行路由和模型包适配。
预处理只在训练划分拟合；验证集选择检查点；测试集用于最终独立报告。
模型包需包含权重、模型配置、预处理、特征顺序、ID/关系编码和推理所需上下文，
详见[模型产物协议](model-artifacts.md)。不要另外复制一套研究算法到服务侧。

## 6. 接入完成的交付标准

- 数据集：小型样本与完整包通过校验，来源、版本、标签、划分和统计可追溯。
- 模型：有效样本完成准备、短训练、新进程测试、导出和独立加载预测。
- 失败情况：缺文件、错误摘要、非法 ID/划分、不兼容版本及未知预测 ID 能明确报错。
- 工作台：上传至发布/下载/预测真实跑通；无兼容 runner 的数据只标为可分析。
- 代码：协议说明、适配实现及必要测试随同提交；契约有变化时重新导出 OpenAPI。
- 记录：交付 ZIP 摘要、测试命令、服务提交号、runner/模型版本和验收结果。

常见问题：找不到 company_attr → 检查协议和目录深度；ID 映射错误 → 检查行序；
特征顺序错误 → 检查 feature_config；无法创建实验 → 检查 supportedRunnerIds；
模型服务不可用 → 先检查 HTTP/Worker/基础设施状态，再判断数据是否有问题。
