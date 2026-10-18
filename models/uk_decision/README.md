# UK 决策模型共享代码与版本

`src/uk_decision_runtime/` 只保存训练和推理共用的模型加载、运行缓冲区保存与恢复。
它不依赖模型服务、HTTP、数据库或工作台。
`releases/` 保存固定模型版本的协议与摘要，不提交模型权重。

模型服务通过 uv 路径依赖自动安装本包。研究者已有 Torch/JevForge 环境时，
可使用 `pip install --no-deps -e models/uk_decision` 安装共享小包，继续使用原训练命令。
原 `scripts/jevforge_runtime.py` 保留导入兼容入口，不再维护另一份实现。

正式预测与交付说明见 [功能文档](../../docs/features/uk-decision-model/README.md)。
