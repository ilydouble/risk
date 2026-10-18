# UK 财务模型发布与安装

所有命令从仓库根目录执行。本次人为约定的基线为 `uk-financial-0.6b-v1`，
不引入发布状态、基线状态或相应检查。`release.json` 仅记录下载位置和文件摘要。

## 同一个 Release 的附件

tag 约定为 `model-uk-financial-0.6b-v1`，上传以下三个文件：

| 文件 | 内容 |
| --- | --- |
| `uk-financial-0.6b-v1.tar.gz` | 完整 LoRA、运行状态、校准、冻结协议、manifest、模型说明及验收输入 |
| `uk-financial-20261018.zip` | 127,646 条财务观测、企业索引、来源清单与工作台契约 |
| `uk-financial-0.6b-v1.tar.release.json` | 两个附件的文件名、大小、SHA-256 和模型 manifest 摘要 |

Qwen3-0.6B 底座不上传 Release。安装工具从公开的
[固定 Hugging Face revision](https://huggingface.co/Qwen/Qwen3-0.6B/tree/c1899de289a04d12100db370d81485cdf75e47ca)
下载 manifest 列出的十个文件，并沿用现有完整性检查。
底座 URL 同时注明在 `scripts/uk-decision`，实际仓库和 revision 由模型版本定义提供。

模型包内保留 adapter 原始七文件；`decision_runtime.json` 与权重配套，不能省略。
根目录包含 `calibration.json`、`input-contract.json`、`manifest.json`、`README.md` 和 `acceptance/`。
校准原件包含温度及训练期 4,046 个样本的审计信息；运行只读取温度。

## 准备发布附件

已有配套数据 ZIP 时直接使用；从同事提供的 full 目录重新打包：

```bash
./scripts/package-dataset --preset uk-financial \
  --data-dir /path/to/full --dataset-version 20261018
```

然后一次准备模型、数据和下载清单：

```bash
./scripts/uk-decision package \
  --adapter /path/to/adapter \
  --dataset models/runs/datasets/uk-financial-20261018.zip \
  --output models/runs/releases/uk-financial-0.6b-v1.tar.gz
```

`adapter/calibration.json` 默认一起读取，也可显式传 `--calibration /path/to/calibration.json`。
未知附加文件、修改过的原始 adapter 和已有输出会明确报错。
模型包重复构建的字节相同；数据 ZIP 按原始字节复制，不重新压缩或改变划分。
打包检查复用财务 Adapter 的文件清单；字段、索引、标签的全量校验仍在工作台上传时执行。
工具仅生成本地附件，不上传 Release、不创建 tag。

## 发布

1. 将附件旁 `.release.json` 的内容同步至 Git 中该版本的 `release.json`，提交对应代码。
2. 推送代码，在对应代码提交创建 `model-uk-financial-0.6b-v1` tag。
3. 创建同名 GitHub Release，上传上述三个附件。
4. 用一套空目录执行下方安装命令，完成下载、解压和启动验收。

发布后无需再改任何状态字段。下载工具直接请求固定仓库、tag 和附件名，
Release 不存在或无访问权限时返回实际下载错误。附件修改应形成新的模型版本。

## 同事安装

```bash
./scripts/uk-decision install --with-base
```

安装前准备 uv 和 GitHub CLI；私有仓库需 `gh auth login`。脚本使用模型服务的锁定环境，
目前支持 Linux x86_64；首次执行会下载 Python 依赖。无需安装训练数据处理用的研究环境。

默认结果：

- `models/weights/uk-financial-0.6b-v1/`：可直接只读挂载的完整模型，含 `base/`。
- `datasets/uk-financial-20261018/`：解压的数据文件。
- `datasets/uk-financial-20261018.zip`：可直接上传工作台的原始 ZIP。

自定义目录使用 `--destination` 和 `--dataset-destination`；相对路径按调用时的目录解释。
`--base-from` 可代替 `--with-base` 复用本机已有的固定底座；已正确安装的模型和数据可重复安装。
本地修改过的数据、其他模型或未管理目录不会被覆盖。
不带底座选项时仍安装模型包与数据，运行推理前需要另行准备底座。

Release 上传前或无网络时，使用同一批本地附件：

```bash
./scripts/uk-decision install \
  --assets-dir models/runs/releases \
  --base-from /path/to/verified/base
```

同一条安装逻辑处理本地和远程附件，不维护两套发布流程。

## 离线现场

联网时完成安装和镜像构建，再传完整模型目录、财务数据 ZIP、Compose、配置和镜像。
使用 `docker image save`/`load` 搬运镜像，启动时加 `--no-build --pull never`。
模型服务启动不下载权重；首次运行 `scripts/uk-decision` 或 uv 的环境准备也要提前完成。
具体启动和验收见 [bootstrap.md](bootstrap.md)，当前已验证 CPU/float32 和 CUDA/bfloat16。
