# 风控工作台 API

Python 3.12 + uv，FastAPI 提供 HTTP，Dishka 管理应用/请求作用域。
认证、企业、图谱、评分和文档按模块分层；目录、信封及日志约定见[后端架构](../docs/architecture/backend.md)。

## 运行与检查

在 `backend/` 执行：

```bash
uv sync --dev
uv run python -m risk_api
uv run ruff check src alembic tests
uv run mypy src/risk_api
uv run pytest -q tests
uv run python -m risk_api.export_openapi
```

本机运行需要对应的数据库等环境配置；Compose 会配置容器间地址并在每次后端启动前执行
`alembic upgrade head`。独立 uv 启动不会自动读取根目录 `.env` 或执行迁移。

## 基准推理

`modules/benchmark/` 仅保留 HTTP、Service、错误映射与加载生命周期。
网络和推理通过本地路径依赖 `../com_risk_model/runtime/` 安装，训练代码和 scikit-learn
不进入后端运行依赖。研究、训练及本地推理命令见[模型工程](../com_risk_model/README.md)。

474 家企业的测试快照位于 `../com_risk_model/data/processed/smesd/test.json`。
下载 Release 模型包后解压到 `../com_risk_model/weights/smesd-v1/`，内含四个文件：
`weights.pt`、`metadata.json`、`metrics.json`、`manifest.json`。
`BENCHMARK_MODEL_VERSION` 选择版本，`BENCHMARK_MODEL_DIR` 和 `BENCHMARK_DATA_PATH` 可显式覆盖。

启动时工作线程校验所选包与测试快照并预计算预测；文件缺失、损坏或不兼容时，仅基准接口
返回 `BENCHMARK_MODEL_UNAVAILABLE` 503。其他接口仍可用，不会自动下载或训练。
后端容器只读挂载整个 `weights/`，模型包不内置于镜像。

```bash
uv run pytest -q --require-model tests/test_benchmark_api.py tests/test_demo_bundle.py
```

普通测试在尚未下载模型时明确跳过 `model_integration`；验收必须使用 `--require-model`。
具体打包、升级与回退方式见[模型产物约定](../docs/architecture/model-artifacts.md)。
