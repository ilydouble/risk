# 数据集 ZIP 契约 v1

## 作用与边界

新上传 ZIP 必须提供唯一的 `risk_dataset_contract.json`。
工作台据此读取数据集身份、版本和适配器选择；不根据某个 Parquet 文件名猜测协议。
工作台不规定统一的业务表、特征、标签、划分或图格式。
具体语义由 `models/riskgnn/dataset_adapters/` 中已登记的代码负责。

## 最小示例

```json
{
  "contract_version": 1,
  "dataset": {
    "id": "singapore-company",
    "version": "2026-10-11",
    "name": "新加坡企业数据"
  },
  "adapter": {
    "id": "sg-comrisk",
    "version": "1",
    "config": {}
  }
}
```

| 字段 | 约定 |
| --- | --- |
| contract_version | 外层清单格式版本，当前为整数 1 |
| dataset.id | 稳定数据集标识，可用字母、数字、下划线、点和连字符 |
| dataset.version | 该批数据版本；内容改变后使用新版本 |
| dataset.name / description | 可选的人类可读说明 |
| adapter.id / version | 模型侧已登记适配器的精确标识和版本 |
| adapter.config | 必需 JSON 对象，内容由该适配器校验 |

权威 JSON Schema：`models/risk_dataset_contract.schema.json`。
未知顶层字段、不支持的格式版本、重复或缺失清单均拒绝。
清单不能指定 Python 模块、脚本路径或 shell 命令。
当前 sg-comrisk 和 bundle 的 v1 适配器只接受空 config。

## 文件位置与完整性

清单在 ZIP 根目录，或统一的单层顶层目录内；最大 64 KiB。
例如 `comrisk_export/risk_dataset_contract.json` 与同目录的 Parquet 文件一起打包。
外层允许单层目录，具体适配器可以更严格：Bundle 当前要求 ZIP 根目录。

ZIP 上限 512 MiB，安全解压上限 2 GiB；拒绝路径越界、链接和重复成员。
模型侧进一步校验所需文件、类型、ID、标签、划分和数据内容。
包内 `.py` 可作为说明附件保存，但不会被工作台执行。

服务计算 ZIP SHA-256 和文件索引，不要求人工填写每个文件的摘要。
数据集 ID/版本是交付标识；实际执行还绑定内容摘要，不能仅凭名称认为内容相同。

## 当前支持

| 适配器 | 数据格式 | 能力 |
| --- | --- | --- |
| sg-comrisk / 1 | 同事的 comrisk_export 数据 | 校验、分析、smoke-v1 准备、训练 |
| bundle / 1 | 现有 Bundle v1 | 校验、分析；当前 RiskGNN 不训练该格式 |

同一格式更新数据通常只需新 dataset.version；语义发生变化时升级或新增适配器。
不存在“增加清单就能训练任意数据集”的承诺。

## 生成一个新包

模型侧提供打包工具，不会修改或覆盖原 ZIP：

```bash
cd models
uv run --project service python -m riskgnn.tools.package_dataset \
  --input /path/to/comrisk_export.zip --output /path/to/dataset-v1.zip \
  --dataset-id singapore-company --dataset-version 2026-10-11 \
  --adapter sg-comrisk
```

工具只为已知布局补交付清单，不执行数据清洗、特征转换或模型训练。
其他数据由提供方按本协议制作清单，并由模型开发者实现对应适配器。

本轮为破坏性升级：旧工作台数据、任务和模型不再兼容；不自动转换历史对象。
新数据重新按契约上传。详见[升级说明](modeling-migration.md)。
