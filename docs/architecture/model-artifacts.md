# RiskGNN 模型产物与发布

当前新模型使用 riskgnn-plus-model-v1，完整文件与算法状态见[RiskGNN+ 接入](riskgnn-plus-workbench.md)。
以下 riskgnn-model-v2 描述作为历史 RiskGNN 包兼容说明；两种格式均可独立重载预测。
产物格式由模型代码负责，服务只校验声明、文件安全和内容摘要。

```text
model/
  manifest.json     formatVersion=1, kind=riskgnn-model-v2, files
  weights.pt        网络、分类器、固定嵌入和 alpha
  metadata.json     配置快照、生效参数、实际目标数量、特征、预处理、划分与源码/依赖版本
  ids.json          公司在前、人物在后的图内索引；预测只接受公司
  context.npz       特征、图、标签及测试划分；快照配置另存方向/权重/置信度
  evidence.json     JSON 子集原始关系、超边和事件（仅保留证据）
report/
  metrics.json      独立测试报告和被测模型摘要
  predictions.json 测试预测
```

manifest 为每个文件记录长度和 SHA-256，仅接受包内相对路径。
模型 CLI 验证格式、权重及必需状态，Torch 使用 weights_only=True。
模型当前只接受绑定图内企业，不自动接收新节点。

训练完成即封存模型；evaluate 在新进程重载并输出独立报告，不能改写模型。
服务封存操作回执，绑定运行时版本、输入、参数、资源和产物清单。
上传对象位于 artifacts/<任务>/<attempt>/<序号>/<sha256>，目录打包成 ZIP。

业务发布创建不可变模型版本，绑定通过独立测试的模型 ZIP 摘要；重复发布幂等。
发布不切换生产默认模型，也不自动上传 GitHub Release。
参数冻结和重试绑定见[实验配置](experiment-configuration.md)；metadata 中的 configuration
与业务记录一致，effectiveConfig 对应 resolvedParameters，actualCounts 记录实际执行数量。
当前用户下载入口提供模型 ZIP；报告保存在任务结果和独立对象中。

## 离线重载

下载地址有效期 60 秒。校验 ZIP 摘要并解压后：

```python
from pathlib import Path
from riskgnn.workbench.artifacts import verify

verify(Path("/absolute/path/model"), "riskgnn-model-v2")
```

随后按[模型 CLI 示例](dataset-adapters.md#模型-cli-本地调用)提交 evaluate 或 predict：
输入角色为 model，format 为 riskgnn-model-v2，sha256 使用模型侧 asset_digest 计算目录摘要。
预测参数为 company_ids，按输入顺序返回结果；未知 ID 明确失败。

完整模型包含数据上下文和企业 ID，沿用数据集归属与访问权限，不自动公开。
原研究输出的预测 NPZ 不是可直接发布的完整模型包。

architecture 区分既有 sg-node-edge-v2 与 dataset-node-edge-v1；保持旧 v2 产物可加载。
快照人物嵌入也作为 buffer 保存，人物不接受预测请求；跨快照人物使用不同内部索引。
完整源包仍由 datasetSha256 绑定，evidence.json 不替代全量来源文件。
