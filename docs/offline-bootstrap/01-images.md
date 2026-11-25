# 1. 在联网机器构建和导出 Docker 镜像

在 Linux x86_64 打包机的仓库根目录打开 Bash。以下命令只构建和导出镜像，可以在没有 GPU 的打包机上执行。先用 `git status --short --branch` 确认将要交付的提交和工作区。构建代理如有需要，按仓库 `.env.example` 设置 `BUILD_*_PROXY` 或 `BUILD_GOPROXY`。

## 构建 GPU 部署使用的全部镜像

```bash
set -euo pipefail
docker version --format '{{.Server.Os}}/{{.Server.Arch}}'
docker compose version
export DOCKER_DEFAULT_PLATFORM=linux/amd64
dc=(docker compose -p risk -f compose.yaml -f compose.gpu.yaml)

"${dc[@]}" config --quiet
"${dc[@]}" pull --ignore-buildable
"${dc[@]}" build
```

基础配置与 GPU 覆盖在构建和运行时都要使用。当前 13 个服务共用 11 个不同的镜像。GPU 覆盖为 `riskgnn` 构建 CUDA 推理镜像，`riskgnn-worker` 继续使用 CPU 镜像校验上传包。数据库和存储的一次性初始化也会使用镜像。只导出正在运行的容器容易漏掉它们。

## 导出并记录版本

接着在同一 Bash 中执行。清单从 Compose 生成，项目名固定为 `risk`，这样自动生成的前端、后端等镜像名和现场一致。

```bash
revision=$(git rev-parse HEAD)
out="$PWD/backup/distributions/$(git rev-parse --short=12 HEAD)"
mkdir -p "$out"
stage="$out/risk-offline"
mkdir "$stage"
printf '%s\n' "$revision" > "$stage/REVISION"

"${dc[@]}" config --images | awk -F/ '$NF !~ /:/ { $0 = $0 ":latest" } { print }' \
  | LC_ALL=C sort -u > "$stage/images.txt"
mapfile -t images < "$stage/images.txt"
for image in "${images[@]}"; do
  platform=$(docker image inspect --format '{{.Os}}/{{.Architecture}}' "$image")
  printf '%-40s %s\n' "$image" "$platform"
  test "$platform" = linux/amd64
done

docker image save "${images[@]}" | gzip -1 > "$stage/images.tar.gz.partial"
gzip -t "$stage/images.tar.gz.partial"
mv "$stage/images.tar.gz.partial" "$stage/images.tar.gz"
ls -lh "$stage/images.tar.gz"
```

若同一提交已有归档，核对 `REVISION` 和清单后即可复用。中断的导出只会留下 `.partial` 文件，可在原暂存目录重跑导出命令。成功标志是 `images.txt` 包含 `risk-riskgnn:cuda-local` 和 `risk-riskgnn:local`，且同目录有通过 gzip 校验的 `images.tar.gz`。

继续[组装离线部署包](02-bundle.md)。
