# 模型包与发布

## 完整产物

```text
model/
  manifest.json    formatVersion=1, kind=riskgnn-model-v1, sourceSha256, files
  weights.pt       网络、分类器、固定嵌入及 alpha
  metadata.json    协议、特征顺序、预处理、关系编码、划分统计、依赖与源码摘要
  ids.json         图内企业 ID 与张量索引
  context.npz      特征、图、标签和冻结测试划分
  metrics.json     独立重载测试报告
  predictions.json 逐测试企业预测
```

manifest 为每个文件记录长度及 SHA-256；只接受包内相对路径。
加载时校验格式版本、必需文件、网络版本和摘要，Torch 使用 weights_only=True。
模型只能预测该包绑定的图内企业；未知 ID 明确返回 404，不推断新节点。

训练产物先在 Attempt 的持久目录封存，独立测试后重新封存；上传到
`artifacts/<任务>/<attempt>/<sha256>.zip`。业务发布创建不可变版本，绑定该摘要，重复发布同一 Run
返回同一版本。发布不更改生产默认模型，不创建 Release。

## 下载和离线使用

业务 API 在权限校验后返回 60 秒预签名地址及 SHA-256。下载完整 ZIP，核对摘要、解压后：

```bash
cd models
uv run --project service python -m service.cli verify --input /path/to/model
uv run --project service python -m service.cli test --input /path/to/model
uv run --project service python -m service.cli predict --input /path/to/model --ids YOUR_UEN
```

下载包包含图上下文和企业 ID，按数据集权限管理；本轮不自动公开发布。
源代码、训练配置、数据指纹共同标识一次可重放实验；旧研究检查点不自动转换为本协议。
旧 com_risk_model 的本机产物备份见[迁移说明](modeling-migration.md)。

服务直接调用研究网络，包装层将固定嵌入和 alpha 纳入 v1 状态。旧 v1 包继续可加载；
新训练的初始化沿用原 RiskGNN，不能仅凭相同 seed 宣称复现早期服务训练分数。
