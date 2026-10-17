# 英国同历史时期的对照企业

## 目标与标签

用户确认事件前 12 个月观察、1:1 对照。首版目标是**正式破产程序的研究对照**，
不是已核验所有维度健康的企业名录。

- 病例：2020—2025 年首次观测到的主要正式不良程序，每家公司取一次，合并同月证据。
- 基线：事件参考月份向前 12 个月后的月末；随访为次月至事件参考月，共 12 个月。
- 对照：同基线月份、注册编号辖区/类别及申报年龄层；2015 年以来至随访末无任何源记录。
- 对照也排除保护程序、后续转换和 bulk 条目，防止把已知异常当作正常。
- 随访后才发生事件的企业可作为更早时期的对照，不全局排除未来病例。
- 原始事件只有月份，标签沿用官方登记/裁定参考月，不虚构精确发生日。

标签 0 的含义是“官方源覆盖的窗口内未记录目标程序”，不是从未出事、无财务风险或持续经营保证。
当前无法全面核验历史存续/解散及非正式不良；自愿退出等竞争事件没有完整登记史。
正式上线或研究声称“当时持续存续的健康企业”之前，仍需补历史注册局状态及解散/恢复记录。

## 历史风险集与匹配

当前 [基础企业快照](https://www.gov.uk/guidance/companies-house-data-products) 是当前名录，
[历史快照会按月覆盖](https://forum.companieshouse.gov.uk/t/access-to-historical-bulk-data/4636)。
因此本版从 [历史电子财报归档](https://download.companieshouse.gov.uk/historicmonthlyaccountsdata.html)
建立电子申报企业候选池，不以 2026 年 Active 状态、最新名称或最新 SIC 筛选历史对照。

两组使用同样的可见性条件：观察日前 36 个月内的提交归档；会计期末不晚于观察日，
保守可用日取归档次月末且不晚于观察日。精确公开日期仍未逐份取得。
这只能证明历史电子申报证据，不能独立证明观察日仍在经营。

每个企业选最新会计期末、最新归档月份、文件名字典序最大的一份合格财报。
**不按是否有可解析金额决定入组，也不改选较旧财报来补齐金额**；两组均保留解析或披露缺失。
这与上一版财务交付“最多三份候选回退取可解析财报”的策略不同，旧交付不覆盖。

匹配条件：

1. 观察月份完全相同。
2. 编号类别相同：英格兰/威尔士数字公司、SC 公司、OC LLP、SO LLP；其余首版不纳入。
3. 归档距离观察月的月数同层：1—6、7—12、13—24、25—36。
4. 对照企业在整版中无放回抽取，不重复作为两个对照。

固定种子、公司编号哈希建立候选子池：数字及 SC 公司抽 1/16，较少的 OC/SO 全部保留。
随后在每个匹配层内按固定哈希顺序选取，不根据财务值、当前存续或未来窗口外结果选人。
`sampled-pool-counts.csv` 记录的是候选子池，不是全英国企业总体。
历史 SIC 不足，未做行业或规模匹配；事件时 SIC 和当前 SIC 不回填成基线行业。

无历史电子申报证据、基线前已出现事件或不支持辖区的病例保存在 `excluded-cases.csv`。
原始 126674 家首次观测病例及先前全部事件交付保持完整；不把电子申报总体与无证据总体混合。

## 财务、名称与建模边界

复用 [历史财务提取](uk-financials.md) 的 17 项事实、币种、上下文、金额缩放及冲突处理。
不做零填充或换汇。名称从所选历史财报取注册名称，缺失时展示公司编号并标记缺失。
两组字段覆盖率分别交付，不能用“匹配到财报”代替“所有财务指标齐全”。

`features.csv` 与 `labels.csv` 分开，允许模型使用的字段只来自 `feature-contract.json`。
公司编号、名称、样本/财报/配对 ID 及标签证据不输入模型。
同一公司可能在较早年份为对照、较晚年份为病例，切分必须按公司分组并处理时间及随访间隔。
本版未生成训练/验证/测试切分，没有训练、上线或改写企业库。
没有附同历史时点的关系边/超边，原 UK 静态图谱不能直接解释成这批样本的历史关系证据。
1:1 抽样阳性率是人为设计，模型原始分数不能直接解释为真实总体不良概率；本版未提供总体校准权重。

## 文件与复现

| 文件 | 内容 |
| --- | --- |
| `features.csv` | 观察时点的两组财务、缺失及历史展示名 |
| `labels.csv` | 0/1、随访范围、公司分组及事件证据 |
| `matches.csv` | 1:1 配对及实际匹配层 |
| `excluded-cases.csv` | 原病例未入电子申报队列的原因 |
| `baseline-reports.csv` / `baseline-facts.jsonl.gz` | 去重原始财报、状态与事实证据 |
| `matched-pairs.jsonl.gz` | 两组所选原始归档成员 |
| `sampled-pool-counts.csv` | 各月份/辖区/申报年龄层的候选数 |
| `coverage.csv` / `validation.json` | 实际覆盖、原文和标签窗口全量核验 |
| `feature-contract.json` | 允许字段、分组及时间切分要求 |

```sh
uv run --no-project --with-requirements scripts/requirements-uk-financials.txt \
  python scripts/prepare_uk_controls.py \
  --events outputs/uk-adverse-events-2020-2025-v1/events.csv \
  --event-archive datasets/sources/insolvency-service-2025-12/record-level.zip \
  --case-financials outputs/uk-financials-2020-2025-h12-v1 \
  --financial-cache datasets/sources/uk-financials \
  --cache datasets/sources/uk-controls-h12-v1 \
  --output outputs/uk-controls-2020-2025-h12-1to1-v1
```

固定输入、协议及已保存的配对可以续跑；新规则或来源应使用新版本目录。
`validate_uk_controls.py` 核对独立源记录、完整随访、配对、源 SHA/CRC、财务原值及特征隔离。
财报索引和原文独立证据包保留，原始事件 ZIP 及输入摘要随结构化包交付。
