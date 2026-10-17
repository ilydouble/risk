# 英国研究图谱的标签隔离

不良事件只用于构造观察级监督标签，不属于图结构、图特征或群组依据。
本次仅调整独立英国研究数据包，不涉及系统图谱页面。

## 当前交付

入口：`scripts/isolate_uk_graph_labels.py`。默认读取已验证的
`outputs/uk-research-graph-20261017-v3`，生成新目录
`outputs/uk-research-graph-20261017-labels-only-v1` 及 ZIP/SHA256。
拒绝覆盖已有目录；先核对基线交付清单的所有文件摘要。

- 移除根目录 `events.csv`、`event-node-links.csv`、`out-of-scope-events.csv`。
- 当前 `graph-manifest.json` 不再声明 `eventJoin`，监督标签独立声明。
- `nodes.csv` 及全部 GraphML 移除 `event_reference_*` 属性。
- 事件来源的显示名称改为已有历史财报名；没有历史名称时回退企业编号，
  不据此删除企业。登记和 GLEIF 名称保持不变。
- 企业 ID、普通边、超边、成员、观察映射保持不变。
- `labels.csv`、财务、配对和排除清单原字节保留。

`labels.csv` 按 `sample_id` 表示观察与预测窗口的标签。
通过 `node-observations.csv` 关联企业；同一企业的多个观察不合并为单一节点标签。
独立多期财务扩展仍按 `sample_id` 和 `company_id` 关联。

## 证据和历史档案

原事件表、源记录和旧包保持在原目录，不删除原始证据。
保留的 `company-reference.csv` 等源审计表可能包含 `event_reference_*`，
这些列仅解释原始来源，不属于 `nodes.csv` 或图特征契约。
旧版 `code/`、`base-*`、`provenance/` 是复现档案，旧 `eventJoin` 声明不再生效；
当前使用根目录 `graph-manifest.json`。本版转换脚本随包保存。

## 验证

转换完成后独立核对：所有企业 ID、每个 GraphML 节点集合及边内容摘要相同，
全部 GraphML 的事件属性消失，企业节点属性与当前 CSV 一致；
标签、财务、配对、排除清单、普通边及群组成员摘要均与基线相同。
重建完整交付清单，打包后检查 ZIP CRC 并写入 SHA256。

已有当前登记近似历史观察的研究假设继续沿用；
标签隔离不改变图关系的历史可用性限制。
