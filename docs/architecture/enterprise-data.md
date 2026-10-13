# 标准企业数据与模型共享映射

## 数据链路

```text
原始 ZIP → DatasetAdapter.inspect / enterprise_records
                  ├─ 标准可读数据 → RustFS → 业务端事务导入 → 工作台分页浏览
                  └─ 同一属性映射 → prepare 编码/填充/标准化 → RiskGNN
                                                           ↓
                             企业 ID + 模型版本 ← 真实预测记录
```

适配器负责解释来源字段；标准数据保留预处理前的属性值，模型准备通过同一
`attributes / feature_vector` 映射读取数值。训练集拟合的填充、对数与标准化规则不变。
标签和划分单独保留，不作为节点输入特征。模型服务与业务 API 不导入对方的模型代码。

## 标准产物 v1

`inspect` 输出文件产物 `enterprises`，格式 `risk-enterprise-data-v1`，UTF-8 JSONL。
执行器按现有产物协议封存、计算摘要并上传；校验任务结果中的 `enterpriseArtifact`
指向该文件，`enterpriseData.counts` 保存实际导出数量。

第一行包含：

- `format`：固定 `risk-enterprise-data-v1`。
- `datasetContract`：源包契约，绑定数据集 ID/版本和适配器版本。
- `sourceSha256`：原始 ZIP 字节摘要。
- `featureNames`：模型特征顺序；`target`：真实标签定义。

其余每行包含 `kind`、`snapshot`、`data`，以及对应身份/引用字段：

| kind | 身份或引用 | data 内容 |
| --- | --- | --- |
| company / person | nodeId | name（可空）、attributes、标签/划分或其他可读属性 |
| edge | source、target | 关系类型、方向、权重及已有证据 |
| hyperedge | members | 群组类型、成员及已有置信度等证据 |
| event | source（企业 ID） | 原始事件字段 |

节点在同一数据集和 snapshot 内唯一。人物 ID 可跨快照重复，不合并图上下文。
企业预测仍沿用适配器原有企业 ID；现有适配器保证监督企业跨划分不重复。
未来有同企业多时点样本时，适配器必须提供可区分快照的模型目标 ID。
没有企业名称时保留 null，页面显示源 ID；缺失数值显示为 —，不填造名称、评分或授信额度。

当前支持：ACRA 导出全部企业六维模型属性、已有名称/国家/资本等展示属性、seed 0 划分和原始边；SMEsD / UK
导出全部快照的企业、人物、关系、超边和事件。ACRA 可选超图/风险附件仍在源 ZIP 中，
未解释为标准记录。标准导出与模型输入独立，实际参与的证据以当前实验档案为准。

新适配器实现 `enterprise_records(validated)`，共享其属性映射与模型准备代码，
并验证导出数量、引用、缺失值及训练前后转换一致性。不能靠文件名推断业务字段含义。

## 导入与查询

业务接口均为 POST，位于 `/api/v1/modeling/`：

- `import-enterprises`：按 datasetId 导入标准文件，已有同摘要导入幂等返回。
- `list-enterprise-records`：按数据集、类型、ID/名称、节点和快照筛选，使用公共分页。
  可选 modelId 必须属于同一用户、同一数据集；企业记录附上该模型已保存的预测。
- 既有 `predict-model`：执行成功后按模型版本/企业 ID 保存不可变结果，重复请求幂等。

所有读取与导入先校验数据集归属，跨用户返回 404。下载复核长度和 SHA-256，
再核对源契约/摘要、行结构、节点唯一性、引用和导出数量。单产物最多 512 MiB，
单行最多 1 MiB。批量写入属于同一事务，失败整批回滚；同数据集并发导入使用行锁串行化。

`V0008` 新增 `workbench_enterprise_imports / records / predictions`。
标准企业数据按数据集隔离，不覆盖演示 `companies` 表，也不制造演示授信字段。
目前导入为显式同步操作，大规模数据可能需要后续异步任务化。

## 页面操作与现有限制

1. 重新上传数据 ZIP 并等待校验；升级前旧校验结果没有标准产物，需重新上传。
2. 在数据集详情的「真实企业数据」点击「导入企业数据」。
3. 分页浏览企业/人物、查看属性，或按企业快照查看关系、超边和事件。
4. 发布同数据集的模型后选择模型，运行企业预测并查看保存的概率与标签。

当前预测只支持已发布模型绑定图中的企业，子集训练不会包含全部数据；未知企业明确失败。
标准企业映射继续复用；当前默认算法已切换[RiskGNN+](riskgnn-plus-workbench.md)。现有企业画像/评分演示页独立保留；
本次真实数据入口在模型工作台，不自动写 Neo4j 或生成 SHAP、报告和授信决策。
