# 数据交付：选择预设并打包

日常上传者不需要编写 JSON，也不用安装 Torch、FastAPI 或数据库依赖。
首次接入由模型开发者和数据负责人确认预设，之后每次只需选择数据目录并填写版本。

## 1. 谁确定哪些值

| 信息 | 维护者 | 日常打包 |
| --- | --- | --- |
| adapter ID / version、必需文件、config 约束 | 适配器开发者 | 从声明读取，不按文件名猜测 |
| dataset ID / name、预设配置 | 数据负责人和适配器开发者 | 选择预设后复用 |
| dataset version | 数据提供方 | 每次交付填写 |
| data-dir / output | 打包者 | 填数据目录；输出位置可选 |

`dataset.id` 与 `adapter.id` 独立；同一个适配器可以为多个数据集建立预设。
当前预设：

| preset | dataset.id | adapter | 默认 target_count |
| --- | --- | --- | --- |
| acra-companies | acra | sg-comrisk / 1 | 2000 |
| smesd | smesd | smesd / 1 | 4000 |
| uk-companies | uk-companies | uk-dataset-v1 / 1 | 2000 |

这些值分别保存在 [ACRA](acra/delivery.json)、[SMEsD](smesd/delivery.json)、
[UK](uk_dataset_v1/delivery.json) 的 `delivery.json`，与各自代码和 README 一起维护。
数据负责人要交付另一个企业群体时新增预设，不需要复制适配器代码。

## 2. 固定入口与轻量环境

安装 uv 并加入 PATH，拉取仓库后，从仓库根目录执行（Bash 环境）：

```bash
./scripts/package-dataset --list-presets
```

脚本使用 uv 准备 Python 3.12 及 packaging-requirements.txt 中的轻量依赖，首次可能需要下载。
无需定义 Shell 函数或安装模型服务环境；默认入口仅依赖标准库和 jsonschema。
启动脚本只处理环境、模块定位和参数转交，保留 Python CLI 的错误与退出状态。
预设、文件要求和配置全部由适配器声明，启动脚本不维护另一份映射。

显式提供的 --data-dir、--output、--validation-python 均相对于**执行命令时的目录**。
从其他目录也可用启动脚本的绝对路径调用；脚本不会把当前目录切换到 models/。

## 3. 查看预设，交付本次版本

```bash
./scripts/package-dataset --show-preset uk-companies

./scripts/package-dataset \
  --preset uk-companies --data-dir datasets/uk_dataset_v1 --dataset-version 2026-10-20
```

只要求 --preset、--data-dir、--dataset-version；--output、--set 和 --json 可选。
`--show-preset` 展示绑定身份、默认配置、必需文件、配置 Schema 及输出规则。
`--data-dir` 精确表示一套数据的根目录，不递归猜测数据集类型。
ACRA 选择 `comrisk_export_v5/acra`；SMEsD 选择 `comrisk_export_v5/smesd`。
已有 ZIP 请先解压，再指定目录；旧 `tools.package_dataset --input ...` 入口已移除。

省略 --output 时输出到仓库 models/runs/datasets/<预设>-<版本>.zip，不受当前目录影响。
上例输出 models/runs/datasets/uk-companies-2026-10-20.zip。
默认文件名的预设与版本以英文字母或数字开头，仅含字母、数字、点、下划线、连字符；
其他版本名称可以保留，通过 --output 显式指定文件路径即可。

默认显示中文摘要：数据集/版本、适配器、契约生成、配置、文件数量、大小、校验级别和下一步。
自动化调用添加 --json，标准输出保留详细 JSON，包括默认配置、本次覆盖及完整校验报告。
--list-presets 与 --show-preset 也支持 --json；错误写入标准错误并返回非零退出状态。
默认检查目录、必需文件、配置、契约及 ZIP 资源限制；**不扫描表内容，也不训练**。
文件缺失会在压缩前列出具体名字，例如 `valid.json, test.json`。
输出不能在数据目录中，也不能覆盖已有文件；遇到同名文件换版本或指定 --output，源目录不会被修改。

## 4. 可选参数覆盖

```bash
./scripts/package-dataset \
  --show-preset uk-companies --set target_count=60

./scripts/package-dataset \
  --preset uk-companies --data-dir datasets/uk_dataset_v1 \
  --dataset-version smoke-20261020 --output /tmp/uk-smoke.zip --set target_count=60
```

覆盖优先级：适配器默认配置 → 预设配置 → 本次 `--set KEY=JSON`。
仅接受配置 Schema 允许的字段与值，重复覆盖同一参数报错。
当前只开放整数 target_count，范围 6–20,000；新适配器可在自己的声明中定义其他参数。
未指定覆盖时自动写入全部已预填配置，便于之后追溯。
适配器 ID/version 与数据集 ID 不能临时覆盖；需要改变绑定时修改或新增经过审核的预设。

## 5. 按需执行完整校验

全量字段、标签、划分、图引用和分析需要模型环境，由独立进程执行 inspect，不训练。
已有服务开发环境时可指定其 Python；打包环境仍保持轻量：

```bash
./scripts/package-dataset \
  --preset uk-companies --data-dir datasets/uk_dataset_v1 \
  --dataset-version 2026-10-20 --output /tmp/uk-verified.zip \
  --validate --validation-python models/service/.venv/bin/python
```

完整校验解释器需已有模型依赖；固定启动器的轻量环境不包含这些依赖。
校验失败不会发布输出 ZIP；通过后摘要为 `validation=full`，附带数据规模与兼容性。
默认 `validation=packaging-only` 只表示打包检查成功，不能作为数据有效或训练可用的证明。
上传后 Worker 仍会独立全量校验，不信任本地摘要来跳过服务端校验。

## 6. 契约如何进入 ZIP

工具根据预设和本次数据版本生成根目录 `risk_dataset_contract.json`，并用权威 Schema 校验。
适配器版本来自声明，不再固定为 1。ZIP 中仍只有一个契约，保留独立上传和追溯能力。
源目录若已有根契约，工具忽略它、重新生成包内契约，并在摘要标记 `sourceContractIgnored=true`；
源文件原样保留。嵌套目录出现第二个契约则拒绝，避免混入另一套数据。

源目录的普通文件全部打包，含说明附件；包内 Python 不执行。
限制与上传侧一致：ZIP 512 MiB、解压 2 GiB、单文件 1 GiB、成员 128 个；拒绝链接和越界路径。

## 7. 新预设与脚本调用

适配器开发者在自己的目录维护 `delivery.json`：

- adapter：代码注册的 ID 与版本；required_files：相对数据根目录的必需文件。
- config_schema / default_config：允许的参数及默认值，适配器与打包器共同读取。
- presets：每项有 dataset（ID、可选 name/description）、description、可选 config。
- 声明通过 [delivery.schema.json](delivery.schema.json) 校验；重复预设或适配器身份拒绝。

工具仅发现仓库中 `*/delivery.json`，不读取数据目录中的预设或动态导入上传代码。
新增预设无需修改打包器映射表；新增适配器仍须按 [接入指南](README.md) 注册、验收并部署。

导出脚本也可以直接调用同一逻辑（从 `models/` 运行或在环境中提供该模块）：

```python
from pathlib import Path
from riskgnn.dataset_adapters.packaging import package

summary = package(
    data_dir=Path("/path/to/export"), output=Path("/tmp/new-version.zip"),
    preset="uk-companies", dataset_version="2026-10-20",
)
print(summary["validation"], summary["output"])
```

最后到 `/modeling` 上传 ZIP，等待校验 ready，再创建实验、测试、发布和下载。
新适配器代码必须先部署到模型 HTTP 服务与 Worker；仅交付清单不能安装代码。
