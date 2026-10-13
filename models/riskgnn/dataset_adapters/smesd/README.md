# SMEsD JSON V5 数据适配器

工作台当前默认使用 [RiskGNN+](../../../../docs/architecture/riskgnn-plus-workbench.md)，
在本适配器基础准备后加入超图和已有事件。下文 node_edge 描述保留为基础准备与历史配置说明。

## 输入与来源

ID / 版本为 `smesd / 1`。接收 `datasets/comrisk_export_v5/smesd/` 的处理后快照，
不直接接收 `datasets/smesd/` 的原始 Pickle。

```text
risk_dataset_contract.json
train.json
valid.json
test.json
audit.json                 # 来源说明；其中 SHA 是原始 Pickle 的摘要
```

原始文件继续用于同事的研究复现。工作台不反序列化上传的 Pickle，
不执行交付包中的 schema_v5.py，也不恢复已删除的 com_risk_runtime。
服务器重新记录当前 JSON 的 SHA-256，不把 audit 中的原始摘要当成 JSON 校验值。

## 专用语义

- 三个快照标记 isolated_snapshots；保留已经完成的企业去重与划分。
- train / valid / test 企业数分别为 2,816 / 686 / 474。
- 企业参与监督；人物没有标签，特征为 null，仅作为图上下文。
- 人物 ID 可能跨快照重复，内部索引使用 `(snapshot, node_id)`，不跨图合并人物。
- 三维特征是 log_registered_capital、log_paid_capital、age_months；资本不重复 log。
- 十二类有向关系按原顺序编码；不补反向关系、不把不同关系合并。
- V5 要求独立 strength 和 existence_confidence；当前后者恒为 1。
- industry / area 是属性型超边；qualify 是共享人物关系型超边。
- 保留诉讼事件及超边证据，校验成员与事件的公司引用。

## 初版训练范围

当前选择 `snapshot-node-edge-v1`，默认最多 4,000 个目标（当前包共有 3,976 个）。
`config.target_count` 可设 6–20,000；不足时使用全部目标。

抽样保持每个原始划分及标签层；上下文按入边扩展两跳，每节点最多四个来源邻居。
保留选中节点之间的原始有向边，人物只进入人物投影，预测 API 只接受企业 ID。
同一人物在不同快照的内部节点始终独立。

训练特征的缺失中位数与标准化均值/尺度仅在训练目标拟合，写入 metadata。
消息传播使用源文件 weight 及显式 confidence，二者分别传入研究模型。
原始 strength 与来源说明保留在 evidence.json，不冒充另一种权重解释。

**本配置未启用超图分支和事件分支。** 选中节点关联的超边与事件保存在 evidence.json，
超边保留原始成员数及子集成员，完整数据留在绑定的上传包。
实验档案记录 usedInputs / retainedOnlyInputs；结果不声称复现完整 SMEsD 研究指标。

## 打包与验收

预设与规则见 [delivery.json](delivery.json)，轻量环境及校验选项见 [打包指南](../PACKAGING.md)。

安装 uv 后，从仓库根目录执行：

```bash
./scripts/package-dataset \
  --data-dir datasets/comrisk_export_v5/smesd \
  --preset smesd --dataset-version json-v5
```

默认输出 `models/runs/datasets/smesd-json-v5.zip`，不覆盖已有文件；--output 可指定其他位置。
可加 `--set target_count=60` 进行真实小样本链路检查，不能将其指标当成模型效果结论。
工作台训练完成后，由独立进程加载、测试和预测；发布包保存人物嵌入及必要图上下文。
