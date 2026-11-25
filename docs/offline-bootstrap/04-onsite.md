# 4. 比赛机启动与业务验收

管理员准备 `risk-offline.tar` 和 `risk-offline.tar.sha256`。演示电脑准备单独交付、已核对摘要的数据 ZIP。比赛机只需访问内网的 Qwen3.6-35B 接口。以下服务器命令使用 Bash，按顺序在同一终端执行。

## 校验并导入镜像

进入两个部署文件所在的目录。在首次安装时创建新的解包目录，后续重启继续使用原目录和 `.env`。

```bash
set -euo pipefail
docker version --format '{{.Server.Os}}/{{.Server.Arch}}'
docker compose version
nvidia-smi -L
df -h .
docker system df

sha256sum -c risk-offline.tar.sha256
mkdir risk-offline
tar -xf risk-offline.tar -C risk-offline
cd risk-offline
cat REVISION
docker image load -i images.tar.gz
while IFS= read -r image; do
  docker image inspect --format '{{.Os}}/{{.Architecture}} {{.Id}}' "$image"
done < images.txt
```

预期为 `linux/amd64`，宿主机能看到 A100，清单中的每个镜像都能在本地找到。磁盘要能同时容纳外层 TAR、解包目录、Docker 数据目录及业务卷。接下来用刚导入的 CUDA 镜像检查设备名称及 bfloat16 支持。

```bash
docker run --rm --pull never --network none --gpus 1 --entrypoint python risk-riskgnn:cuda-local \
  -c 'import torch; print(torch.cuda.get_device_name(0), torch.version.cuda); assert torch.cuda.is_bf16_supported()'
```

## 设置现场配置

在新解包目录执行一次 `install -m 600 .env.example .env`，用编辑器填写 `.env`。已有部署沿用与其数据卷匹配的凭据。部署使用固定的 Compose 项目名 `risk`，如目标机上已有同名项目，先确认这些卷是否属于本次部署。

| 配置项 | 现场填写 |
| --- | --- |
| `RISK_LLM_CONNECTION_TYPE`、`RISK_LLM_THINKING_ENABLED` | `qwen_self_hosted`、`false` |
| `RISK_LLM_URL`、`RISK_LLM_MODEL` | 比赛方提供的完整 Chat Completions URL（通常以 `/v1/chat/completions` 结尾）和准确模型 ID。地址需能从 backend 容器访问。 |
| `RISK_LLM_API_KEY` | 比赛方提供的原始令牌，省去 `Bearer ` 前缀。 |
| `DECISION_ENABLED`、`DECISION_MODEL_DIRECTORY` | `true`、`uk-financial-0.6b-v1`。GPU Compose 为 HTTP 模型服务设置 `cuda` 和 `bfloat16`。 |
| 数据库、存储与服务凭据 | 首次安装时设置 PostgreSQL、Neo4j、RustFS 两套应用账号及管理员凭据、模型数据库密码和 `RISK_GNN_API_TOKEN`。数据库密码会拼入连接 URL，可选用随机十六进制串。 |
| 浏览器地址 | 下方 SSH 转发方案使用模板的默认端口及 Origin。若使用已有内网反向代理，将 `PUBLIC_ORIGINS` 设为浏览器实际 Origin，将 `STORAGE_PUBLIC_ENDPOINT` 设为浏览器可达的 RustFS API 入口，代理须保留预签名请求的 Host 和路径。 |

## 启动服务，确认加载的是财务模型

```bash
dc=(docker compose -p risk -f compose.yaml -f compose.gpu.yaml)
"${dc[@]}" config --quiet
"${dc[@]}" up -d --no-build --pull never
"${dc[@]}" ps -a
```

`model-db-init`、`rustfs-init`、`neo4j-init` 和 `demo-seed` 首次运行成功后应为 `Exited (0)`。其余服务应处于运行状态。模型容器即使权重加载失败也可能通过存活检查，需要从业务后端查询模型就绪状态。

```bash
"${dc[@]}" exec -T backend python - <<'PY'
import os
import httpx

endpoint = os.environ["RISK_GNN_URL"] + "/internal/v1/decision/status"
headers = {"Authorization": "Bearer " + os.environ["RISK_GNN_API_TOKEN"]}
response = httpx.post(endpoint, headers=headers, json={}, timeout=30)
response.raise_for_status()
status = response.json()["data"]
if not status["ready"]:
    raise SystemExit(status["errorCode"])
model = status["model"]
print(model["modelVersion"], model["device"], model["dtype"], model["calibrationAvailable"])
PY
```

预期输出 `uk-financial-0.6b-v1 cuda bfloat16 True`。首次启动需等待模型预热完成。后续应用 `.env` 变更也使用相同的离线 `up` 命令。需暂时停机时使用 `"${dc[@]}" stop`，保留命名卷。

## 从演示电脑上传并预测

默认 Compose 只在比赛服务器的回环地址发布端口。若从另一台电脑操作，将 SSH 目标换成实际账号和主机，在**演示电脑**另开终端并保持隧道连接。

```bash
ssh -N -o ExitOnForwardFailure=yes \
  -L 18080:127.0.0.1:18080 -L 19000:127.0.0.1:19000 user@competition-server
```

1. 在演示电脑打开 `http://localhost:18080`，注册或登录比赛账号。前端通过 18080 同源访问 API，浏览器通过 19000 向 RustFS 直传。若更换默认端口，同步调整服务器配置、隧道和浏览器入口。
2. 打开模型设置，选择“使用后端默认模型”，点击“测试连接”，确认比赛方对话模型返回成功。
3. 在“模型工作台 → 数据集”选择演示电脑上的财务 ZIP，上传并等待服务端校验、企业导入均完成。在当前账号下查到企业及观测月份后即可预测，无需创建训练实验。
4. 在智能助手中先问“列出已部署的财务模型和我可用的数据集”，再问“查找企业 08876383 的观测月份，用 2024-03 的记录评估财务风险”。使用新数据时替换成该数据集真实存在的编号与月份。
5. 展开工具记录，应依次看到 `financial_risk_catalog`、`financial_risk_companies`、`predict_company_financial_risk` 的成功结果。确认卡片中的企业、月份、破产风险参考分及“已保存”，刷新会话后仍可查看同一记录。

## 常见故障

| 现象 | 先查哪里 |
| --- | --- |
| 启动提示缺镜像 | 核对 `images.txt`、`docker image load` 的输出和项目名 `risk`，尤其检查 CPU Worker 与 CUDA 服务两个标签。 |
| 初始化容器非零退出 | 查看 `"${dc[@]}" logs --tail=100 model-db-init rustfs-init neo4j-init demo-seed`，核对三个绑定挂载脚本和卷的凭据。 |
| 模型状态未就绪 | 查看 `"${dc[@]}" logs --tail=100 riskgnn`，核对 GPU 探针和 `models/weights/uk-financial-0.6b-v1/base/`。 |
| 能登录但上传失败 | 在浏览器网络面板查看 PUT 的主机和端口，确认 RustFS 隧道、预签名地址和 Origin。上传完成但校验停滞时查看 `riskgnn-worker` 日志。 |
| 助手无法连接或没有可预测数据 | 连接失败先核对内网 URL、模型 ID 与令牌。目录中缺数据时核对上传账号、财务适配器和企业导入状态。同一企业有多期时按检索返回的观测选择。 |
