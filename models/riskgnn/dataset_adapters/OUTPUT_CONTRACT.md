# Adapter 输出契约

## 新基线与边界

每个 DatasetAdapter 必须实现 inspect、prepare、enterprise_records。
本轮收紧模型侧 Python 接口，旧 Adapter 返回裸字典的实现不兼容；没有历史任务回填或自动重跑。
不清理数据库、已上传文件或旧模型。新上传仍执行校验后自动企业导出，只有全部成功才发布结果。
打包入口和 risk_dataset_contract.json 不变；上传者不需要自行提供 enterprises.jsonl。

这些类型位于模型侧 contracts/，不依赖 model-service、HTTP DTO 或数据库。
加载、划分、标签、图语义、训练输入仍由 Adapter 和模型代码负责。
registry 和 CLI 在跨进程边界转换为 JSON，服务只执行命令、保存结果和产物。
CLI 完成导出后输出 InspectionOutput，强制包含 enterpriseData（格式和数量）。
同一个模型自动生成 runtime.json 的 inspect.result_schema，服务据此校验执行结果。
修改类型后，从 models/service/ 执行：

```bash
PYTHONPATH=.. uv run --no-sync python -m riskgnn.dataset_adapters.contracts.export_schema
```

测试核对生成 Schema 无漂移，不能只修改 runtime.json 放宽约束。

## 校验摘要：contracts/inspection.py

Adapter.inspect 返回 InspectionResult，不再返回 dict。

| 字段 | 约束 |
| --- | --- |
| protocol | 非空数据格式标识 |
| sha256 | 实际源 ZIP 的 64 位小写十六进制摘要；registry 再与源文件比较 |
| files | 非空文件索引，含 workspace 相对路径、非负字节数及 SHA-256；路径不得重复或逃逸 |
| counts | 非负整数；必须包含 company_attr；人物、边、群组、事件使用 persons/edges/hyperedges/events |
| features | 非空、不重复的特征名称列表 |
| labeledCount / positiveCount | 0 ≤ positiveCount ≤ labeledCount ≤ company_attr |
| splits | 划分名称、样本数、正例数、可选 seed；正例数不大于样本数 |
| datasetProfile | 必须包含 datasetFormat、taskType、target；格式须与 protocol 一致 |
| analysis | 可选 JSON 分析报告，展示内容仍遵循既有分析报告约定 |
| limitations | 数据与模型使用限制 |
| metadata | 数据集专属 JSON 扩展信息；不允许任意增加顶层字段 |

root、relations 为公共读取与关系统计字段。ACRA 的 source、edgeFile、edgeEvidence 已下沉 metadata。
DatasetProfile 可携带 evaluation/features/splits/relations 和 metadata。
未知字段、类型错误、NaN/Infinity（包括扩展字段内）均拒绝。
数据语义校验仍属于 inspect，类型校验不替代文件扫描、标签定义、划分或图引用检查。

registry 生成 ValidatedDataset，补入验证过的 datasetContract、supportedRunnerIds、
compatibility 和 issues，写入 validation.json。Adapter 不自行决定平台状态或运行器兼容性。

## 企业记录：contracts/enterprise.py

enterprise_records(validated) 返回 Iterable[EnterpriseRecord]，不返回裸字典。
可按文件/批次 yield，无需把整套企业记录装入内存。

| kind | 必需标识 | data |
| --- | --- | --- |
| company / person | snapshot、nodeId | attributes 必需；可含 name、label、community、split、properties、sourceRecord |
| edge | snapshot、source、target | 关系类型、权重及证据等 JSON 字段，由 Adapter 解释 |
| hyperedge | snapshot、非空且不重复的 members | 群组类型及证据 |
| event | snapshot、source | 事件字段及证据 |

节点 attributes 是声明特征到有限数值、布尔值、字符串或 null 的映射；不接受嵌套对象/数组。
企业须包含摘要声明的特征，人物不强制使用企业特征集合。保留类别和布尔原值，不强制数值化；
具体模型负责检查能消费的特征类型。额外业务原文及审计信息放 properties，不混入模型输入。
label 只能是整数 0/1 或 null，业务含义由 datasetProfile.target 说明。
不同记录类型不能混用 nodeId、source/target 和 members；缺失身份及非法 JSON 数值立即拒绝。
同快照 ID 唯一性、端点与成员引用、语义保真须由 Adapter 校验；后端导入仍独立检查引用。

示例：

```python
from riskgnn.dataset_adapters.contracts.enterprise import EnterpriseRecord

record = EnterpriseRecord(
    kind="company", snapshot="train", nodeId="000012",
    data={"name": None, "attributes": {"revenue": 120.0}, "label": 0},
)
```

## 公共导出器：enterprise.py

export 接受 registry 的校验结果并返回 EnterpriseExportSummary（format/counts）。
第一行是 EnterpriseManifest：格式、数据契约、源摘要、特征名称和目标定义。
后续逐行序列化 EnterpriseRecord，继续使用 risk-enterprise-data-v1 JSONL 交换格式。
此次没有改 HTTP DTO，也没有额外引入共享 Python 包或让后端导入模型代码。

输出前重新验证类型实例，不能通过 model_construct 或实例修改绕过校验。
企业数须匹配 company_attr，已声明的其他实体数量也必须匹配；未导出的类型不得虚报数量。
输出总大小不超过 512 MiB，单行含换行不超过 1 MiB，与业务导入边界保持一致。
临时文件全部写完并核验后原子替换目标文件；失败删除临时文件，不发布部分成功产物。
错误由既有 CLI 错误协议返回，平台不能将导出失败视为数据校验完成。

## 接入验收

- 缺少 enterprise_records 的 Adapter 不能实例化。
- 摘要缺字段、错误类型、摘要不匹配、重复特征、非法记录和非有限数值应明确失败。
- 导出失败不产生半成品，也不覆盖上一份有效输出。
- 使用真实数据验收 inspect、导出数量、来源摘要、身份及引用、后端解析和 prepare 特征一致性。
- 不改研究脚本的入口、训练方法和数据划分；本契约只约束工作台适配输出。
