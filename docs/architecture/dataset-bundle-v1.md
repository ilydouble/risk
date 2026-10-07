# Bundle v1 数据 ZIP 协议

主流程见[数据集接入流程](dataset-zip-onboarding.md)。当前 Bundle 只开放校验和分析，
`supportedRunnerIds` 为空；包含图文件也不会自动获得工作台训练能力。

## 文件结构

所有文件直接位于 ZIP 根目录，不允许目录项、子目录或未在 metadata 声明的附件：

```text
metadata.json
samples.parquet
nodes.parquet        # 可选
relations.parquet    # 可选
events.parquet       # 可选
hyperedges.parquet   # 可选
```

每个表可选 CSV 或 Parquet，文件名通过 metadata 的 files 声明，扩展名须匹配 format。
metadata.json 不超过 1 MiB；ZIP 最多 6 个成员，其余容量限制见[主流程](dataset-zip-onboarding.md#3-按协议打包并本地自检)。
建议选 Parquet 保留字符串 ID 和时间/数值类型；交付说明、脚本等单独提供。

## metadata.json

| 字段 | 要求 |
| --- | --- |
| schemaVersion | 固定整数 1 |
| datasetName | 数据集名称，1–128 字符 |
| taskType / sampleUnit | 两者一致，取 loan_application 或 entity_snapshot |
| columns | 使用下表的固定列映射，不是任意列名映射功能 |
| target | name、positiveValue、businessDefinition；可选 predictionWindowDays（正整数） |
| features | 1–500 个唯一特征，不能占用六个样本基础列名 |
| files | 必需 samples；可选 nodes、relations、events、hyperedges |
| graph | 只要声明任意图文件就必须提供 |

columns 固定为以下键值：

```json
{
  "sampleId": "sample_id", "entityId": "entity_id",
  "observationTime": "observation_time", "graphSnapshotId": "graph_snapshot_id",
  "split": "split", "target": "target"
}
```

每个 feature 声明 name、kind（numeric/categorical）和 group；可选 description、recommended。
group 取 application、bureau、financial、registry、judicial、behavioral、derived、other。

每个 files 条目包含 path、format（csv/parquet）、sizeBytes、sha256。
sizeBytes 和 sha256 针对**实际写入 ZIP 的表文件原始字节**计算，SHA-256 为 64 位小写十六进制。
重新导出表文件后重新计算，metadata.json 自身不列入 files。
metadata 的模型定义拒绝未声明字段；新元信息先与维护者约定，不随意增加键。

graph 声明 snapshotMode="external"、snapshotDefinition，可选 staticExperimentOnly。
快照由提供方准备。若只支持静态实验，要明确设置 staticExperimentOnly=true，
不能据此声称评估了未来时点预测。

## 样本与图表

samples 必须包含六个基础列，以及 features 声明的全部特征列：

| 列 | 含义与要求 |
| --- | --- |
| sample_id | 非空、唯一的样本 ID |
| entity_id | 非空主体 ID；可对应同一主体的多次观察 |
| observation_time | 可解析为 UTC 的观察时间；建议使用带时区的 ISO 8601 |
| graph_snapshot_id | 该样本使用的图快照 ID，纯表格数据也保留此列 |
| split | train、validation、test；注意这里使用 validation，而不是新加坡协议的 val |
| target | 完整二分类标签，包含 metadata.target.positiveValue |

三个划分都要存在；每个划分的正、负类各至少两条样本。缺失标签不能填成负类。
positiveValue 的类型和取值应与表内标签一致，避免 CSV 类型推断导致比较不一致。
提供方应按真实时间/主体边界划分，记录重复主体跨划分的处理；服务不会替你确认业务泄漏。

| 可选表 | 必需列 |
| --- | --- |
| nodes | graph_snapshot_id、node_id、node_type |
| relations | graph_snapshot_id、source_id、target_id、relation_type、weight |
| events | graph_snapshot_id、node_id、event_type、event_time |
| hyperedges | graph_snapshot_id、hyperedge_id、hyperedge_type、node_id |

- 任意图表存在时都需要 nodes；节点键在各快照内非空且唯一。
- 样本主体、边端点、事件和超边成员必须引用相同快照中存在的节点。
- 关系权重使用有限正数；说明方向与单位，不把同址关系描述成股权或控制关系。
- 事件时间必须有效，不能晚于该快照所关联样本中最早的 observation_time。

当前样本和节点各最多 200 万行，样本最多 1,000 列；关系、事件、超边成员各最多 500 万行。
Bundle 分析会将表读入内存，行数与 ZIP 限额不是可用内存保证；大数据需先评估或新增流式适配。
不要把 211 万企业的原始新加坡导出机械转成 Bundle，以规避或替代专用协议。

## 生成可运行示例

以下示例是合成数据，只用于理解协议和验证分析链路，不作为研究或正式训练数据：

```bash
cd models
uv sync --project service --locked
mkdir -p runs
BUNDLE_CHECK_DIR="$(mktemp -d "$PWD/runs/bundle-check.XXXXXX")"
uv run --project service python -m service.tools.bundle_demo \
  --output "$BUNDLE_CHECK_DIR/example.zip" --task entity_snapshot --with-graph
uv run --project service python -m service.cli validate-data \
  --input "$BUNDLE_CHECK_DIR/example.zip" --output "$BUNDLE_CHECK_DIR/validated"
```

解压查看生成的 metadata 和各表；替换为真实数据时重新生成摘要、核对任务含义与划分。
校验成功后可上传工作台查看分析；要训练还需完成[新增 runner 流程](dataset-zip-onboarding.md#5-新数据协议或新模型需要补哪些代码)。

权威字段定义：[schema.py](../../models/service/datasets/bundle/schema.py)；
文件校验：[bundle.py](../../models/service/datasets/bundle/bundle.py)；
数据约束：[data.py](../../models/service/datasets/bundle/data.py)。
