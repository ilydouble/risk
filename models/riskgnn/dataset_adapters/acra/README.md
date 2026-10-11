# ACRA 数据适配器

## 输入与契约

- ID / 版本：`sg-comrisk / 1`；代码目录为 `acra/`，沿用既有契约 ID。
- 本机来源：仓库 `datasets/comrisk_export_v5/acra/`。
- 此目录是一个数据集；不要把含 `acra/` 和 `smesd/` 的整个交付包一起上传。
- Parquet 原始业务行留在对象存储和执行目录，不导入业务数据库。

必需文件：

```text
risk_dataset_contract.json
company_attr.parquet
label.parquet
id_map.parquet
edges.parquet
splits_5seed.parquet
feature_config.json
export_meta.json
```

可附带超图、风险表、审计说明和历史边表；包内 Python 不执行。
源 ZIP 的 SHA-256 和每个实际文件的大小/校验值由适配器记录。

## 校验与准备

`validation.py` 验证节点 ID 唯一、属性行号与 id_map 一致、边端点、有效标签掩码、
五组冻结划分覆盖及互斥，并扫描所有 Parquet。V5 的 strength、existence_confidence、
is_inferred 必须一起出现且取值有效，不能把三者合并为一个权重。

`preparation.py` 当前固定使用 `edges.parquet`，不自动切换历史边表。
`edges_bucketed` 和 `edges_by_addr_type` 同名关系的语义可能不同，不按名字猜测。

训练使用既有 `smoke-v1`：

- seed 0，保留原 train / val / test；监督只在有标签企业上计算。
- 默认选择 2,000 个目标，按划分与标签分层、稳定哈希抽取。
- 两跳上下文，每个中心最多选择四个邻居；关联方向双向化。
- 六维 A_no_priors，缺失填充统计仅在训练目标拟合。
- 边权使用单位权重，保持原训练协议；V5 的原权重、强度、置信度不进入本次前向。
- 超边和空风险表不参与 node_edge；原始证据继续保存在上传包。

`config` 可设 `target_count`（整数 6–20,000），其余字段拒绝。
这只控制训练子集，不缩减上传校验范围；结果不是全量实验或授信 PD。

## 打包

预设与规则见 [delivery.json](delivery.json)，轻量环境及校验选项见 [打包指南](../PACKAGING.md)。

安装 uv 后，从仓库根目录执行：

```bash
./scripts/package-dataset \
  --data-dir datasets/comrisk_export_v5/acra \
  --preset acra-companies --dataset-version v5
```

默认输出 `models/runs/datasets/acra-companies-v5.zip`；可用 --output 指定新路径，原目录不会被修改。

## 静态概览

`analysis.py` 提供工作台质量/划分/漂移报告；`overview.py` 与 `overview_samples.py`
保留已有概览、检索、画像使用的静态输出结构。统计从已校验的目录读取，
不再自行解压或依赖 `comrisk_export/` 固定前缀。

```bash
cd models
uv run --project service python -m riskgnn.tools.sg_overview \
  --source runs/datasets/acra-companies-v5.zip --output /tmp/acra-overview.json
```

这个工具不会写数据库，也不会覆盖仓库已有种子；样本用于调试，不代表总体比例。
目录定位属于 `paths.py`；通用 archive 模块只负责 ZIP 资源和路径限制。
