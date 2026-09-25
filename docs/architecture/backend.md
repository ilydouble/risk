# 后端

`backend/` 使用 Python 3.12 与 uv。FastAPI 是 HTTP 入口，Dishka 装配依赖；SQLAlchemy AsyncSession + asyncpg、Redis asyncio、Neo4j async driver 和 `stellarmesh-objectstorage` 负责持久化访问。`stellarmesh-logging` 的 JSON formatter 输出结构化日志。

## 目录

```text
backend/
  alembic/versions/V0001_initial_schema.py
  seed/demo.json
  src/risk_api/
    main.py, dependencies.py, models.py
    shared/
      config.py, db.py
      api/{envelope,page,response}.py
    modules/{auth,company,graph,score,document}/
      api/{route,handler,schemas}.py
      service.py, repository.py, errors.py（按需）
```

`route.py` 声明路径与响应模型；`handler.py` 处理 HTTP、依赖注入及 DTO 映射；`schemas.py` 是模块自己的请求/响应 DTO。Service 处理认证、查询、文件流程，Repository 处理数据库/图谱。Service 和 Repository 不引用 HTTP DTO。公共分页请求为 `PageRequest`，列表响应继承 `Page[T]`。模块错误映射为 `AppError`，全局 handler 调用公共响应函数序列化；参数校验、路由错误与未处理错误也走同一信封。

## 数据与生命周期

- PostgreSQL 的 `users`、`companies`、`documents` 保存账号、检索字段与文件状态。画像及中英评分快照存 JSONB，读取时由 Pydantic DTO 校验。
- 自助注册复用现有 `users` 表，无需迁移；密码由 Argon2 哈希后写入，用户名冲突由唯一约束原子判定。注册不写入 Redis，成功后用户单独登录。
- Neo4j 保存演示关系节点和边，接口仅返回页面需要的 2–3 跳。图谱不从 PostgreSQL JSON 拷贝响应。
- `V0001_initial_schema.py` 的 revision 是 `V0001`；后续迁移顺序递增。后端容器启动时先执行 `alembic upgrade head`，成功后启动 HTTP 服务。
- `demo-seed` 是一次性容器，在迁移与服务就绪后补入缺失账号、企业、快照和图谱。它不重置已有行或关系。演示密码由本地环境给出并以 Argon2 哈希写入。

## SDK 与验证

Python 锁文件固定 `stellarmesh-logging` 0.5.1 与 `stellarmesh-objectstorage` 0.1.0。对象上传/下载只由 SDK 生成 60 秒预签名 URL，浏览器随后传输对象字节。

在 `backend/` 执行：

```bash
uv sync --dev
uv run ruff check src alembic tests
uv run mypy src/risk_api
uv run pytest -q tests
uv run python -m risk_api.export_openapi
```
