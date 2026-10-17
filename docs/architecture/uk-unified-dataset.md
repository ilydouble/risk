# 英国研究数据集统一交付

当前入口固定为 `datasets/uk_research/`，完整交付为 `datasets/uk_research.zip`。
用户不再需要将图谱、财务历史与行政地区扩展包手工拼接。
原始缓存继续在 `datasets/sources/`；旧输出集中在 `datasets/archive/uk-research-20261017/`。

## 当前数据

- `dataset.json`：统一入口与关联键、上游摘要。
- `features.csv`：209,192 条观察，包含原财务/基本信息及多期趋势字段。
- `labels.csv`：观察级不良标签，按 `sample_id` 关联，保持原字节。
- `feature-contract.json`：多期财务版本的编码候选字段契约。
- `nodes.csv`、`edges.csv`：229,965 企业节点、155 并表关系。
- `groups.csv`、`group-memberships.csv`：50,226 超边、1,530,711 成员关联。
  包含原行业/邮政群组、行政地方当局/英格兰大区及行业×行政地区群组。
- `node-observations.csv`：企业与观察映射。
- `observation-geography.csv`：全部观察的地区侧表。
- `financial-history.csv`、`sample-history-links.csv`：财务期间版本及观察选择。
- `enterprise-and-hyperedges.graphml`：当前完整图，另保留企业关系专用 GraphML。
- `sources/` 和行级证据：来源副本与可追溯信息；基础原件缓存仍在上级 `sources/`。
- `audit/`：上游历史清单、说明和审计，不作为当前特征或标签入口。

不良事件不作为节点、边、超边或图属性；事件源只用于监督标签与来源审计。
节点移除事件来源行业字段，事件来源名称使用历史财报名或企业编号。
原始研究企业、样本、标签与排除原因不变。

## 复现与验证

```bash
python scripts/consolidate_uk_research.py
```

脚本先验证最新行政地区图谱与多期财务交付的全部摘要。
逐观察核对多期特征包含原始列及原值，标签字节相同，地区侧表覆盖所有样本。
清理全部 GraphML 的事件属性，核对节点集合与每条边的内容摘要不变；
普通边、超边、成员及证据与上游版本一致。
输出 `validation.json`、全量 `delivery-manifest.json`、ZIP 及 SHA256，检查 ZIP CRC。
已有目标目录或 ZIP 时拒绝覆盖；更新时先指定暂存目录并审核结果。

原始研究表仍需适配成工作台协议后才能上传，不将研究 ZIP 宣称为工作台输入包。
现有当前登记近似历史观察假设不变；精确申报日和历史地址/关系未核实。

## 目录整理

根目录 `outputs/` 整体移入数据归档，未删除唯一原件。
英国生成脚本和复现文档同步使用归档路径，不再默认写根目录 `outputs/`。
`datasets/` 根目录历史 ZIP 归入 `archive/imports/`；
根目录离线部署包 `exports/` 移至 `backup/distributions/`。
移除 `examples/data-prep/` 的三份演示文件；真实数据与模型源码保留。
旧清单内绝对路径仍是采集时的历史证据；当前路径以目录说明和统一入口为准。
