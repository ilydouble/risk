# 英国研究图谱的行业、地区及其他超边

## 范围与版本

以独立图谱 v1 为基础生成 v2，不改工作台、不覆盖旧交付。
229,907 家研究企业、58 家母公司、155 条普通并表关系、原财务、标签、事件及排除记录保留。
用户界面和文档称“不良事件企业”“对照企业”；保留原始表的 case/control 机器编码。

入口：`scripts/extend_uk_hyperedges.py`、`scripts/validate_uk_hyperedges.py`。
生成器从已经完整验证的 v1 读取，不重复联网查询 GLEIF。
SIC 校验表来自 Companies House 官方凝缩列表，下载文件和摘要随包保留。

## 超边定义

| kind | 含义 | 条数 | 成员关联 |
| --- | --- | ---: | ---: |
| shared_registered_address | 共同完整注册地址，原样保留 | 7,655 | 54,964 |
| industry_sic_division | SIC 两位行业大类 | 88 | 131,501 |
| industry_sic_subclass | SIC 五位行业细类 | 684 | 145,235 |
| postcode_area | 共同邮区 | 121 | 118,550 |
| postcode_district | 共同邮政分区 | 2,481 | 118,436 |
| registered_post_town | 同邮区内的共同登记邮政城镇 | 2,172 | 116,019 |
| legal_form | 共同法律形式 | 12 | 118,630 |
| common_direct_parent | 共同直接并表母公司的子企业集合 | 6 | 15 |
| common_ultimate_parent | 共同最终并表母公司的子企业集合 | 10 | 26 |

合计 13,229 条超边、803,376 条成员关联。至少两个不同企业才形成超边，不截断大群组。
所有超边都是群组节点 + 成员连接，不展开成企业两两连边；属性超边与关系超边分开标记。
共同母公司超边仅包含其子企业，不把母公司当成自己的子企业加入。

## 行业与地理约束

只使用同一截止 2026-09-30 的工商快照，不使用事件行业补充不良事件企业的行业成员。
企业可申报多个 SIC，保留多行业成员；同一企业在同一两位大类内只关联一次，证据保留相关槽位。
五位码必须在官方分类表中，保留前导零；99999（休眠）、74990（非交易企业）不作为实际行业。
缺失、未知、无效值不形成“未知行业”等集合。

邮编经大小写/空白正规化后做格式检验，解析 area/district；不声称已通过完整邮编目录地理编码。
登记城镇使用邮区 + 城镇组合，避免把不同邮区的同名城镇合并；不做城镇名称模糊合并。
邮政分区不是行政区；工商注册地址不是实际经营地点。
没有额外补采 ONSPD 映射，因此本版不生成“同一行政区”的超边。

依据：[ONS 邮政地理](https://www.ons.gov.uk/methodology/geography/ukgeographies/postalgeography)、
[Companies House SIC 分类表](https://www.gov.uk/government/publications/standard-industrial-classification-of-economic-activities-sic)。

## 来源、时间与使用

群组记录包含 kind、value、label、semantic_kind、层级、上级群组、来源日期/摘要、成员线类型。
membership-evidence.csv 为每条成员关联保留来源文件、逻辑记录号、记录 ID、原字段、原值及源行摘要。
快照来源记录号指 snapshot-raw-records.jsonl.gz 内从 1 开始的 JSONL 条目号；摘要对应其中原工商行。
共同母公司成员来自 edges.csv 的对应行及关系 ID；其原 GLEIF 证据继续保留。

所有超边 historical_prediction_eligible=false，不能从当前属性反推 2019—2024 年的历史群组。
SIC 大类/细类、邮区/分区/城镇是不同粒度；它们存在冗余，模型使用时应选择层级或显式处理重复贡献。
法律形式最大群组 115,150 家，是宽泛属性类别，不应理解为紧密业务联系。

没有生成共同董事、共同实际控制人、共同交易对手：当前材料缺少足够身份/交易记录。
也不按不良标签、当前困境状态或未经训练集拟合的财务相似度补造超边。

## 验证与交付

完整群组图为 enterprise-and-hyperedges.graphml，包含 229,965 企业节点、13,229 群组节点、
155 条普通关系及 803,376 条成员线；规范 CSV 同时交付。
hyperedge-type-summary.csv 报告各类型数量、覆盖企业及最大群组。
独立验证重建全部可形成群组，核对单成员排除、重复/悬空引用、原地址成员保留、
所有成员证据、分类层级、GraphML 类型/标签/引用以及原数据摘要。
