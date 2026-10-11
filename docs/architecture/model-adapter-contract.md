# 模型适配器执行契约 v1

## 边界

工作台负责身份、资产传输、执行进程、租约、状态、事件持久化和产物上传。
适配器负责识别数据、load/split、特征/构图、训练、测试及模型重载。
不要求不同数据集遵守同一张表、固定特征、划分或模型包内部结构。
同事继续使用研究目录原来的 requirements、Python/CUDA 环境和脚本。

协议是 `model_service/adapters/contracts/` 内部模块，随服务镜像安装，暂无独立包。

| 文件 | 职责 |
| --- | --- |
| `base.py` | `ModelAdapter` 抽象类 |
| `spec.py` | 操作枚举、能力、参数/结果 schema、输入/产物声明 |
| `io.py` | 操作请求、资产、结果与产物引用 |
| `events.py` | 事件枚举和事件数据 |
| `context.py` | 执行上下文和取消检查 |
| `errors.py` | 结构化异常与取消异常 |
| `validation.py` | 契约检查、默认参数合并 |
| `common.py` | JSON 值与基础 Pydantic 配置 |

## 最小接口

```python
class ModelAdapter(ABC):
    @classmethod
    @abstractmethod
    def describe(cls) -> AdapterSpec: ...

    @abstractmethod
    def execute(
        self, request: OperationRequest, context: ExecutionContext
    ) -> OperationResult: ...
```

`describe()` 不加载数据、权重或计算库。声明稳定 ID、适配器版本、协议版本及支持的操作。
`Operation` 提供 `inspect/train/evaluate/predict`；适配器可以只实现其中一部分。
每个操作声明输入角色、格式、参数 JSON Schema、默认参数、结果 Schema 和产物角色。
Schema 使用 JSON Schema 2020-12，只允许文档内 `$ref`；`ui_schema` 为可选展示提示。
递归合并默认参数后校验，不隐式执行 JSON Schema 中的 default 或类型转换。

新增兼容性不同的参数、数据处理或模型行为时，发布新的适配器版本。
任务使用精确版本，不自动选择最新版或回退到另一个适配器。

## 输入、上下文与输出

- `OperationRequest`：操作、按角色命名的 `inputs`、适配器自己的 `parameters`。
- `AssetInput`：本地路径、SHA-256、格式标识。原始文件和模型目录均可作为输入。
- 文件摘要为文件字节 SHA-256；目录摘要为排序后的文件清单 JSON 摘要，
  清单项包含相对路径、长度、文件摘要。它与对象传输 ZIP 的字节摘要分别记录。
- `ExecutionContext`：Run/Attempt/Request ID、工作目录、输出目录、device/resources、
  `emit()` 与 `check_cancelled()`；不提供 HTTP Request、数据库或对象存储客户端。
- `OperationResult`：小型 JSON `data`、实际使用的 `effective_config`、按角色声明的产物。
  JSON 上限 1 MiB；大表、预测全集和权重写为文件。
- 产物只声明输出目录内相对路径及格式，框架计算长度、摘要、打包和上传。
  拒绝缺失、越界、符号链接、特殊文件、类型/格式不符及未声明的产物角色。

输入按只读约定使用，执行前后复核摘要；中间文件写入工作目录。
这是可信仓库代码的协作契约，不是运行不可信 Python 的安全沙箱。
跨操作只传递文件产物，不依赖上一个 Python 进程的对象或全局状态。
训练产物封存后不再修改；独立测试写新的报告产物并记录被测模型摘要。

## 事件

`events.py` 的 `EventKind` 明确列出四种枚举：

| 枚举 | 数据 |
| --- | --- |
| `STAGE` / `stage` | stage、message；阶段名由适配器定义 |
| `PROGRESS` / `progress` | current、可空 total、unit |
| `LOG` / `log` | `LogLevel` 枚举和 message |
| `METRIC` / `metric` | name、数值 value、可选 step/group/unit |

事件值拒绝 NaN/Infinity；已知 total 时 current 不得超过它。
示例：`MetricEvent(name="loss", value=0.42, step=1, group="validation")`。
阶段只用于展示，不用于控制模型执行或判定成功。
`queued/running/completed/failed/cancelled` 由工作台维护，保存为平台 `state` 事件；
适配器不能上报这些任务状态作为自己的事件。

## 失败与恢复

`AdapterError(code, message, path=..., retryable=False)` 使用稳定机器码，path 为可选字段路径。
数据/配置错误默认不重试；明确的临时故障才声明 retryable。
框架异常和子进程退出单独分类，不依赖日志文本判断错误原因。
子进程正常退出但没有有效结果也算失败，不能将打印日志当成成功结果。

框架为每次操作保存绑定输入摘要、版本、参数和资源配置的结果回执及产物清单。
跨 Attempt 仅复用通过绑定与文件校验的结果；复制到当前 Attempt 后再次复核。
上传失败可复用已完成的训练/测试，缺失或损坏的结果重新计算。
取消由上下文协作检查和进程组终止共同保证，租约 fencing 防止旧执行者覆盖新结果。

具体接入见[适配器开发与 CLI](model-adapter-development.md)。
