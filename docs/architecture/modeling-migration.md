# 工作台协议升级

## 本轮为破坏性升级

1. 备份需要保留的本机文件和数据库；本轮不会物理删除旧记录、对象或研究输出。
2. 重建业务后端、模型 HTTP 和 Worker。模型镜像包含 service、riskgnn 及数据契约 Schema。
3. 业务 Alembic V0007 将已有工作台记录标记为协议代次 1，新记录默认代次 2；
   列表和访问只接受代次 2。旧的未投递消息停止发送。
4. 模型 Alembic V0002 取消旧 queued/running 任务、关闭旧 Attempt 并清除租约。
5. 新 ZIP 必须包含 risk_dataset_contract.json；不为旧包提供缺省推断或自动补契约。
6. 重新上传、训练并发布模型。原 riskgnn-model-v1 包不再被新 CLI 接受。

不使用 down -v。协议失效与删除数据分开处理；以后如需清理历史对象另行安排。
迁移 downgrade 不会重新投递或启动已退休任务。

## 代码边界

- 数据适配在 models/riskgnn/dataset_adapters/；模型 CLI 为 riskgnn.workbench_cli。
- 研究和工作台入口共用 training_engine.py；研究 CLI 原参数、环境和默认行为保留。
- service 不再包含训练、数据分析或模型加载代码，也不定义 ModelAdapter 插件类。
- 静态概览工具迁为 python -m riskgnn.tools.sg_overview，已有概览快照不受本轮失效影响。
- 旧 service.cli 的训练命令停用，服务 CLI 只启动 HTTP；新模型命令见数据适配器文档。

[数据契约](dataset-contract.md) · [数据适配与 CLI](dataset-adapters.md) ·
[执行协议](model-execution-contract.md)
