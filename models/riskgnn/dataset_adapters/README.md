# 数据集 Adapter 接入指南

本文面向新增数据集的模型开发者和负责打包上传的同事。
**新上传 ZIP 必须有唯一的 `risk_dataset_contract.json`。** 清单选择仓库中的适配器，
不会安装或执行 ZIP 中的代码；仅添加清单不能让不兼容的数据自动可训练。

日常数据交付请直接看 [选择预设并打包](PACKAGING.md)：无需手写契约或安装模型环境。

## 1. 谁负责什么，什么时候需要新适配器

| 负责人 | 交付内容 |
| --- | --- |
| 数据提供方 | 原始文件、字段/单位/标签说明、划分和图语义、来源、版本、使用范围 |
| 模型开发者 | 适配器、训练输入准备、兼容模型及产物、真实数据验收、目录内 README |
| 工作台维护者 | 上传、执行状态/事件、权限、产物存储和部署 |

工作台不决定 load、split、特征变换、构图或训练方法；这些由模型侧负责。
同一格式和语义的新批次通常复用适配器，只更新 `dataset.version`。
字段、标签、关系或划分语义改变时，再新增适配器或升级 `adapter.version`。
数据版本、适配器版本、外层清单版本、模型执行协议版本相互独立。

先参照最接近的实现：[ACRA](acra/README.md)、[SMEsD](smesd/README.md)、[UK](uk_dataset_v1/README.md)。
SMEsD 原始 Pickle 不直接上传；工作台使用处理后的 JSON。旧 Bundle 协议已删除。

## 2. 新建目录并实现三个必需方法

```text
dataset_adapters/new_dataset/
├── __init__.py
├── adapter.py          # DatasetAdapter 实现及配置校验
├── delivery.json       # 绑定预设、必需文件、配置约束及默认值
├── schemas.py          # 此数据的类型/字段约束，按需建立
├── validation.py       # 全量文件、ID、引用、标签和划分校验
├── preparation.py      # 读取、编码、预处理和模型输入准备
├── analysis.py         # 工作台质量、分布、划分等报告
└── README.md           # 专用语义、配置、打包命令、训练范围、已知限制
```

继承 [DatasetAdapter](base.py)，可参考 [UKAdapter](uk_dataset_v1/adapter.py) 的薄装配方式：

```python
from collections.abc import Iterable
from pathlib import Path

from riskgnn.dataset_adapters.base import DatasetAdapter
from riskgnn.dataset_adapters.contracts.enterprise import EnterpriseRecord
from riskgnn.dataset_adapters.contracts.inspection import InspectionResult


class NewDatasetAdapter(DatasetAdapter):
    id = "new-dataset"  # 清单中的稳定标识，不是 Python 模块名
    version = "1"
    trainable = False  # 只完成校验时保持 False

    def inspect(self, archive: Path, workspace: Path, config: dict) -> InspectionResult:
        raise NotImplementedError("实现全量校验和分析")

    def prepare(self, validated: Path, output: Path, config: dict) -> dict:
        raise NotImplementedError("实现模型输入准备")

    def enterprise_records(self, validated: Path) -> Iterable[EnterpriseRecord]:
        raise NotImplementedError("实现完整企业浏览记录导出")
```

这是待实现骨架。import 放模块顶部；原研究入口无需改用工作台或依赖服务包。
接通准备、训练和重载后，在开发分支设为 True，才能验收下文的完整 CLI 链路；通过后再发布。

### inspect：全量校验与描述

1. 校验 `config` 的类型、范围和未知字段；不要静默忽略不支持的选项。
2. 使用 [read_contract](contract.py) 获取清单位置，使用 [unpack](archive.py) 安全解压。
3. 全量检查所需文件、字段类型、ID 唯一性、图引用、标签掩码与划分；不能只抽样验文件。
4. 明确边方向、weight/strength/confidence、人物及超边语义，不执行附件 Python/Pickle。
5. 返回通过校验的 `InspectionResult`，必要数据落在 workspace，供 prepare 和企业导出使用。

公共输出字段、扩展信息及错误约束见 [输出契约](OUTPUT_CONTRACT.md)。
不要返回裸 dict、吞掉校验错误或用空值掩盖缺少的字段。`datasetContract` 由 registry 补入，
原校验辅助函数带该字段时，应先移除再构造 `InspectionResult`。

[registry.inspect](registry.py) 统一补充 datasetContract、supportedRunnerIds、compatibility、issues，
并写入 `validation.json`。适配器不自行认定平台任务 completed，也不访问数据库或对象存储。
非法数据/配置抛 `ValueError`，缺文件可抛 `FileNotFoundError`；模型 CLI 转为统一执行错误。
不能把校验错误吞掉后返回成功摘要。摘要不塞全量业务行，执行结果 JSON 上限为 1 MiB。

### prepare：生成模型真正能消费的输入

调用前 inspect 已成功，validated 是其工作目录。先复核实际文件与校验清单，
保留已有划分；需要抽样或重新划分时必须给出确定性规则、版本和实际样本清单。
预处理拟合范围、标签定义和关系政策由适配器明确，通常仅在训练划分拟合统计。

**当前 CLI 不使用 prepare 的返回值驱动训练，而是读取 output 中的文件：**

| 文件 | 当前 RiskGNN 要求 |
| --- | --- |
| `context.npz` | features、labels、splits、edges；加权快照另有 weights、confidence |
| `ids.json` | 与张量一致的节点索引；快照配置公司在前、人物在后 |
| `metadata.json` | 特征/关系顺序、预处理、划分、数据摘要、架构及实际消费能力 |
| `manifest.json` | 用 [seal](../workbench/artifacts.py) 封存，kind 为 `riskgnn-prepared-v1` |
| `evidence.json` | 可选；保存未消费的关系说明、超边或事件证据 |

NPZ 的监督划分名是 train / val / test；上下文为 context、label=-1。
上述文件属于 RiskGNN 内部输入，不要求上传包统一为 NPZ 或“万能大表”。
可复用相同 JSON 结构的 snapshot_* 函数，但数据专用语义仍写在自己的目录。
元数据细节参照 [ACRA preparation](acra/preparation.py) 和 [快照 preparation](snapshot_preparation.py)。
如新数据需要当前训练器不支持的输入，必须同步完善模型 CLI、训练和重载逻辑，
不能丢掉人物、方向、权重或超边后仍声称已经使用。当前 node_edge 未启用超图/事件分支。

### enterprise_records：导出企业浏览产物

这是必需抽象方法，未实现的适配器不能实例化；即使只支持分析，也必须支持企业导出。
流式返回 `EnterpriseRecord`；企业特征、属性、关系和快照映射由具体适配器负责。
公共导出器负责头部、逐条验证、数量核对、大小限制及原子发布，不负责推断字段和关系。
UK/SMEsD 可以复用 `snapshot_records()`；ACRA 自己按批读取 Parquet。
详细字段和新增适配器验收要求见 [输出契约](OUTPUT_CONTRACT.md)。

## 3. 注册、声明、打包支持

- 在 [registry.py](registry.py) 顶部导入并加入实例，`(id, version)` 必须唯一。
- 在 [runtime.json](../runtime.json) 的 `dataset_formats` 中加入 inspect 返回的 protocol。
  工作台通过模型声明展示格式，不需要在业务 API 再写一套数据加载分支。
- 在具体适配器目录添加 delivery.json，定义 adapter ID/version、必需文件、配置 Schema、
  默认配置和数据集预设。适配器调用 delivery_for(id, version) 复用配置与文件规则。
- 预设由数据负责人和适配器开发者首次确定；dataset.id 与 adapter.id 分别维护。
  打包器自动发现仓库声明，无需再维护 MARKERS；声明格式见 [打包指南](PACKAGING.md)。
- 新增依赖时同步模型可选依赖、服务 pyproject/uv.lock；不改变同事原研究环境的依赖方式。

## 4. 制作 ZIP：两条路径

**推荐：选择预设**。安装 uv 后，从仓库根目录执行固定入口，自动准备轻量环境。
示例预设需由开发者先新增，完整选项见 [打包指南](PACKAGING.md)：

```bash
./scripts/package-dataset --show-preset new-dataset
./scripts/package-dataset \
  --preset new-dataset --data-dir /path/to/new_dataset \
  --dataset-version 2026-10-11
```

目录就是数据根，不猜测；现有 ZIP 先解压。工具自动生成契约、检查必需文件和配置，
默认输出 models/runs/datasets/<预设>-<版本>.zip，--output 可选且不覆盖已有文件。
成功摘要区分默认打包与 --validate 全量校验，--json 用于自动化。允许的参数可用 --set KEY=JSON 覆盖。

**高级用法：手工清单**。在单个数据集目录放入以下文件，再压缩目录内容：

```json
{
  "contract_version": 1,
  "dataset": {"id": "new-dataset", "version": "2026-10-11"},
  "adapter": {"id": "new-dataset", "version": "1", "config": {}}
}
```

文件名必须是 `risk_dataset_contract.json`；位于 ZIP 根目录或统一单层目录，
与数据文件同根。清单最多 64 KiB，只声明数据身份和仓库适配器，不声明可执行脚本路径。
外层约束见 [JSON Schema](../../risk_dataset_contract.schema.json)。
ZIP 上限 512 MiB，解压总量 2 GiB、单文件 1 GiB、成员 128 个；拒绝链接、重复和越界路径。
一个 ZIP 只提交一套数据；例如 comrisk_export_v5 的 acra 与 smesd 必须分别打包。

## 5. 本地验收，再部署上传

先在本地执行适配器，无需 PostgreSQL/RustFS（仍从 `models/` 执行）：

```bash
uv run --project service python - <<'PY'
import tempfile
from pathlib import Path
from riskgnn.dataset_adapters.registry import inspect, resolve

source = Path("/tmp/new-dataset-v1.zip")
with tempfile.TemporaryDirectory() as work:
    validated, prepared = Path(work) / "validated", Path(work) / "prepared"
    report = inspect(source, validated)
    print(report["protocol"], report["counts"], report["compatibility"])
    adapter, contract = resolve(source)
    if adapter.trainable:
        adapter.prepare(validated, prepared, contract["adapter"]["config"])
PY
```

随后按[模型 CLI 示例](../../../docs/architecture/dataset-adapters.md#模型-cli-本地调用)
先验证 inspect → 企业导出 → 后端记录解析；再执行 inspect → 短训练 → 新进程 evaluate → predict → 导出/重载；原始数据保持只读。
用真实数据固定子集补必要测试：非法引用/划分、缺文件、非法配置、方向/权重、
未知预测 ID、预测顺序及重载一致性。完整文件校验与子集训练分开验收。
测试入口参考 [test_snapshot_datasets.py](../../service/tests/test_snapshot_datasets.py) 和
[test_adapter_flow.py](../../service/tests/test_adapter_flow.py)；新 fixture 应能定位新数据，
缺数据明确跳过，要求完整验收时失败，不能用未执行的训练冒充通过。

适配器随仓库代码发布；模型 HTTP 服务与 Worker 都必须加载同一新版镜像：

```bash
# 仓库根目录；完成代码检查和本地验收后执行
docker compose up -d --build riskgnn riskgnn-worker
```

在 `/modeling` 选择 ZIP：浏览器预览 → 预签名直传 → 确认上传 → Worker 全量校验 → ready。
再创建实验、查看事件、独立测试、发布和下载模型；未部署的新适配器会报“不支持”。
纯新增数据适配通常不改前端、业务接口或数据库。若增加 DTO，按仓库规则重新导出并生成。
最后核对工作台展示的实际训练输入、未启用能力、数据版本和指标含义，再交付同事使用。
