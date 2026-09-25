# 本地开发与验收

## Compose

```bash
cp .env.example .env
docker compose up --build -d
docker compose ps -a
```

浏览器访问 `http://localhost:18080`；默认本地演示账号 `demo`，密码取 `.env` 的 `DEMO_PASSWORD`（示例值 `demo-change-me`）。Vite 开发端口为 3000，API 网关诊断端口 18081，RustFS API/Console 为 19000/19001，均绑定本机。新环境请先修改 `.env` 中的凭据。运行 `docker compose down` 不删除命名卷；需清空演示数据时明确处理卷。

## 组件命令

```bash
cd backend && uv sync --dev
uv run ruff check src alembic tests
uv run mypy src/risk_api
uv run pytest -q tests
cd ../gateway && go test ./...
cd ../frontend && npm ci
npm run generate:api
npm run lint && npm run type-check && npm run build
```

导出契约在 `backend/` 执行 `uv run python -m risk_api.export_openapi`，随后生成前端类型，并检查 Git diff。提交前始终运行后端 Ruff 与 mypy。

## 最小验收链路

1. 首次启动后 `postgres`、`redis`、`rustfs`、`neo4j`、`backend` 健康；三个 init/seed 容器正常退出。重复运行 init/seed 不覆盖数据。
2. 登录后检索企业，打开画像、2–3 跳图谱及评分；评分与解释必须标记为演示快照。
3. 在画像上传一个测试文件，经 RustFS 直传、确认登记、下载并核对字节。报告、决策、模型看板和批量评估仍能显示演示标识。
4. 校验 401 会话过期、503 Redis 故障、伪造身份头、非法 Origin、参数 422 和不存在资源的统一信封。
