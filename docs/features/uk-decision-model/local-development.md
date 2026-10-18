# UK 决策模型本地加载

## 范围

本入口验证已训练财务版模型的加载与候选评分，不训练、不接数据库、不发布模型。
正式 HTTP 与助手入口见[服务接入](integration.md)。原始结果口径见[全量训练记录](../../architecture/uk-financial-full-training.md)。

JevForge 来自仓库内 [vendor/jevforge](../../../models/vendor/jevforge/UPSTREAM.md)，
通过模型服务 uv 路径依赖安装；开发者不再复制外部源码或手工配置 PYTHONPATH。
默认模型服务及 Docker 使用 CPU Torch，GPU 使用单独的锁定依赖组和部署覆盖。

## 准备模型

协作者日常安装推荐使用[发布包流程](release.md)，可同时校验 LoRA、冻结协议及底座。
以下手工方式保留作初次收取模型时的调试入口，输出 bundleVerified=false。

所有命令从仓库根目录执行。先安装锁定依赖：

```bash
uv sync --project models/service --locked
```

联网时下载固定底座，后续预测不访问 Hugging Face：

```bash
uv run --project models/service --locked hf download Qwen/Qwen3-0.6B \
  --revision c1899de289a04d12100db370d81485cdf75e47ca \
  --local-dir models/weights/uk-financial-0.6b-v1/base
```

将协作者提供的完整 adapter 目录复制到 `models/weights/uk-financial-0.6b-v1/adapter/`。
必须保留 adapter_config.json、adapter_model.safetensors、decision_runtime.json；
tokenizer 等附属文件一并保留。模型按训练加载方式使用固定底座的 tokenizer。
本地权重、下载缓存及运行结果均被 Git 忽略，不提交模型文件。

## 输入与执行

`--input` 支持一个 JSON 对象，或原训练格式的 financial JSONL；`--line` 从 1 开始选择 JSONL 行。
仅序列化 `state.features`，不读取 expected、标签或审计 ID。
输入协议固定在 `models/uk_decision/releases/uk-financial-0.6b-v1/input-contract.json`，
不再读取 UK 适配器的当前特征规则。若输入提供 questions，则必须与固定训练问题一致。
未知字段、非有限值和超出 2048 token
的输入直接失败，不静默补值或截断；零值、负值和币种保留。

最小工程探针如下。它不包含真实企业财务资料，只验证加载，不能用于证明预测质量：

```json
{"state":{"features":{"financial_missing":true}}}
```

保存为本地 `models/weights/uk-financial-0.6b-v1/smoke-input.json` 后执行：

```bash
uv run --project models/service --locked python -m scripts.predict_uk_decision \
  --base models/weights/uk-financial-0.6b-v1/base \
  --adapter models/weights/uk-financial-0.6b-v1/adapter \
  --input models/weights/uk-financial-0.6b-v1/smoke-input.json --device cpu
```

原始两类分数位于 rawProbabilities；未提供校准文件时 calibratedProbabilities 为 null。
有正式 calibration.json 后加 `--calibration /path/to/calibration.json`，不从文档数字补造文件。
输出记录输入及 adapter/runtime 摘要、设备、dtype、token 数、加载与推理时间。
expectedBaseRevision 是此入口约定的底座版本，下载时仍须使用上述固定 revision。

## 独立 CUDA 调试环境

本机 NVIDIA 驱动可用即可运行 Python CUDA；本步骤不安装或重启宿主驱动及 Docker。
从同一锁文件选择 cuda 组，CPU 默认组与其互斥：

```bash
UV_PROJECT_ENVIRONMENT="$PWD/models/runs/uk-decision-cuda/.venv" \
  uv sync --project models/service --locked --no-default-groups --group cuda
```

该环境安装同一份正式服务包与共享底层运行时，CUDA 12.8 库来自已提交的锁文件。
不会修改默认 CPU 虚拟环境，也不影响研究者自己的 requirements 环境。

```bash
models/runs/uk-decision-cuda/.venv/bin/python -m scripts.predict_uk_decision \
  --base models/weights/uk-financial-0.6b-v1/base \
  --adapter models/weights/uk-financial-0.6b-v1/adapter \
  --input models/weights/uk-financial-0.6b-v1/smoke-input.json --device cuda
```

CUDA 默认 bfloat16，CPU 默认 float32；两者都恢复训练保存的运行缓冲区。
改变设备、dtype 或批次后应对照真实验收样本，不宣称与训练服务器逐位一致。
不合并 LoRA、不量化，避免首次部署时增加数值变化来源。

## Docker 验证边界

服务 Dockerfile 在依赖安装层复制 vendor 和共享 uk_decision 小包，再安装正式服务。
镜像已包含 CLI，不再需要挂载根目录 scripts。
CPU 镜像可在 network=none 的临时容器中只读挂载完整模型目录，
以 `python -m model_service.cli predict --model-dir ... --input ... --device cpu` 验证离线评分。
GPU 容器还需宿主 NVIDIA Container Toolkit；现场需提前准备镜像及模型文件。

## 本轮验证

2026-10-18：固定 revision 的 10 个底座文件已对照官方 Git/LFS 摘要，adapter 保留原始字节。
最小缺失财务工程探针在 CPU/float32 与 RTX4060 Laptop/CUDA12.8/bfloat16 均完成评分。
该短输入 CUDA 首次推理约 0.45 秒，峰值 allocated 约 1191 MiB；不作为完整输入吞吐承诺。
CPU 禁网容器的原始两类概率与本机 CPU 完全一致。GPU 与 CPU 概率存在 dtype 数值差异。
已取得同事提供的完整 financial JSONL，并用真实 test 观测完成常驻服务推理。
仍缺少服务器固定参考输出及 calibration.json，尚未验收服务器数值复现和校准结果。
