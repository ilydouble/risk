# 后端

`backend/` 使用 Python 3.12 与 uv。FastAPI 是 HTTP 入口，Dishka 装配依赖；SQLAlchemy AsyncSession + asyncpg、Redis asyncio、Neo4j async driver 和 `stellarmesh-objectstorage` 负责持久化访问。`stellarmesh-logging` 提供 Pretty 与 JSON 日志格式。

## 目录

```text
backend/
  alembic/versions/V0001_initial_schema.py
  seed/demo/C-1001.json … C-1008.json
  src/risk_api/
    app.py, __main__.py, dependencies.py
    shared/
      config.py, db.py, logging.py
      api/{envelope,page,response,middleware}.py
    modules/{auth,company,graph,score,document}/
      api/{route,handler,schemas}.py
      model.py, service.py, repository.py, errors.py（按需）
    modules/benchmark/
      api/{route,handler,schemas}.py
      service.py, errors.py, cli.py, engine/
```

`route.py` 声明路径与响应模型；`handler.py` 处理 HTTP、依赖注入及 DTO 映射；`schemas.py` 是模块自己的请求/响应 DTO。`auth`、`company`、`document` 的 `model.py` 保存各自 SQLAlchemy 映射；图谱和评分不为凑目录建立模型文件。Service 处理认证、查询、文件流程，Repository 处理数据库/图谱。Service 和 Repository 不引用 HTTP DTO。公共分页请求为 `PageRequest`，列表响应继承 `Page[T]`。模块错误映射为 `AppError`，全局 handler 调用公共响应函数序列化；参数校验、路由错误与未处理错误也走同一信封。

`app.py` 中的 `create_app()` 为每个 FastAPI 实例创建并装配自己的 Dishka 容器；lifespan 从 `app.state.dishka_container` 关闭它。`__main__.py` 在 `python -m risk_api` 启动 Uvicorn 前配置日志；Uvicorn 使用 `risk_api.app:create_app` factory。OpenAPI 导出也创建并关闭独立应用。请求 ID、Origin 校验与完成日志集中在 `shared/api/middleware.py`。

## 数据与生命周期

- PostgreSQL 的 `users`、`companies`、`documents` 保存账号、检索字段与文件状态。画像及中英评分快照存 JSONB，读取时由 Pydantic DTO 校验。
- 自助注册复用现有 `users` 表，无需迁移；密码由 Argon2 哈希后写入，用户名冲突由唯一约束原子判定。注册不写入 Redis，成功后用户单独登录。
- Neo4j 保存演示关系节点和边，图谱查询接受 1–3 跳（默认 3），由后端返回对应范围的节点及范围内的边。图谱不从 PostgreSQL JSON 拷贝响应。
- `V0001_initial_schema.py` 的 revision 是 `V0001`；后续迁移顺序递增。后端容器启动时先执行 `alembic upgrade head`，成功后启动 HTTP 服务。
- `demo-seed` 是默认启动的一次性容器，在迁移与服务就绪后补入八家精选企业、快照和图谱，不创建账号，也不重置已有行或关系。已有数据卷中的旧演示账号与企业保留。
- 演示种子由前端案例生成脚本按企业输出到 `seed/demo/`；在 `frontend/` 执行 `npm run demo:generate` 后检查 Git 差异。正式数据导入与演示种子分开处理。
- 基准模块在应用启动时由 Dishka 装配，工作线程校验测试快照、清单和权重并预计算 474 家预测。加载失败只使基准接口返回 503，认证与原有业务接口继续运行；解释计算也限制在专用工作线程。只读快照不导入 PostgreSQL 或 Neo4j，详见[公开基准](benchmark.md)。

## SDK 与验证

Python 锁文件固定 `stellarmesh-logging` 0.5.1 与 `stellarmesh-objectstorage` 0.1.0。对象上传/下载只由 SDK 生成 60 秒预签名 URL，浏览器随后传输对象字节。

## 日志边界

`shared/logging.py` 统一配置应用与 Uvicorn 的 stdout handler，并用 request context 将 `X-Request-ID` 加到模块日志；HTTP、Alembic 和一次性种子进程分别调用该配置。HTTP 进程不修改根 logger，独立运行的 Alembic CLI 则接管其文本根 handler，以便迁移日志也遵循所选格式。导出 OpenAPI 时不会因导入 `app.py` 而安装 handler。重复配置不会叠加 handler。`RISK_LOG_LEVEL` 控制应用日志级别，默认 `INFO`；`RISK_LOG_FORMAT=pretty|json` 选择同一 SDK 的可读输出或单行 JSON。Compose 本地默认 `pretty`，部署日志采集器时设为 `json`。

业务请求各输出一条完成日志，包含方法、路由模板、HTTP 状态、`internal_code` 和耗时；正常健康检查不逐次记录。注册、登录成功和文档预签名/确认等关键写入另记事件，仅记录内部 ID 与尺寸，不记录密码、Cookie、请求体、文件名、对象密钥或预签名 URL。已处理的 5xx 记录稳定错误码与底层异常类型；未处理异常记录堆栈及请求 ID。SDK formatter 负责字段脱敏与有界 JSON 编码，但不会扫描自由文本中的秘密，因此新增日志也须避免拼接敏感值。

日志写入容器 stdout，排障可按请求 ID 关联前后端链路；本仓库尚未配置集中采集与长期留存，不能将容器日志当作审计记录。

在 `backend/` 执行：

```bash
uv sync --dev
uv run ruff check src alembic tests
uv run mypy src/risk_api
uv run pytest -q tests
uv run python -m risk_api.export_openapi
```
