# 英国企业不良事件表

## 来源与范围

第一版使用 Insolvency Service 的 December 2025 企业级统计文件，发布于 2026-01-20。
来源为[官方发布页](https://www.gov.uk/government/statistics/company-insolvencies-december-2025)，
源 ZIP、Metadata.csv 和 README.txt 原字节随交付保留，许可为 OGL v3.0。
源数据覆盖 2015-01 至 2025-12 的英格兰、威尔士、苏格兰，不含北爱尔兰企业级记录。
这是一份冻结的统计版本，后续官方版本可能修订历史值，不代表已核实的企业当前状态。

用户选择 2020—2025 年。本源不含逐事件公告日期，因此实际筛选依据是
`month_registered`，不能称为“按公告公开日期筛选”。精确事件日及公告日保留缺失。
原先考虑的 Gazette 采集未执行，不能将其列为已核验的逐行证据。

## 数据口径

| 来源 case_type | 标准事件类型 | 默认用途 |
| --- | --- | --- |
| Compulsory Liquidation | compulsory_liquidation | 不良进入候选 |
| Creditors Voluntary Liquidation | creditors_voluntary_liquidation | 不良进入候选 |
| In Administration | administration | 不良进入候选 |
| Corporate Voluntary Arrangement | company_voluntary_arrangement | 不良进入候选 |
| Administrative Receiver | administrative_receivership | 不良进入候选 |
| Administration to CVL | administration_to_cvl | 后续程序，保留但不重复计首次进入 |
| Moratorium | moratorium | 保护程序，单独保留，不纳入默认不良进入标签 |

成员自愿清算、主动注销、个人破产不是这份源文件的上述标签类型。
`label_candidate` 还要求编号格式可关联、未标记 bulk、不是完全重复证据。
它只是生成标签的候选资格，不证明每次程序都是企业首次不良。

## 日期

- 普通类型使用 Companies House 登记月份，不能解释为程序精确开始日。
- 英格兰/威尔士强制清算使用法院裁定月份。
- 源 Metadata 对强制清算日期的表述与方法文档的地域限定存在差别；
  苏格兰强制清算保留来源月份，标记为需要核验日期口径。
- `reference_interval_start/end` 仅界定参考月份的日历边界，未用于填补事件发生日。
- `event_date`、`published_at` 留空；`source_release_date` 是整份统计文件发布日期。
- 报表中的行业和名称是事件记录属性，不能直接回填成事前预测特征。

## 主键、重复与来源

数字公司编号恢复到 8 位字符串；合法双字母前缀编号转大写并检查格式。
不会把 O 猜成 0，也不会擅自补全残缺前缀编号。特殊注册实体及缺失编号进入复核表，
原编号仍保留；格式通过不等于已经向企业注册机关核验其真实性。
源文件存在混合编码，名称逐字段优先严格 UTF-8，再以 CP1252/Latin-1 回退并标记。

每条记录保留来源 ZIP 摘要、成员名、逻辑记录号和来源字段摘要。
逻辑记录号以表头为第 1 条，不等于带引号换行的物理文件行号。
`source_row_sha256` 为 Latin-1 无损读取后的字段字典经排序、ASCII JSON 序列化后的摘要。
`event_id` 是来源摘要、成员名及记录号生成的证据记录 ID，不冒充跨版本不变的案件 ID。

全部源记录不删除。完全相同字段字典的后续记录标记 `duplicate_of_event_id`，
候选表只保留第一条。不会仅因“企业＋类型＋月份”相同而合并不同证据。

首次观测月份先用全部 2015—2025 历史计算，再筛选 2020—2025；
不能只在目标年份内取最小值而漏掉此前已出现的不良。
这仍不是首次发生的证明，2015 年前事件和源文件未覆盖的事件未知。

## 交付内容

- `events.csv`：130,250 条 2020—2025 月度源记录，含全部标准化及证据字段。
- `adverse-entry-candidates.csv`：127,915 条默认不良进入候选，保留后续多次进入。
- `first-observed-adverse-month.csv`：126,674 家企业的首次观测月，非完整生存标签。
- `review.csv`：2,205 条需核对编号、日期口径、编码或重复的记录。
- `year-type-counts.csv`：年度/类型记录数；它是事件数量，不是企业不良率。
- `英国不良事件.xlsx`：同一数据的查看视图，完整字段以 CSV 为准。
- `source/`、`report.json`、`validation.json`、`SHA256SUMS.txt`：原始证据及检查结果。

不能把未在此表出现的企业直接标为负样本。本阶段没有构造正常对照、财务特征或训练模型。
后续日级标签需另补案件/公告证据；月度预测可先使用本表，但须统一目标日期口径。

## 复现

```bash
python3 scripts/prepare_uk_adverse_events.py \
  --source-zip datasets/sources/insolvency-service-2025-12/record-level.zip \
  --output outputs/uk-adverse-events-2020-2025-v1 \
  --start 2020-01 --end 2025-12
```

输出目录必须不存在。脚本验证源 ZIP、发布版本、编号、类型及月份，不执行网络请求。
事件口径与源发布日期发生变化时应复核映射并生成新版本，不能原地覆盖。
