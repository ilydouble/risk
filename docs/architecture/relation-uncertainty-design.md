> 本文包含历史问题和后续设计。当前工作台仍采用已验收的单位边权协议，置信度实验尚未作为服务能力开放。

# 关系强度与不确定性设计

建图分层与超图/事件节点取舍见[建图设计](graph-construction-design.md)。本篇处理关系强度与存在
置信度如何拆分、如何进入传播。

## 如何处理关系不确定性

这个问题目前确实没有被充分表达。

当前 Bundle 的关系只有：

```
graph_snapshot_id
source_id
target_id
relation_type
weight
```

并且只校验 `weight > 0`，见 [data.py (line 137)](../../models/service/datasets/bundle/data.py)。超边也只有类型、编号和成员，没有置信度，见 [data.py (line 168)](../../models/service/datasets/bundle/data.py)。

更重要的是，当前 RiskGNN 将 `weight` 放入注意力：

```
alpha = softmax(attention_logit + log(weight))
```

见 [model.py (line 73)](../../models/riskgnn/gnn.py)。

这意味着当前 `weight` 表达的是“邻居之间的相对传播强度”，并不是“这条边存在的概率”。两者不能混用。例如一个节点只有一个邻居时，即使其 `weight=0.01`，softmax 后仍然可能得到接近 1 的注意力，它不会真正削弱这条低可信边的影响。

### 应当拆分的关系字段

建议关系至少增加：

```
relation_id
relation_type
source_id
target_id

strength               # 业务强度，如持股比例、担保金额
existence_confidence   # 关系存在的可信度，0~1
source_system          # 工商、司法、人工、第三方推断
evidence_count
observed_at
valid_from
valid_to
is_inferred
```

其中：

- `strength` 回答“关系有多强”；
- `existence_confidence` 回答“我们有多相信它存在”；
- `source_system` 回答“为什么相信它”；
- `is_inferred` 区分事实关系和模型推断关系。

如果置信度没有经过校准，不要轻易把它称为概率。可以先使用 `A/B/C/D` 证据等级，在敏感性实验中映射为不同区间。

超边则需要两种置信度：

- `hyperedge_confidence`：这个群体关系是否真实存在；
- `membership_confidence`：某个节点是否真的属于该群体。

### 模型层面的建议

最实用的方案不是立即上完整贝叶斯 GNN，而是分三步。

第一步：确定图对照

同时训练：

- 表格基线；
- 只使用高可信边的 RiskGNN；
- 使用全部边但忽略置信度的 RiskGNN。

这样首先能判断低可信关系究竟带来提升还是噪声。

第二步：置信度感知传播

关系强度仍参与邻居间的注意力竞争：

\[ \alpha_{ij}=\operatorname{softmax}(a_{ij}+\log s_{ij}) \]

但置信度放在归一化之后：

\[ m_i=\sum_j q_{ij}\alpha_{ij}W h_j \]

其中：

- \(s_{ij}\) 是业务强度；
- \(q_{ij}\) 是关系存在置信度。

这样即使一个节点只有一个低可信邻居，`q=0.1` 也会让传播消息真正缩小，而不是被 softmax 重新放大到 1。

第三步：随机图推理

对于不确定边：

\[ z_{ij}\sim\operatorname{Bernoulli}(q_{ij}) \]

每次推理抽样一张可能的图，重复例如 20–50 次，最终输出：

- 平均风险概率；
- 5%–95% 风险区间；
- 不同图采样下的标准差；
- 对关系不确定性的敏感程度。

这样系统不再只输出“风险为 0.73”，而可以输出：

```
平均风险：0.73
图不确定性区间：0.61–0.81
主要不确定来源：两条推断控制关系、一条低可信共同地址关系
```

这比把不确定关系当成确定事实更适合人工风控复核。

## 对当前项目的具体建议

下一版不需要重新变成多个产品算法，可以仍然只有一个 RiskGNN，但增加三个实验配置：

| 配置                      | 作用                           |
| ------------------------- | ------------------------------ |
| `self_only`               | 不使用图，判断企业自身信息上限 |
| `high_confidence_graph`   | 只使用高可信事实关系           |
| `uncertainty_aware_graph` | 使用全部关系并显式建模置信度   |

同时保留 HGB 作为表格基线。这样比较的是同一个 RiskGNN 的信息与鲁棒性消融，不会再次造成“多个算法合并还是拆分”的概念混乱。

我建议优先顺序是：

1. 先扩展 Bundle 契约，分离 `strength` 和 `confidence`。
2. 为关系和超边增加来源、时间及推断标记。
3. 建立“无图／高可信图／全图”三组对照。
4. 再实现置信度感知传播。
5. 最后加入随机图推理和预测区间。

最重要的设计原则是：图不仅要记录“谁和谁相连”，还必须记录“为什么相连、何时相连、我们有多相信这条关系”。否则 GNN 的传播能力越强，错误关系造成的风险扩散反而越严重。
