# UK Dataset V1 数据适配器

## 输入与契约

ID / 版本：`uk-dataset-v1 / 1`。来源为 `datasets/uk_dataset_v1/`。

```text
risk_dataset_contract.json
train.json
valid.json
test.json
audit.json
export_meta.json
```

三个 JSON 的 SHA-256 必须与 audit 和 export_meta 中的记录一致。
现有包部分说明仍写四维特征或两类超边；代码以本适配器和实际数据为准。
包内 build/verify Python 不执行，不依赖已删除的 com_risk_runtime。

## 专用语义

- 233,251 家企业，412,348 条有向关系；无人物节点、无事件。
- 七维特征：age_months、n_charges、n_charges_outstanding、addr_company_count、
  n_net_dir、max_span、sum_span。后六列按本准备协议执行 log1p。
- 四类关系：SAME_ADDRESS、EQUITY、PREVNAME、SAME_NAME。
- 三类超边：sic_section、postcode_area、director_group。
- 保留源包 train / valid / test，不重新随机划分企业；源构建流程按地址组划分。
- 三个快照独立，边不能引用其他快照节点。
- 标签是企业登记困境状态，不是未来固定期限的违约概率。
- weight 在 [0.3, 1] 内，表示源包定义的证据权重；没有独立 confidence 字段。
  模型的 confidence 通道使用中性值 1，不把 weight 复制成所谓校准概率。

## 初版训练

`config.target_count` 默认为 2,000，可设整数 6–20,000。
按原始划分和标签比例稳定抽取目标，保留少数类；不足时使用全部目标。
邻域按入边扩展两跳，每节点最多四个来源，保留选中节点间的有向关系。

本准备协议为 `uk-dataset-v1-train-fit-v1`：

1. 后六个计数字段 log1p，年龄不做 log。
2. 缺失值处理、均值和标准差只在训练目标拟合并保存。
3. 验证/测试使用同一参数，保持各自原始快照边界。

它不同于交付说明中“在全部节点计算 z-score”的实验，不声称复现那些历史分数。
当前 CPU node_edge 使用公司特征和有向加权关系，超边仅作为保留证据。
不把缺少自然人节点理解成没有董事信息：director_group 与三个人统计量来自上游处理。

## 打包

预设与规则见 [delivery.json](delivery.json)，轻量环境及校验选项见 [打包指南](../PACKAGING.md)。

从 `models/` 执行：

```bash
python -m riskgnn.dataset_adapters.package_dataset \
  --data-dir ../datasets/uk_dataset_v1 --output /tmp/uk-v1.zip \
  --preset uk-companies --dataset-version v1-20261010
```

输出文件不能预先存在。可加 `--set target_count=60` 准备小样本实验；默认打包只做基本检查，
显式 `--validate` 或上传后的 Worker 才执行全量结构/哈希校验。
模型结果记录数据摘要、预处理、划分和实际使用的数据能力，下载后可独立加载预测。
