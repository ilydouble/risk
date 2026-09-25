# 本地开发与验收

## Compose

```bash
cp .env.example .env
docker compose up --build -d
docker compose ps -a
docker compose logs -f backend demo-seed
```

浏览器默认访问 `http://localhost:18080`；登录页可自助注册，注册后再登录，新环境不预置账号。新环境请先修改 `.env` 中基础设施的示例凭据。项目名 `risk` 负责容器命名空间，服务键不重复加前缀。运行 `docker compose down` 不删除命名卷；服务更名后可加 `--remove-orphans` 清理旧容器，不使用 `-v`。Redis 不持久化，重建时需要重新登录。新空卷写入八家演示企业；已有卷中的旧账号和企业不会自动删除。

宿主机端口在 `.env` 中单独设置，所有映射只绑定 `127.0.0.1`；容器内端口和服务间地址保持固定：

| 变量 | 默认宿主机端口 | 容器端口 |
| --- | ---: | ---: |
| `FRONTEND_HOST_PORT` | 18080 | 80 |
| `GATEWAY_HOST_PORT` | 18081 | 8081 |
| `RUSTFS_API_HOST_PORT` | 19000 | 9000 |
| `RUSTFS_CONSOLE_HOST_PORT` | 19001 | 9001 |

本机默认的 Origin 白名单随前端端口变化，浏览器预签名地址随 RustFS API 端口变化；独立运行的 Vite 仍监听 3000，其 API 代理会读取仓库根目录 `.env` 的网关端口。自定义域名可显式设置 `PUBLIC_ORIGINS`、`STORAGE_PUBLIC_ENDPOINT`，`VITE_API_PROXY` 仍可覆盖开发代理。旧 `.env` 如保留固定的 `PUBLIC_ORIGINS` 或 `STORAGE_PUBLIC_ENDPOINT`，需删除这两项旧默认值才能让端口自动联动；自定义值会继续覆盖默认值。

镜像构建如需经过宿主机代理，在 `.env` 设置 `BUILD_HTTP_PROXY`、`BUILD_HTTPS_PROXY`，地址可使用 `host.docker.internal`；`BUILD_NO_PROXY` 用于排除直连地址。这些变量只用于源码镜像的构建步骤，不传给运行中的应用。RustFS 服务固定为 `rustfs/rustfs:1.0.0`，切换镜像前保留现有数据卷。

后端与种子容器在本地默认输出易读的 `pretty` 日志；服务器有日志采集器时设置 `RISK_LOG_FORMAT=json`，输出单行 JSON。`RISK_LOG_LEVEL` 默认 `INFO`，只控制应用日志。业务请求的日志带 `X-Request-ID`，可以从响应头复制该值在容器日志中检索；成功的健康检查不产生日志。容器日志的保留期限取决于 Docker 配置。

## 组件命令

```bash
cd backend && uv sync --dev
uv run ruff check src alembic tests
uv run mypy src/risk_api
uv run pytest -q tests
cd ../gateway && go test ./...
cd ../frontend && npm ci
npm run api:generate
npm run demo:generate
npm run lint && npm run type-check && npm run build
```

导出契约在 `backend/` 执行 `uv run python -m risk_api.export_openapi`，随后生成前端类型，并检查 Git diff。演示种子生成到 `backend/seed/demo/`，重复生成也应无差异。提交前始终运行后端 Ruff 与 mypy。

## 最小验收链路

1. 空卷首次启动后 `postgres`、`redis`、`rustfs`、`neo4j`、`backend` 健康；三个 init/seed 容器正常退出。演示库有八家企业且无预置用户，重复运行 init/seed 不覆盖数据。
2. 登录后检索企业，打开画像、2–3 跳图谱及评分；评分与解释必须标记为演示快照。
3. 在画像上传一个测试文件，经 RustFS 直传、确认登记、下载并核对字节。报告、决策、模型看板和批量评估仍能显示演示标识。
4. 校验 401 会话过期、503 Redis 故障、伪造身份头、非法 Origin、参数 422 和不存在资源的统一信封。
