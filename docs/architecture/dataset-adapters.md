# 模型侧数据适配器

## 目录与所有权

```text
models/riskgnn/
  train_sg_neighbor.py      原研究 CLI，命令与默认参数保留
  training_engine.py       研究 CLI 与工作台 CLI 共用的 epoch/优化循环
  workbench_cli.py          工作台执行入口
  runtime.json             当前模型操作、输入和参数的声明
  dataset_adapters/
    base.py                DatasetAdapter 抽象类
    contract.py            读取外层契约
    registry.py            显式登记数据适配器
    package_dataset.py     轻量打包 CLI
    delivery.py            读取各适配器的绑定预设与交付规则
    acra/                  ACRA 校验、分析、准备和静态概览
    smesd/                 SMEsD V5 JSON、人物与隔离快照
    uk_dataset_v1/         英国七维特征与三类超边
    snapshot_*.py          两个 JSON 数据集共用的结构与编码函数
    statistics.py          已复用的统计函数
    report.py              分析报告展示结构
  workbench/               模型包、训练配置、评估和预测
```

DatasetAdapter 提供 inspect(archive, workspace, config) 和 prepare(validated, output, config)。
inspect 负责该数据的语义校验及描述；prepare 负责 load、split、编码和模型输入准备。
两者都属于模型工程，model-service 不直接调用它们，也不要求其输出是统一业务大表。
当前准备输出的 NPZ 是 RiskGNN 自己的输入格式，不是全部数据集必须使用的上传格式。

## 新数据接入

协作者的实施步骤、返回字段、打包和上传链路统一见
[Adapter 接入指南](../../models/riskgnn/dataset_adapters/README.md)。

1. 判断已有适配器是否能够处理该数据；同一格式的新批次通常无需新增类。
2. 如有新语义，在 dataset_adapters/ 下实现 DatasetAdapter，声明精确 ID 和版本。
3. 明确标签、缺失值、划分、特征、关系和时间边界；实现自己的校验与准备。
4. 在 registry.py 静态注册；不得从 ZIP 内导入 Python 或按清单动态加载模块。
5. 数据提供方加入 risk_dataset_contract.json，指向该适配器及配置。
6. 完成小数据短训练、新进程测试/预测、失败场景和完整数据校验，再交付工作台使用。

各适配器的字段、配置、打包和训练范围见目录内说明：

- [ACRA](../../models/riskgnn/dataset_adapters/acra/README.md)
- [SMEsD](../../models/riskgnn/dataset_adapters/smesd/README.md)
- [UK](../../models/riskgnn/dataset_adapters/uk_dataset_v1/README.md)

ACRA 使用 smoke-v1；SMEsD/UK 使用 snapshot-node-edge-v1。
研究 CLI 的全量训练、GPU 和消融命令保持原样。
旧 Bundle 协议与合成演示生成器已移除，验收使用本地真实数据的固定子集。
训练策略属于模型侧：现有研究配置和工作台 smoke 配置可以不同，并在档案中明确记录。
未来确定使用 RiskGNN+ 时，再切换模型 CLI；不保证它自动兼容 RiskGNN 的输入与产物。

## 模型 CLI 本地调用

新工作台入口无需数据库和对象存储，可使用服务 uv 环境，或研究环境的可选
`pip install -r workbench-requirements.txt`。原研究 requirements.txt 不增加服务依赖。

在 models/ 下生成请求文件（路径替换成实际值）：

```python
import hashlib
import json
from pathlib import Path

source = Path("/absolute/path/dataset.zip")
with source.open("rb") as stream:
    sha = hashlib.file_digest(stream, "sha256").hexdigest()
request = {
    "contract_version": 2, "runtime_id": "riskgnn", "runtime_version": "2",
    "run_id": "local", "attempt_id": "1", "request_id": "local",
    "directory": "/tmp/riskgnn-local-train",
    "device": "cpu", "resources": {"threads": 2},
    "request": {
        "operation": "train",
        "inputs": {"dataset": {"path": str(source), "sha256": sha, "format": "zip"}},
        "parameters": {"epochs": 2, "dataset": {"target_count": 60}}
    }
}
Path("/tmp/model-request.json").write_text(json.dumps(request))
```

```bash
uv run --project service python -m riskgnn.workbench_cli --request /tmp/model-request.json
```

每次操作用新的空目录。先校验可改为 inspect、parameters={}。
train 返回模型目录；evaluate/predict 接收该目录，格式 riskgnn-model-v2。
目录摘要可通过模型侧 `riskgnn.workbench.artifacts.asset_digest(path)` 计算。
predict 参数为 company_ids 数组；evaluate 输出独立报告，不改模型文件。

服务执行时还会复核结果与产物并写成功回执；本地直接调用时检查退出码、
operation-result.json、events.jsonl 或 error.json。

## 协作与验证

- 原研究脚本不导入 model_service；服务也不导入研究模型。
- 服务和本轮模型接入模块的 import 均放在模块顶部。
- 原研究 CLI 按 --data_dir 加载本地 load_comrisk 的历史行为仍保留，
  这是研究环境自己的入口；工作台 CLI 只使用仓库的数据适配器。
- 共用训练核心已有原 CLI 的固定输入预测回归；参数和输出含义变化需明确版本化。
- 工作台产物保存配置、数据指纹、预处理和必要上下文；模型源码变化更新对应测试。
- 数据合同版本、数据版本、适配器版本、执行协议版本分别管理，不能互相替代。

测试可设 RISK_DATASETS_ROOT，默认为仓库 datasets/；完整验收使用 pytest --require-datasets。
缺数据的普通环境明确跳过数据集集成测试；要求数据的验收模式直接失败。

日常数据交付参见[预设打包指南](../../models/riskgnn/dataset_adapters/PACKAGING.md)，
只需选择预设、根目录、数据版本与输出，不要求安装模型环境或编写清单。
