# 单模型 CLI 执行协议 v2

## 边界

工作台负责身份、输入传输、进程、租约、状态、事件持久化与产物上传。
RiskGNN CLI 负责调用数据适配器、训练、独立测试和预测。
configure 操作读取已校验的数据契约，返回模型声明的实验参数、默认值和解析快照；
不读取数据文件、不训练。提交配置及重试语义见[实验配置](experiment-configuration.md)。
当前只部署一个模型 RiskGNN；研究脚本及环境继续由模型开发者维护。
服务不导入 RiskGNN、Torch、数据适配器或训练代码。

```text
model-service → python -m riskgnn.workbench_cli --request request.json
                       ├── dataset_adapters/
                       ├── training_engine.py
                       └── workbench/ 中的产物、评估和预测
```

服务不再定义 ModelAdapter 类。接口描述来自模型维护的 `models/riskgnn/runtime.json`，
服务中的 `execution/contracts/` 只描述执行消息，按 spec/io/events/errors 等职责分文件。
Docker 同时打包服务与模型源码；`MODEL_CODE_ROOT=/app/models` 指定模型根目录。

## 请求与结果

每次操作在独立进程运行。请求记录：

- `contract_version=2`、`runtime_id="riskgnn"`、`runtime_version="2"`。
- Run/Attempt/Request ID、绝对工作目录、CPU 资源提示。
- `request.operation`：configure、inspect、train、evaluate 或 predict。
- 按角色传递 `inputs`：本地路径、格式、SHA-256。
- 模型声明的 `parameters`；有 `configuration` 快照时保持最终值，否则按声明补齐默认。

输入文件按只读约定使用。文件摘要为字节 SHA-256；目录摘要为排序的文件清单 JSON 摘要，
每项记录相对路径、长度及文件 SHA-256。目录摘要与传输 ZIP 摘要分别记录。

CLI 写 `operation-result.json`，包含小型 JSON data、effective_config 和产物角色/相对路径/格式。
服务独立检查输入与结果、产物安全和摘要，再写 `result.json` 成功回执。
退出码为 0 但没有合法结果仍算失败；stdout/stderr 只作为诊断日志。
大结果写文件，JSON 摘要限制为 1 MiB；拒绝越界路径、链接、空产物或缺失必需角色。

各操作不共享 Python 内存。训练产物封存后不可修改，evaluate 输出独立报告。
同一镜像不意味着自动拥有可重载产物；模型 CLI 负责完整保存和加载模型状态。

## 事件

`execution/contracts/events.py` 定义 `EventKind` 枚举和对应数据：

| 枚举 | 内容 |
| --- | --- |
| STAGE / stage | 阶段名称、说明 |
| PROGRESS / progress | current、可空 total、unit |
| LOG / log | LogLevel 与 message |
| METRIC / metric | name、数值 value、可选 step/group/unit |

CLI 通过 `events.jsonl` 输出；框架校验后分配递增序号并持久化。
阶段由模型定义，框架不根据阶段名控制训练算法。
queued/running/completed/failed/cancelled 由工作台维护，作为平台 state 事件。

## 错误、取消与恢复

CLI 失败写 error.json：code、message、可选 path、retryable。
数据/参数错误不重试；进程崩溃不自动被当作临时网络故障。
传输故障可复用完整操作结果；任务回执绑定模型版本、输入、参数和资源。
复用前后均校验文件，复制到新 Attempt，旧租约不能覆盖新结果。
取消先通知进程，再按超时终止整个进程组。

这是可信仓库代码的执行协议，不是运行上传 Python 的沙箱。
命令由服务固定构造，清单和 API 均不能传入任意执行入口。

## 内部 HTTP

- `models/runtime`：单模型操作、输入和参数声明。
- `models/configuration`：对已校验的数据集查询并解析实验参数，调用模型 configure 操作。
- `jobs/submit` 的 `kind=execute`：指定当前 runtime 和单次操作；对象引用由服务下载。
- 页面所用 validate/train 由 jobs/workflows.py 组合 inspect、train、evaluate 并投影显示字段。
- jobs/get、jobs/events、jobs/cancel、artifacts/get 继续管理生命周期。

外部用户只访问业务后端，由业务后端校验数据归属。
数据协议见[ZIP 契约](dataset-contract.md)，模型侧扩展见[数据适配器](dataset-adapters.md)。
