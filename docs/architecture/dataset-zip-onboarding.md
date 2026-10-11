# 数据集 ZIP 接入工作台流程

## 1. 分工

| 负责人 | 交付内容 |
| --- | --- |
| 数据提供方 | 数据文件、字段/标签/关系说明、数据版本、来源与使用范围、risk_dataset_contract.json |
| 模型开发者 | dataset_adapters、数据准备、训练/测试/预测、可重载产物及必要测试 |
| 工作台维护者 | 上传安全、进程与队列、状态/事件、权限、产物管理、页面和部署 |

工作台没有统一业务大表，也不决定 load、split、构图或模型算法。
新数据格式可以需要额外适配；具体数据语义由模型侧实现。
当前模型固定为 RiskGNN，未来确定 RiskGNN+ 后再切换。

## 2. 确定适配器

| 数据 | 当前适配器 | 能力 |
| --- | --- | --- |
| comrisk_export_v5/acra | sg-comrisk / 1 | 校验、分析、子集训练、测试、发布、预测 |
| comrisk_export_v5/smesd | smesd / 1 | JSON 快照校验、分析、训练、测试、发布、预测 |
| uk_dataset_v1 | uk-dataset-v1 / 1 | JSON 快照校验、分析、训练、测试、发布、预测 |
| 新加坡图数据、其他格式 | 需新增适配器 | 提交样本和语义说明后实现 |

同一数据格式的新批次更新 dataset.version；语义改变时升级或新增适配器。
不能仅改文件名、补假标签或重命名特征来通过现有校验。
新增适配器步骤见[模型侧数据适配器](dataset-adapters.md)。

## 3. 制作清单与 ZIP

每个新包必须有唯一的 risk_dataset_contract.json，见[完整契约](dataset-contract.md)。
清单在 ZIP 根目录或统一单层目录；具体布局以适配器要求为准。
包内 Python 不执行；需要的加载代码必须进入仓库，经测试后随模型镜像发布。

现有 comrisk_export 可以生成一个新的交付包，原包不会改变：

```bash
cd models
uv sync --project service --locked
uv run --project service python -m riskgnn.tools.package_dataset \
  --input /path/to/comrisk_export.zip --output /path/to/dataset-v1.zip \
  --dataset-id singapore-company --dataset-version 2026-10-11 --adapter sg-comrisk
```

通用 ZIP 上限 512 MiB，解压上限 2 GiB、单文件 1 GiB，最多 128 个成员。
压缩体积不能代表训练内存。需要分片或更大数据时另行明确资源与传输策略。

交付时同时说明：

- 数据 ID/版本、文件摘要、日期、来源、可使用范围和已知缺口。
- 样本粒度、稳定 ID、字段类型与单位、缺失含义、标签定义及观察窗口。
- 图节点/边/超边的类型、方向、权重、快照时点和构建方法。
- 划分方法、随机种子、防泄漏约束；可复现的数据准备命令。
- 小型有效样本与完整数据，拟使用的适配器及配置。

## 4. 本地与工作台验收

1. 模型开发者用[模型 CLI](dataset-adapters.md#模型-cli-本地调用)执行 inspect。
2. 核对文件索引、数据集契约、完整校验与数据统计。
3. 用小样本 train，再以新进程 evaluate/predict，检查产物能够独立加载。
4. 用户在 /modeling 上传新 ZIP，等待服务端校验，创建 RiskGNN 实验。
5. 查看阶段、指标和事件，确认刷新恢复、取消、重试行为。
6. 独立测试成功后发布、下载模型，并核对线上/离线预测和输入顺序。

sg-comrisk 当前运行 smoke-v1 子集，完整校验不等于全量训练；结果不描述成授信违约概率。
SMEsD / UK 当前使用 node_edge；超边和事件作为证据保留，未接入该配置的前向计算。

## 5. 接入完成标准

- 外层清单有效；模型侧校验真实字段、ID、标签、图和划分。
- 训练、测试和预测来自模型代码；服务没有复制算法或新建数据分支。
- 模型包包含重载所需全部信息，测试不改写训练产物。
- 缺清单、不兼容版本、非法配置、损坏文件和未知预测 ID 明确失败。
- 数据提供方与模型开发者的变更各自可追溯，文档说明实际使用的配置与资源。

本轮旧工作台数据与模型全部失效，不自动补清单或转换；按新契约重新上传和训练。
原研究 requirements、环境和训练命令继续可用。

## 6. 本仓库三份数据

适配器专用文档与可复制的目录打包命令：

- [ACRA](../../models/riskgnn/dataset_adapters/acra/README.md)
- [SMEsD JSON](../../models/riskgnn/dataset_adapters/smesd/README.md)
- [UK Dataset V1](../../models/riskgnn/dataset_adapters/uk_dataset_v1/README.md)

comrisk_export_v5 是包含两套数据的交付包，必须分别打包其 acra 和 smesd 子目录。
原始 datasets/smesd Pickle 不直接上传；旧 Bundle 及合成演示协议已移除。
