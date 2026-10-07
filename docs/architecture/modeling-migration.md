# 旧模型工程迁移

模型研究以 models/ 为主线，models/service/ 提供工作台服务；停用 SMEsD HTTP 与旧 Bundle Worker。

## 已有开发环境

1. 停止本机旧 `workbench.worker`，避免它继续领取旧表任务；不要清理原数据库或 Bucket。
2. 在切换分支前备份 `com_risk_model/weights`、`runs`、本地训练数据到忽略目录
   `riskgnn/legacy-artifacts/`，核对各文件 SHA-256。此目录不会提交 Git。
3. 本次实施已备份本机 25 个文件，清单为该目录的 `backup-manifest.json`；原忽略文件仍保留。
4. 更新 `.env` 中模型数据库、服务令牌及独立 Bucket 配置，参照 `.env.example`。
5. `docker compose up --build -d`，初始化在现有 PostgreSQL 中幂等创建独立数据库/账号，
   在 RustFS 创建新 Bucket；后端只新增 V0006 表，不改旧迁移、不删除旧表。
6. 打开 `/modeling` 重新上传 comrisk_export ZIP。旧模型权重不兼容新协议，不自动发布。

旧受跟踪运行代码已移除，可通过 Git 历史追溯；研究来源说明保存于
`models/service/docs/legacy-comrisk/`。旧对象、旧实验表、命名卷保留。
`/benchmark/*` 显示停用说明；模型服务尚未启动时，登录和企业演示仍可使用。

## 研发入口

研究侧沿用 requirements.txt、原 Python/CUDA 环境及训练命令。
服务代码集中在 models/service/，依赖并调用原研究模型；不要求研究者安装服务。
服务单独使用 service/pyproject.toml、uv.lock 与 service/.venv，安装及 CLI 见[服务说明](../../models/service/README.md)。
从上一版工作台切换时，原 riskgnn/.venv 可保留，但不再用于服务；使用新的独立环境。
重新构建 riskgnn 与 riskgnn-worker 即可，数据库迁移历史、对象和已有模型包保持兼容。
静态概览工具迁为 `python -m service.tools.sg_overview`，原快照内容不变。
不要继续启动旧工作台 Worker，也不要把旧检查点直接放入新模型包。

## 跟进 dev 的 models 主线

统一服务迁到 models/service，与研究目录并列；Compose 构建上下文改为 models。
研究 requirements 和脚本入口保留，Python 包导入与原脚本导入均可用。
旧 workbench 的 Bundle 校验和分析迁入 datasets/bundle 与 analysis，不迁入旧 JobStore。
旧 runtime / training / testing 已退出后端运行依赖，原表与本地未跟踪文件保留。
本机旧 riskgnn/runs、legacy-artifacts 不自动搬动；新环境工作目录为 models，
重新创建 service/.venv，勿直接移动虚拟环境。已有模型包继续通过对象存储加载。
此次只在已有 JSON 配置和结果中增加模型选择、分析及档案字段，无新增表结构迁移。

## 服务环境迁移到 uv 项目

研究目录继续保留 requirements 和原训练命令。服务的旧 requirements 输入/锁及分散工具配置
已由 pyproject.toml 和 uv.lock 替代；在 models 执行 `uv sync --project service --locked`。
已有 service/.venv 会被 uv 同步，原研究虚拟环境不受影响；不要在该服务环境手动 pip 安装。
容器需重新构建模型镜像，HTTP/Worker 命令、数据库与持久卷保持不变。
