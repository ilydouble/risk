# 2. 组装离线部署包

在第 1 步的仓库根目录操作。磁盘需同时容纳 Docker 本地镜像、镜像导出文件、暂存权重和最终 TAR。可用 `df -h .` 与 `docker system df` 查看实际空间。

## 准备并验证完整财务模型

新打包机先运行以下命令。它从 GitHub Release 取得 LoRA 和配套数据 ZIP，从 Hugging Face 取得固定 revision 的 Qwen3-0.6B 底座。本机已有完整安装时，直接执行校验即可。

```bash
./scripts/uk-decision install --with-base
```

```bash
set -euo pipefail
model=models/weights/uk-financial-0.6b-v1
./scripts/uk-decision verify --model-dir "$model" --base "$model/base"
```

成功输出包含 `base verified: True`。整份模型目录包含 `base/`、`adapter/`、`acceptance/`、`calibration.json`、`input-contract.json` 和 `manifest.json` 等文件。推理服务启动时会从只读挂载加载并预热模型。

## 合并部署文件并封包

在同一个 Bash 中执行。部署配置取自构建镜像时记录的提交，文件按 Compose 挂载所需的相对路径放置。正式数据和运行凭据单独交接。

```bash
out="$PWD/backup/distributions/$(git rev-parse --short=12 HEAD)"
stage="$out/risk-offline"
revision=$(cat "$stage/REVISION")
test "$revision" = "$(git rev-parse HEAD)"
test -s "$stage/images.tar.gz"

git archive "$revision" -- compose.yaml compose.gpu.yaml .env.example \
  infra/postgres/model-init.sh infra/neo4j/init.sh infra/rustfs/init.sh \
  docs/offline-bootstrap | tar -x -C "$stage"

mkdir -p "$stage/models/weights"
cp -aL "$model/." "$stage/$model/"
./scripts/uk-decision verify --model-dir "$stage/$model" --base "$stage/$model/base"

(
  cd "$stage"
  docker compose --env-file .env.example -p risk -f compose.yaml -f compose.gpu.yaml config --quiet
  tar -cf "$out/risk-offline.tar.partial" REVISION images.txt images.tar.gz \
    compose.yaml compose.gpu.yaml .env.example infra models/weights/uk-financial-0.6b-v1 \
    docs/offline-bootstrap
)
mv "$out/risk-offline.tar.partial" "$out/risk-offline.tar"
(cd "$out" && sha256sum risk-offline.tar > risk-offline.tar.sha256)
ls -lh "$out"/risk-offline.tar*
```

`cp -aL` 会复制链接指向的实际权重，比赛机无需打包机的模型缓存目录。镜像归档已压缩，外层 TAR 用于将文件和目录一起搬运。交付时保留下面两个文件的原名，以便在比赛机直接核对摘要。

- `risk-offline.tar`
- `risk-offline.tar.sha256`

部署文件可以用移动介质搬运。有 SSH 连接时，可将两个文件一起传到管理员主目录。

```bash
scp "$out/risk-offline.tar" "$out/risk-offline.tar.sha256" user@competition-server:~/
```

数据另按[数据集交付](03-dataset.md)准备。管理员从[现场启动与验收](04-onsite.md)开始操作。
