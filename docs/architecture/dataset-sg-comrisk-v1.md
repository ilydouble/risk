# sg-comrisk-v1 数据 ZIP 协议

主流程见[数据集接入流程](dataset-zip-onboarding.md)。本协议用于已有新加坡企业导出，
不代表任意国家、标签或特征的数据都可以通过同名文件复用训练。

## 文件结构

以下文件全部位于 ZIP 根目录，或位于同一个一级目录（例如 `comrisk_export/`）：

```text
comrisk_export/
  company_attr.parquet
  edges.parquet
  label.parquet
  id_map.parquet
  splits_5seed.parquet
  feature_config.json
  export_meta.json
```

ZIP 文件名和这层目录名可以自定义，但必需文件名固定。
不能同时放两份 company_attr；不能再套一层目录。
不要在 ZIP 根目录增加 `metadata.json`，该名称当前用于识别 Bundle v1。
允许其他来源附件，但仍计入 ZIP 限额；所有 `.parquet` 都会完整扫描检查可读性。
包内脚本只作为附件保存，服务不执行。容量和压缩限制见[主流程](dataset-zip-onboarding.md#3-按协议打包并本地自检)。

## 必需列与约束

| 文件 | 必需列 | 类型与含义 |
| --- | --- | --- |
| company_attr | company_id、下列六个特征 | ID 为字符串；特征为整数、浮点或布尔 Parquet 类型 |
| id_map | company_id_str、company_id_int | 字符串 ID → 整数索引 |
| label | company_id、label、is_labeled | 字符串 ID；数值二分类标签；整数/布尔标签掩码 |
| edges | src_id、dst_id、rel_type、weight | 字符串端点/关系类型；数值权重 |
| splits_5seed | seed、node_idx、split | 整数种子、整数节点索引、字符串划分 |

- company_attr、id_map、label 的企业 ID 非空且各自唯一，三表覆盖同一批企业。
- company_id_int 必须等于企业在 company_attr 中的物理行号，从 0 连续编号。
  重排企业行时要同步更新 ID 映射和划分索引，不能沿用旧 node_idx。
- is_labeled 为 0 或 1；值为 1 时 label 必须是非空的 0 或 1。
  不把未知标签填成正常企业；掩码为 0 的企业可作为图上下文。
- 边的两个端点都必须存在于 id_map；rel_type 非空，weight 为有限正数。
- seed 固定为 0、1、2、3、4；每个 seed 都将全部有标签企业恰好划分一次。
  每个 `(seed, node_idx)` 唯一，不能出现无标签企业或不存在的索引。
- split 使用 `train`、`val`、`test`；当前训练取 seed 0，并要求三个划分各有两类标签。

## 特征定义

六个特征及 `numeric_features` 的顺序固定为：

1. `officers`
2. `name_change_count`
3. `has_unit`
4. `related_company_count`
5. `related_company_weighted`
6. `address_trust`

feature_config.json 至少提供以下结构；不要更换顺序或混入额外特征：

```json
{
  "protocol_version": "2.0",
  "protocols": {
    "A_no_priors": {
      "numeric_features": [
        "officers", "name_change_count", "has_unit",
        "related_company_count", "related_company_weighted", "address_trust"
      ]
    }
  }
}
```

`sg-comrisk-v1` 是工作台适配协议名，`2.0` 是原始特征配置版本，二者分别保留。
其他企业列可以存在，但当前 runner 不会自动选入；标签来源、企业年龄、社区风险先验
不进入该训练协议。新增字段的含义和缺失处理需要明确评审，不能仅通过改名接入。

export_meta.json 是必需的有效 JSON。适配器原样记录其中的来源信息，当前未规定必填键；
交付说明应补齐来源、生成时间、快照日期、构图方法、版本和已知缺口。

## 当前模型如何使用这些数据

- 数据校验扫描全量；质量报告扫描六个特征，PSI 在每个划分最多取 5,000 行稳定样本。
- `smoke-v1` 按 seed 0 的原划分与标签比例，最多选 2,000 个有标签目标。
- 再加入最多两跳、每节点四个邻居的确定性上下文，保存实际 ID 与关系。
- node-edge 配置将关系双向化、使用单位权重；输入中的原始权重不会直接参与当前模型。
- node-only 配置保留同一准备协议和划分，将训练图置为空。
- 当前只使用 edges.parquet，不自动使用超边文件、额外边表或另一份图 ZIP。
- 缺失/非有限特征在准备阶段处理；address_trust 的填充值只从训练划分拟合。

这些约束属于[当前训练协议](training-profile.md)，需要保留真实权重、超边、全量图训练
或新企业入图推理时，应先扩展协议和 runner，再开放界面能力。

## 参考与自检

现有 `comrisk_export.zip` 是已跑通的参考输入；`新加坡图数据.zip` 的
nodes/edges/hyperedges 结构缺少本协议要求的标签、划分和特征配置，不能直接代替。
自检命令见[主流程](dataset-zip-onboarding.md#3-按协议打包并本地自检)。
实际校验代码：[singapore.py](../../models/service/adapters/singapore.py)；
准备代码：[prepare.py](../../models/service/adapters/prepare.py)。
