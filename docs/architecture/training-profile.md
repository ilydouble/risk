# 数据集训练配置档案

建模工作台定位为 RiskGNN 专用的企业风险模型训练与验证平台，不是任意算法的通用 AutoML。
平台复用一套模型方法，但每个数据集独立完成字段编码、图构建、参数训练和评估。

## 三层对象

1. **共享方法**：`RiskGNN-v1` 及 `com_risk_runtime.model.RiskGNNCore`，定义关系传播、
   超图传播和自身/传染风险门控融合。
2. **数据集训练配置**：Bundle 指纹、标签语义、划分、特征、编码、图本体和训练协议。
3. **训练制品**：一次实验在当前数据集上独立得到的参数、类别词表、指标和解释结果。

因此，SMEsD 与新加坡数据可以使用相同代码验证方法通用性，但两次运行不共享权重。Embedding
在各自实验中随机初始化并只用本数据集学习；一个数据集上的分数不能被描述为另一个数据集的效果。

## 档案内容

每次完成实验后，Worker 生成 `profileVersion=1` 的 `trainingProfile`，同时写入 PostgreSQL
实验结果和 RustFS 制品内的 `training-profile.json`。档案包含：

- 数据：数据集 ID、Bundle schema、ZIP SHA-256、文件清单、样本/企业/图快照数量；
- 目标：任务类型、样本粒度、正类、预测窗口和业务定义；
- 划分：train/validation/test 的样本、正例、正例率和企业数量；
- 特征：选择模式、入模字段声明、排除原因和仅在 train 拟合的选择规则；
- 编码：数值填补/缩放、类别未知值与随机 Embedding、节点和事件编码策略；
- 图：快照定义、节点/关系/事件/超边数量与类型、静态图限制；
- 训练：执行变体、随机种子、RiskGNN 超参数、早停和数据隔离协议；
- 评估：各变体 validation/test 指标及其用途；
- 溯源：核心实现、代码版本、Python/Torch/scikit-learn 版本和制品格式；
- 限制：例如静态图不能声明严格未来预测、企业风险不能称为贷款违约概率。

类别词表、填补统计和模型参数留在模型文件中，不写入 PostgreSQL 档案；平台也不保存原始客户行。

## 独立训练协议

档案固定记录以下可审计语义：

```json
{
  "trainingScope": "current_dataset_only",
  "weightsTransferred": false,
  "externalPretrainedEmbeddings": false,
  "embeddingInitialization": "random",
  "preprocessingFitSplit": "train",
  "earlyStoppingSplit": "validation",
  "testUsedForSelection": false
}
```

评估页将该协议显示为“共享算法，独立训练”。历史实验没有档案时仍可只读展示原结果，但必须
重新运行才能获得完整训练配置档案。

## 制品校验

实验 ZIP 的 `manifest.json` 记录 `training-profile.json` 以及每个模型文件的路径、大小和
SHA-256。外层实验记录继续保存整个 ZIP 的对象键、大小和 SHA-256，且 `autoPublished=false`。
档案用于复现和审计，不代表模型已经通过上线审批或投入生产授信。
