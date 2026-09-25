# 仓库协作规则

## 开始前

- 先核对需求前提、现有代码与配置。只有缺失信息会改变目标、外部契约、授权范围或难以回退的结果时才询问；其余明确假设并继续。
- 评估维护成本与影响范围，保留与任务无关的现有改动和未跟踪文件。

## 分层与契约

- `frontend/src` 遵循 `app → pages → features → entities → shared`，只能依赖同层或更低层；页面专属组件留在对应页面，不建 `widgets`。
- 后端按 `modules/<name>/{api,service,repository,errors}.py` 拆分。HTTP DTO 属于契约层，业务判断在 Service，数据库与外部系统访问在 Repository/共享适配层。避免为简单流程引入 DDD 抽象。
- `contracts/openapi.json` 从 FastAPI 导出。修改 DTO 或接口后重新导出，再在 `frontend/` 运行 `npm run generate:api`；不得手改 `schema.ts`、`dto.ts` 或手写相同 DTO。
- API 请求体使用 `RequestXxx`，响应 DTO 使用 `ResponseXxx`；业务响应始终为四字段信封，`code` 等于 HTTP 状态。模块定义稳定错误码，全局统一序列化；`X-Request-ID` 放响应头。
- Alembic 文件按 `V0001_xxx.py` 顺序命名，修订号对应版本。修改已发布结构只能新增迁移，不改写旧迁移。
- `gateway/vendor/` 是 Go 模块的生成快照，用于离线容器构建；升级 `go.mod` 后运行 `go mod tidy` 与 `go mod vendor`，不要手改第三方源码。
- 演示种子只补缺失记录，不覆盖已有数据。评分、SHAP、报告、决策、模型和批量评估中的演示内容不得描述成真实在线模型结果。

## 代码与验证

- 注释只解释非显然约束、设计取舍、兼容原因和关键不变量，避免逐行复述。
- 仅写针对长期稳定契约的必要测试；改动后运行受影响模块的测试和检查，不因小改动跑全仓无关测试。
- **每次 Git 提交前必须在 `backend/` 运行 `uv run ruff check src alembic tests` 和 `uv run mypy src/risk_api`。** 按改动再运行 Go 测试、前端 lint/类型检查/构建或契约漂移检查。
- 完成一个可审核单元就提交一次。提交消息用中文 conventional 格式，并在提交正文详细列出改动与验证。
- 文档放在 `docs/architecture/`，按主题拆分，单篇尽量不超过 200 行，保持简洁。
