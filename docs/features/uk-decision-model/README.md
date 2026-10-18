# UK 决策模型协作与交付

## 入口

- [发布包与下载流程](release.md)：打包、摘要、安装及离线交付。
- [本地加载与 CPU/CUDA 调试](local-development.md)。
- [模型说明](model-card.md)：标签、输入输出、指标来源及当前验证范围；同时随包分发。
- [版本定义](../../../models/uk_decision/releases/uk-financial-0.6b-v1/)：冻结协议、文件摘要及验收输入。

## Git 与 Release 的边界

| 内容 | 保存位置 |
| --- | --- |
| 固定输入协议、模型身份、原始文件摘要 | Git：`models/uk_decision/releases/<版本>/` |
| 小型工程验收输入、分设备参考输出 | 同版本目录的 `acceptance/` |
| 下载位置、附件大小和 SHA-256 | 同版本目录的 `release.json` |
| 打包、下载校验、运行缓冲区恢复、预测入口 | Git：`scripts/uk_decision/`、`scripts/jevforge_runtime.py`、`scripts/predict_uk_decision.py` |
| LoRA、配置、运行状态、tokenizer、模板和原始 README | 同一 Release 附件，不零散提交 Git |
| 底座与安装后的模型 | 本地忽略目录 `models/weights/` |

输入协议从本次模型使用的 UK 特征规则冻结，推理不再读取会持续修改的数据适配器规则。
数据适配器更新不应改变旧模型的输入。新增训练版本应建立新版本目录，重新核验并打包。

## 当前交付状态

`uk-financial-0.6b-v1` 已准备本地发布资产，尚未上传 GitHub Release。
正式校准文件和训练服务器验收样本仍缺失，已在元数据与模型说明中显式记录。
不提供伪造的 calibration.json；当前运行返回原始候选分数，校准结果为空。

本轮提供本地 CLI 与模型交付规范；现有 RiskGNN 工作台、HTTP 服务及助手工具尚未改接此模型。
