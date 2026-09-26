# 模型工程与产物

## 代码边界

`com_risk_model/training/` 负责训练、拟合、预训练、消融与导出；`testing/` 是开发者主动执行的
校验、推理、解释和评估入口，`tests/` 专用于自动化测试。网络与推理实现只在
`runtime/src/com_risk_runtime/` 维护，训练、测试工具与后端共同安装这个包。

模型工程是 uv 工具项目，不构建训练 wheel；runtime 独立构建 wheel。
模型工程与后端分别维护锁文件和 `.venv`，通过 uv 本地路径依赖安装 runtime。
runtime 依赖 Torch、NumPy、Pydantic；scikit-learn 和离线指标计算留在模型工程。
两个消费项目的专用索引仅对 Torch 生效，Linux/Windows 使用 CPU 构建；本轮沿用既有锁定版本。

```text
com_risk_model/
  training/, testing/, tests/
  runtime/pyproject.toml, runtime/src/com_risk_runtime/
  data/processed/smesd/test.json     # Git 跟踪，474 家企业
  runs/                            # 忽略：实验、检查点、exports
  weights/<版本>/                  # 忽略：手工下载的正式模型
  docs/                            # 研究文档、历史实验和来源
```

## Release 包契约

包内顶层目录是模型版本，每个版本恰好提供以下四个文件；测试快照独立随仓库发布：

| 文件 | 内容 |
| --- | --- |
| `weights.pt` | CPU 可加载的 state_dict，使用 `weights_only=True` |
| `metadata.json` | 格式 2；网络、特征顺序、预处理、先验、阈值、校准及数据哈希 |
| `metrics.json` | 保存的模型/基线评估、训练曲线与解释边界 |
| `manifest.json` | 清单版本 1、runtime API 版本 1、模型版本、三个文件的字节数和 SHA-256 |

清单的 `snapshot` 记录数据集名称、企业数、原始字节数和 SHA-256；元数据还保留训练时的
规范化测试快照哈希。校验两者以确认产物和快照对应。
清单文件路径必须是包内三个约定文件名，拒绝绝对路径、穿越目录、重复条目与包外符号链接。
运行时只读所选目录自己的清单，不依赖历史 `backend/` 路径。

## 导出与下载

在模型工程中完成训练并选定实验后：

```bash
cd com_risk_model
uv run python -m training.cli export --run runs/smesd-v1/no_hyper-seed42 \
  --version smesd-v1 --data data/processed/smesd/test.json
```

导出检查完整性、格式与数据对应关系，加载网络并完成一次推理，再写入
`runs/exports/smesd-v1/` 和 `runs/exports/smesd-v1.tar.gz`。已有版本拒绝覆盖。
开发者手工上传压缩包为 GitHub Release 附件；本轮没有创建 Release 或实现自动下载。
取得附件后，在仓库根目录解压并校验：

```bash
tar -xzf /path/to/smesd-v1.tar.gz -C com_risk_model/weights
cd com_risk_model
uv run python -m testing.cli validate --model weights/smesd-v1 \
  --data data/processed/smesd/test.json
uv run pytest -q --require-model -m model_integration
```

只能使用来源可信的附件；哈希能验证文件对应关系，不能替代发布者身份确认。

## 后端与 Docker

- `.env` 的 `BENCHMARK_MODEL_VERSION=smesd-v1` 选择 `weights/` 子目录。
- `BENCHMARK_MODEL_DIR`、`BENCHMARK_DATA_PATH` 可显式覆盖；容器中填写容器路径，
  本机 uv 启动时填写本机路径。显式目录的清单版本必须与 `BENCHMARK_MODEL_VERSION` 一致。
- Compose 的 `.env` 供变量替换使用；本机直接运行 uv 时需自行导出所需环境变量。
- 后端与 `demo-seed` 从根目录构建，通过 `backend/Dockerfile.dockerignore` 限制上下文。
  镜像只有后端、runtime、迁移/企业种子和测试快照，没有训练代码、实验输出或权重。
- 仅 backend 将 `com_risk_model/weights/` 整体只读挂载到 `/app/com_risk_model/weights/`。
  `demo-seed` 不加载基准模型，也不挂载权重。
- FastAPI 启动时在专用工作线程校验、加载并预计算预测。缺失、损坏或不兼容仅使基准 API
  返回既有 503；日志含选定版本、目录和原因。不会回退到其他版本、下载或训练。

升级时保留旧版本目录，下载新包并完成校验，在 `.env` 切换版本，再执行：

```bash
docker compose up -d --no-deps --force-recreate backend
```

这会应用环境变量并重载模型。回退时切回旧版本并重新创建后端，无需修改数据库。
仅替换模型包不需要重建镜像；runtime 代码或依赖改变时需重新构建。

## 验证边界

后端保留 API、信封、加载失败隔离与独立目录加载测试；模型工程测试算法、短训练、导出和
产物校验。真实模型回归标记为 `model_integration`；普通测试在未下载模型时明确跳过，
半个模型包或损坏文件会失败。验收使用 `--require-model`，缺失或无效产物在测试开始前报错。
完整训练/验证数据未下载时，只跳过该数据集的划分检查，不影响合成训练和真实模型推理验收。
