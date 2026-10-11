# 实验配置与可追溯执行

数据集上传一次，可用不同配置创建多个实验；已有实验不原地修改。
模型侧定义参数、约束、默认值和说明，工作台负责展示、提交、状态及产物。

## 固定信息与实验参数

| 内容 | 归属 |
| --- | --- |
| 数据集 ID/版本、适配器 ID/版本、原有划分 | 上传契约与数据文件，不允许实验覆盖 |
| epochs | 模型训练参数；当前 1–20，默认 2 |
| dataset.target_count | 适配器准备参数；当前 6–20,000 |
| 学习率、batch size、fanout | 当前模型实现固定，表单和 API 不开放 |
| 并发、进程、线程及资源上限 | 服务部署配置 |

target_count 是训练、验证、测试目标的总数，不是训练集单独的大小。
图上下文可能包含额外公司或人物，不能用图节点数代替实际监督目标数。

## 声明与创建

模型 runtime.json 声明训练参数及中英文展示说明；具体适配器的 delivery.json
声明准备参数范围与默认值。模型 CLI 的 configure 操作结合已校验的 datasetContract，
返回 parameterSchema、defaultParameters、uiSchema、configVersion 和 schemaDigest。
它不重新读取大数据文件，也不重新决定 load、split 或构图方式。

默认值顺序：模型/适配器默认 → ZIP adapter.config 默认 → 本次显式参数。
例如包内 target_count=60，实验填 2000，则该实验实际准备参数为 2000。
不修改 ZIP，不要求已有 ZIP 重新打包。打包工具 --set 只影响上传包的默认值。

业务 POST /api/v1/modeling/run-configuration 接收 datasetId，返回 configuration。
创建实验的请求形态：

```json
{
  "datasetId": "数据集 UUID",
  "name": "SMEsD 2000 目标",
  "requestKey": "创建操作 UUID",
  "parameters": {"epochs": 2, "dataset": {"target_count": 2000}},
  "configurationDigest": "表单读到的 schemaDigest"
}
```

configurationDigest 可选；页面始终传入，用于拒绝过期表单。
外层 DTO 从 OpenAPI 生成，动态参数由模型 JSON Schema 校验。
第一版页面仅支持目标数量与轮数两个整数输入，范围与说明读取模型声明。
配置未加载或不合法时不可提交；声明过期时重新加载配置。

业务后端先检查数据集归属和就绪状态，再通过内部 models/configuration 调用模型 CLI。
服务端重新校验后，Run.configuration 和投递记录在一个事务内保存同一份配置。
相同 requestKey、相同输入返回原 Run；变更参数后复用 requestKey 会返回 409。

## 配置快照与执行

每个新实验保存：

- configVersion、schemaDigest：配置协议版本与声明摘要。
- dataset、adapter：不可变数据及适配器身份。
- parameterSchema、defaultParameters、uiSchema：提交时的完整声明。
- requestedParameters：用户显式提交值。
- resolvedParameters：补齐默认并通过校验的最终值。

排队、自动重试和“重新运行”都传递原最终参数，不重新应用当前默认值。
模型 CLI 检查快照摘要、数据身份、请求与快照一致性，以及当前代码的参数兼容性。
仅默认值改变时仍使用原值；范围收窄等导致原配置不兼容时明确失败。
快照和最终参数均进入执行回执绑定，不同 target_count 不得复用旧产物。

训练完成后，metadata.json 保存 configuration、effectiveConfig 和 actualCounts。
CLI effective_config、任务 effectiveConfig 与实验 resolvedParameters 保持一致。
实际规模分别记录 targets、train、validation、test；不足请求数量时显示真实数量。
例如请求 4000，而数据仅有 3976 个可用目标，两者分别展示。

## 重新运行、修改与历史记录

- “重新运行”：复制原声明和最终配置，新建 Run 并记录 retryOf。
- “复制并修改配置”：打开原最终值预填的表单，按当前声明校验后新建 Run。
- 原 Run 的参数、日志与权重不改变；发布仍绑定通过独立测试的模型包。
- 历史 Run 没有完整快照时页面明确标注；历史轮数和 ZIP 默认值仍可用于新建运行，
  不宣称补齐了历史执行时的全部配置。新 Run 才开始保存完整快照。

本次无需数据库迁移，已有 JSONB 配置列承载快照。创建实验 API 的顶层 epochs
改为 parameters.epochs；前后端应一起部署，旧 ZIP、已保存数据及模型文件保留。
