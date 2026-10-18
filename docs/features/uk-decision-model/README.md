# UK 决策模型协作与交付

## 入口

- [发布包与下载流程](release.md)：打包、摘要、安装及离线交付。
- [本地加载与 CPU/CUDA 调试](local-development.md)。
- [模型服务、数据上传与助手联动](integration.md)。
- [模型说明](model-card.md)：标签、输入输出、指标来源及当前验证范围；同时随包分发。
- [版本定义](../../../models/uk_decision/releases/uk-financial-0.6b-v1/)：冻结协议、文件摘要及验收输入。

## Git 与 Release 的边界

| 内容 | 保存位置 |
| --- | --- |
| 固定输入协议、模型身份、原始文件摘要 | Git：`models/uk_decision/releases/<版本>/` |
| 小型工程验收输入、分设备参考输出 | 同版本目录的 `acceptance/` |
| 下载位置、附件大小和 SHA-256 | 同版本目录的 `release.json` |
| 输入/产物校验、评分与 HTTP/CLI | Git：`models/service/src/model_service/modules/decision/` |
| 训练/推理共享加载与运行缓冲区 | Git：`models/uk_decision/src/uk_decision_runtime/` |
| 兼容命令入口 | Git：`scripts/uk-decision`、`scripts/predict_uk_decision.py`、`scripts/jevforge_runtime.py` |
| LoRA、配置、运行状态、tokenizer、模板和原始 README | 同一 Release 附件，不零散提交 Git |
| 正式校准文件及校准样本审计记录 | 同一 Release 附件；Git 中的 `calibration_file` 记录大小和摘要 |
| 底座与安装后的模型 | 本地忽略目录 `models/weights/` |

输入协议从本次模型使用的 UK 特征规则冻结，推理不再读取会持续修改的数据适配器规则。
数据适配器更新不应改变旧模型的输入。新增训练版本应建立新版本目录，重新核验并打包。

## 当前交付状态

`uk-financial-0.6b-v1` 已准备本地发布资产，尚未上传 GitHub Release。
已取得带索引和来源清单的完整财务 JSONL，可用于真实观测推理验收。
已取得正式校准文件，温度为 0.8826538438450512，来自训练期独立留出的 4,046 条观测。
v1 在首次发布前补齐校准，作为完整基线；本地只保留 `models/weights/uk-financial-0.6b-v1/`。
运行同时返回原始和校准分数；校准适用范围仍为正负各半的匹配研究样本。
训练服务器固定验收输入和参考输出仍缺失，不宣称已经复现服务器数值或全量指标。

常驻推理、独立预测历史和助手结果卡片已接入；与原 RiskGNN+ 训练/发布流程并存。
