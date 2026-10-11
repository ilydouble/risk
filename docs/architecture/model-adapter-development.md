# 适配器开发与 CLI 接入

## 一条依赖方向

```text
工作台 HTTP/Worker → 注册适配器 → 模型目录的 Python 实现或 CLI
```

模型源码仍在 `models/riskgnn`、`models/riskgnn+` 等研究目录，保留原训练命令。
`models/service` 维护服务环境、协议和适配层；研究代码无需导入服务。
适配器与模型源码一起 COPY 到镜像；上传的数据 ZIP 不能提供可执行入口。
本轮不提供任意 shell 命令、动态 import 路径或上传插件。

若模型已经能通过 CLI 接受配置并输出完整产物，适配器可以调用该 CLI；
否则用薄包装补配置翻译、事件和产物导出，不复制模型训练算法。

## 新适配器步骤

1. 在服务 `adapters/<名称>/` 实现 `ModelAdapter`，按需声明支持的操作。
2. `describe()` 返回参数/结果 Schema、输入格式及产物角色；重依赖在执行时导入。
3. `execute()` 校验数据语义，调用模型；自行决定 load/split、训练和评估方法。
4. 通过 `context.emit(...)` 上报枚举事件；在长循环中调用 `check_cancelled()`。
5. 输出可重载产物，返回 `OperationResult`；跨操作只传文件，不共享临时 Python 对象。
6. 在 `adapters/registry.py` 显式注册 ID 与版本，维护服务 uv 依赖和锁文件。
7. 完成契约测试、短训练和独立重载，再开放业务界面；不要只注册名称就标记可训练。

同一适配器可以处理多种数据格式，也可以为新数据提供新的适配器。
工作台不要求所有数据采用 sg-comrisk-v1 或 Bundle v1。

## 本地执行，无需数据库和对象存储

在 `models/` 目录，用服务环境生成一次请求。示例为现有 RiskGNN 的 inspect：

```python
from pathlib import Path
from model_service.adapters.contracts import AssetInput, Operation, OperationRequest
from model_service.execution.artifacts import fingerprint
from model_service.execution.invocation import Invocation

source = Path("/absolute/path/comrisk_export.zip")
call = Invocation(
    adapter_id="riskgnn-node-edge", adapter_version="1.0.0",
    run_id="local-check", attempt_id="1", request_id="local-check",
    directory=Path("/tmp/riskgnn-inspect"),
    request=OperationRequest(
        operation=Operation.INSPECT,
        inputs={"dataset": AssetInput(path=source, sha256=fingerprint(source), format="zip")},
    ),
)
Path("/tmp/adapter-request.json").write_text(call.model_dump_json(indent=2))
```

```bash
uv run --project service python -m model_service.execution.adapter_cli \
  --request /tmp/adapter-request.json
```

每次操作使用新的空输出目录。`request.json` 中的路径应为绝对路径。
CLI 生成 `events.jsonl`、`result.json` 或失败时的 `error.json`；普通 stdout/stderr 只是日志。
`result.json` 包含操作绑定、结果和产物文件清单，只有成功退出且回执有效才算完成。
训练使用 `train`、dataset 输入和 `{"epochs": 2}`；输出目录下的 `model` 作为下一操作输入。
`evaluate` 和 `predict` 使用 model 目录、格式 `riskgnn-model-v1` 及重新计算的目录摘要；
预测参数为 `{"company_ids": ["模型内企业ID"]}`。
旧 `python -m model_service.cli` 命令继续兼容；研究目录的原 CLI 完全保留。

## 工作台内部接口

均位于 `/internal/v1/`，仅允许内部服务令牌调用：

- `POST models/adapters`，Body `{}`：返回精确版本、操作及配置 Schema。
- `POST jobs/submit`：`kind="execute"` 提交一次通用操作。
- 继续通过 jobs/get、jobs/events、jobs/cancel、artifacts/get 查询或取消。

提交例子：

```json
{
  "jobId": "业务操作UUID",
  "kind": "execute",
  "payload": {
    "adapter_id": "riskgnn-node-edge",
    "adapter_version": "1.0.0",
    "operation": "inspect",
    "inputs": {
      "dataset": {"object_key": "uploads/用户/文件.zip", "sha256": "64位摘要", "format": "zip"}
    },
    "parameters": {}
  }
}
```

示例中的 ID、对象路径和摘要需替换为实际值。对象输入下载后验证摘要；目录输入使用 ZIP
传输，安全解压后计算目录摘要。结果记录 data、effectiveConfig 和已上传的 artifacts。
对象凭据留在执行框架中，不传给适配器。

此接口提供执行能力；业务后端仍需检查用户归属、选择流程及映射产品 DTO。
当前前端保留原 RiskGNN 页面；尚未提供根据 Schema 自动生成的通用配置表单。

## 现有流程兼容

`modules/jobs/workflows.py` 将旧 validate/train 请求组合为 inspect、train、evaluate，
再将结果投影到现有页面字段。未携带适配器信息的历史请求固定映射到 v1 适配器，
不会自动选最新版；历史已发布的 v1 模型仍能预测。

RiskGNN 适配器继续使用原网络、采样与优化入口，数据准备沿用现有 smoke-v1。
固定字段、冻结划分、目标抽样和 loss 含义属于该适配器的实现，不属于通用执行器。
Bundle 数据保持分析能力，inspect 会明确报告不兼容当前训练能力。
新模型的有效数据结构、可重载格式和评估意义，由它自己的适配器声明。

## 必要验收

- 不同输入布局能通过同一执行器执行；缺能力、参数或不兼容版本明确失败。
- 缺产物、越界路径、内容损坏、零退出但无结果不能标记完成。
- 短训练后，新进程测试/预测；测试不修改训练产物；批量输入顺序正确。
- 重试不重复训练已封存结果，取消终止进程组，旧 Attempt 不能发布新结果。
- 原研究 CLI 和数值回归通过；工作台使用的依赖升级不改写研究环境。

协议类型详见[执行契约](model-adapter-contract.md)，当前模型包见[RiskGNN 产物](model-artifacts.md)。
