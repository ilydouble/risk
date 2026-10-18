# 英国 Jev 日期来源核实

## 任务与状态

用户授权执行数据改进计划第1项：先核实苏格兰清算月份及实际使用财报的申报日期。
这是来源证据采集任务，不修改既有标签、财务输入或模型，也不启动训练。

2026-10-18已启动一次可续跑采集，结果目录为 `datasets/uk_source_dates_20261018/`。
完整任务尚在执行；本文件不宣称全量日期已经核实。
`job.json`记录进程、启动时间、固定脚本摘要与阶段；`pipeline.log`记录进度。
执行机器为本地Mac，未占用服务器GPU。进程停止后可利用缓存和检查点继续。

顺序为：

1. 1,077条苏格兰事件：训练254、校准26、验证357、测试440；同时核对这些企业的1,112份来源财报。
2. 实际模型输入关联的全部129,252份不同财报：训练优先35,921、校准4,042、验证45,291、测试43,998。

后四组按最早使用集合归属，报告数不是样本数；同份报告不会因跨观察使用而重复计数。
其余81,965份未关联实际模型输入的来源报告仅列入清单，不在本次自动采集范围。
`inputs.json`固定原始表摘要；独立队列不改写既有研究交付。

## 事件日期证据

[同版官方统计正文](https://www.gov.uk/government/statistics/company-insolvencies-december-2025/commentary-company-insolvency-statistics-december-2025)
将苏格兰程序按Companies House登记日期计数，不能直接等同程序开始日期。
归档内Metadata对强制清算例外的描述较笼统，需保留这一口径冲突及逐条证据。

每家企业保存官方filing-history和insolvency页面及SHA256：

- `WU01(Scot)`法院清算文件的登记日期，用于核对原始事件月份。
- insolvency页面的`wound-up-on`日期单列，不能用申请日或登记日替代。
- 任命、申请、最终解散文件不能冒充法院清算命令文件。
- 精确法院命令日期仍需命令原件证据；本采集器不会仅凭登记日标记其已核实。

`order_filing_month_matches`只表示找到同月法院命令登记文件。
未找到、页面获取失败或解析失败均保留待核实，不自动判错、不删除样本。
开始月份不同和开始时间不晚于观察月份分别标记，留给后续标签定义复核。
多个程序日期并存时不自动选择最有利日期，也不据此直接重算标签。

## 财报日期证据

使用官方登记历史的文件申报日，而非报告期末、董事签字日或下载日。
先匹配企业及报告期，再下载候选财报核对原件身份。
候选不限原始归档月份，允许发现归档月份与真实登记月份不一致。

身份确认分为两类：

- 原件字节SHA256相同。
- 官方显示层重排后，全部内联XBRL事实、上下文、单位结构相同。
  此指纹忽略展示文本空白及命名空间前缀，保留科目、报告期间、币种、scale、sign及数值。
  它是已定义的结构内容匹配，不声称整份HTML字节完全相同。

遇到多个相同原件登记、修订版无法区分、无iXBRL下载或指纹不符时保持未核实。
同企业、同报告期本身不足以确认具体版本。
登记历史未完整取得时不确认仅在部分页面发现的日期。

`filing_date_exact_verified`表示登记申报日证据核实。
`exact_publication_timestamp_verified`仍为false：当前页面不能证明当年首次上网时刻。
[官方月度财报产品说明](https://download.companieshouse.gov.uk/en_monthlyaccountsdata.html)
提供的是按月归集的电子财报产品；月度归档不能直接给出单份报告精确公开时间。
即使登记日已补齐，也不能据此宣布整个训练集通过严格真实时点验证。

## 复现与结果

```sh
python3 scripts/verify_uk_source_dates.py prepare --output datasets/uk_source_dates_new
python3 scripts/verify_uk_source_dates.py pipeline --output datasets/uk_source_dates_new --workers 8
```

联网阶段只读官方公开页面，每个采集进程最多每秒启动2次请求，失败有限重试。
同一目录只能运行一个pipeline，避免重复请求与检查点竞争。
`prepare`拒绝覆盖目录；后续采集跳过已经落盘的企业结果。
已完成但仍待核实的结果不会被假装为成功，后续复核应另存新版本。
进程异常退出应检查日志与PID，不能仅凭旧的`running`状态判断仍在采集。

主要产物：

| 路径 | 内容 |
| --- | --- |
| `event-queue.csv`、`financial-queue.csv` | 训练优先清单及原始来源信息 |
| `official-pages/`、`official-methodology.json` | 压缩官方原件、获取时间、摘要和日期口径来源 |
| `companies/*.json` | 每家待核实事件企业的独立检查点 |
| `event-verification.csv` | 事件批次结束或手动汇总后的逐条结果 |
| `financial-{partition}/*.json` | 后续各集合财报证据检查点 |
| `financial-{partition}-status.json` | 对应财报采集进度及已核实/未核实数量 |
| `financial-{partition}-verification.csv` | 对应集合批次结束后的结果 |
| `summary.json` | 最近一次汇总快照；不保证等于正在运行的实时进度 |

采集中也可运行`summarize --output <目录>`读取已有检查点，得到中间汇总。
最初探查的78家结果另存`companies-initial-probe/`及旧脚本，正式固定版本重新检查，
正式批次使用`collector-v2.py`，摘要见`job.json`。

8项契约测试覆盖申报日与描述日期区分、企业身份和页面结构、不同程序日期、
任命文件排除、原件月份不一致检出、部分历史不得确认、XBRL单位/倍率/期间变化。
训练数据修订应依据这些证据另存可追溯版本，本次不会自动清洗或重训。
