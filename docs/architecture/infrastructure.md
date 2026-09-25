# 基础设施与信任边界

`compose.yaml` 启动固定镜像版本的 PostgreSQL 18、Redis、RustFS 1.0.0 GA、Neo4j Community、FastAPI、Go 网关及 Caddy 前端。项目名为 `risk`，服务键使用功能名；Compose 自动生成 `risk-rustfs-1` 等容器名。数据卷保存 PostgreSQL、RustFS 和 Neo4j；Redis 仅保存 Session，关闭持久化。首版不部署 MQ。

Go 容器构建使用 `gateway/vendor/`，避免容器网络无法连接模块代理时失败。升级依赖时以 `go.mod`/`go.sum` 为准重新运行 `go mod vendor`。

## 一次性初始化

- `rustfs-init` 在 RustFS 健康后幂等创建专用 Bucket，写入浏览器直传 CORS，并创建仅限该 Bucket 的应用用户/策略。运行时 API 使用应用凭据，Root 凭据只给初始化容器。
- `neo4j-init` 幂等创建演示节点组合唯一约束。
- `backend` 每次启动先迁移；`demo-seed` 之后补入缺失演示数据。重复启动不清空数据。

## Session 与浏览器

登录凭据是随机 Cookie `risk_sid`，HttpOnly、SameSite=Strict，8 小时固定 TTL，不自动续期。Redis 键为 `risk:session:v1:<凭据 SHA-256>`，值为版本化 JSON 身份。Go 网关通过 Stellarmesh Gateway SDK v0.4.0 的 Cookie 凭据扩展读取它，清理外部身份头并注入可信身份。后端持有登录、退出和当前用户接口。所有业务 POST 校验允许的 Origin；本地 HTTP 的 `COOKIE_SECURE=false`，HTTPS 部署设为 `true`。

## 对象存储

浏览器先调用业务 API 获取 60 秒预签名 PUT，直传 RustFS 后调用完成接口。完成接口核对对象存在与大小，再将 PostgreSQL 元数据置为可见；下载经业务 API 获取 60 秒 GET URL。`STORAGE_PUBLIC_ENDPOINT` 必须是浏览器可访问的地址，`STORAGE_ENDPOINT` 是容器内地址；修改 `PUBLIC_ORIGINS` 时同时更新 Bucket CORS。

Compose 默认凭据仅适合本机演示；共享或外网环境须换密码、配置 HTTPS 与 Cookie Secure，重新审视对外端口和 CORS。
