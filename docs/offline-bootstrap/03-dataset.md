# 3. 单独打包与交接财务数据集

有两种起点。使用本次发布的财务数据时选 A，取得新一版符合财务协议的源目录时选 B。最终都交给演示浏览器一个带 `risk_dataset_contract.json` 的 ZIP。数据负责人在联网准备阶段运行以下命令。

## A. 已有发布数据 ZIP

从仓库根目录执行。第 2 步的安装命令已将发布附件放在 `datasets/`。保留原始 ZIP 字节即可。

```bash
set -euo pipefail
delivery="$PWD/backup/distributions/datasets"
zip_name=uk-financial-20261018.zip
mkdir -p "$delivery"
cp "datasets/$zip_name" "$delivery/$zip_name"

# 从仓库内的发布清单读取已知摘要
release=models/uk_decision/releases/uk-financial-0.6b-v1/release.json
python3 -c 'import json, sys; d=json.load(open(sys.argv[1]))["dataset"]; print(d["sha256"], d["asset"], sep="  ")' \
  "$release" > "$delivery/$zip_name.sha256"
(cd "$delivery" && sha256sum -c "$zip_name.sha256")
```

预期看到 `uk-financial-20261018.zip: OK`。该版本有 127,646 条财务观测，同一家企业可有多个月份。

## B. 用新版本源目录生成 ZIP

当前财务模型使用 `uk-financial` 打包预设，对应适配器 `uk-financial-jsonl / 1`。让数据提供方交付下表五个文件。打包器会收集输入目录中的文件，准备一个仅含本次交付文件的目录，输出放在目录外。

| 输入文件 | 用途 |
| --- | --- |
| `manifest.json` | 来源格式 `uk-labelled-decisions-v1`、目标定义、文件字节数与摘要 |
| `sample-index.jsonl` | 将 split、行号、企业编号和观测月份关联 |
| `train.financial.jsonl`、`valid.financial.jsonl`、`test.financial.jsonl` | 三个已有划分的财务观测 |

将 `data_dir` 和 `version` 换成本次交付值，再从仓库根目录打包。

```bash
set -euo pipefail
data_dir=/path/to/financial-observations
version=competition-v2
delivery="$PWD/backup/distributions/datasets"
zip_name="uk-financial-$version.zip"
mkdir -p "$delivery"

./scripts/package-dataset --show-preset uk-financial
./scripts/package-dataset --preset uk-financial \
  --data-dir "$data_dir" --dataset-version "$version" --output "$delivery/$zip_name"
(cd "$delivery" && sha256sum "$zip_name" > "$zip_name.sha256")
```

打包器会检查目录、必需文件、预设和归档限制，生成包内契约，遇到同名输出会停止。现场上传后，Worker 还会全量校验字段、文件摘要、标签和观测索引。若拿到的是 Companies House 原始 CSV 或旧 UK 七维图数据，需先完成财务观测转换或确认适用的适配器。改文件名或加一个 ZIP 契约无法补齐财务输入。

**如果到场才收到这五个源文件**，可以在导入部署镜像后调用 CPU Worker 镜像内的同一个打包器。容器只读挂载输入目录，生成的 ZIP 会出现在宿主机的 `upload-packages/`。

```bash
set -euo pipefail
data_dir=/absolute/path/to/financial-observations
delivery="$PWD/upload-packages"
version=competition-v2
zip_name="uk-financial-$version.zip"
mkdir -p "$delivery"
docker run --rm --pull never --network none --user "$(id -u):$(id -g)" \
  -v "$data_dir:/input:ro" -v "$delivery:/output" --entrypoint python risk-riskgnn:local \
  -m riskgnn.dataset_adapters.package_dataset --preset uk-financial \
  --data-dir /input --dataset-version "$version" --output "/output/$zip_name"
(cd "$delivery" && sha256sum "$zip_name" > "$zip_name.sha256")
```

## 交给演示电脑

把选定的 `.zip` 和同名 `.zip.sha256` 放在演示电脑的同一个目录。对于发布附件，在该目录执行以下校验。

```bash
sha256sum -c uk-financial-20261018.zip.sha256
```

新版本相应替换文件名。显示 `OK` 后保留 ZIP 原样，由浏览器在工作台选择该文件上传。当前上传上限为 512 MiB，解压总量上限为 2 GiB。后续按[现场启动与验收](04-onsite.md)完成校验、企业导入和推理。
