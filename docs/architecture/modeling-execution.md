# 模型执行与恢复

## 所有权

业务 API 拥有 `workbench_datasets`、`workbench_runs`、`workbench_model_versions` 和
`workbench_dispatch`。每次读取、取消、发布和预测先校验用户归属。
模型服务使用独立数据库，拥有 Job、Attempt 和 Event；两端不直接读取对方的表。
业务库中的 execution 是展示缓存，执行状态以模型服务为准。

## 投递与领取

- 确认上传与校验投递、创建实验与训练投递，在业务库中各用一个事务提交。
- 后台投递器每次锁一条待发记录，通过内部 HTTP 提交。网络失败退避重发。
- 业务操作 ID 是模型任务 ID；重复且相同输入返回同一任务，不同输入返回 409。
- Worker 用 PostgreSQL `SKIP LOCKED` 领取任务，全局 advisory lock 保证一个计算槽。
- 每个 Attempt 有独立 UUID、目录和对象前缀；租约 60 秒，独立心跳间隔 10 秒。
- 心跳、事件与完成提交必须同时匹配任务状态、Attempt、租约所有者和有效期。

## 状态

```text
queued → running → completed
             ├──→ failed
             ├──→ cancelled
             └──→ queued（可恢复故障，最多三次）
```

阶段包括 starting、validating、preparing、training、testing、uploading。
数据/配置错误直接失败；网络或子进程信号中断可重试。
取消与失去租约会终止整个计算进程组，必要时 SIGKILL；过期任务在后续领取时回收。
旧执行者不能完成新 Attempt。取消请求持久化，即使业务后端重启也会继续投递。
用户重新运行创建新的 Run，通过 retryOf 指向原记录。

训练与测试分别运行在新进程。每个阶段的输出在持久卷中保存。
已封存的模型可以跨 Attempt 复制并复核；上传失败只重试上传，缺失结果才重新计算。
训练输出从未以成功状态暴露，只有独立测试与对象上传均完成后才完成任务。

## 事件与推理

每个任务分配递增事件序号，记录状态、epoch 指标和诊断日志。前端每两秒按 after 游标读取，
刷新时重新读取该 Run 的事件。单页最多 200 条，前端显示最近 2,000 条。
预测在 HTTP 服务独立子进程运行，一次最多 32 个图内 ID、60 秒超时、单推理槽；忙时返回 503。
训练 Worker 与预测不共享计算进程，HTTP 事件循环不执行 Torch 运算。

内部接口通过服务令牌认证，沿用网关 Request ID；模型服务缺失 ID 时生成兜底值。
模型服务故障只使相关接口返回 `MODEL_SERVICE_UNAVAILABLE` 503，不阻止登录和原业务启动。
