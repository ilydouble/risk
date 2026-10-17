# UK 数据重新交付

## 范围

本次是历史研究快照的名称补充与语义修订，不是重新采集后的英国全量登记库。
原始目录 `datasets/uk_dataset_v1` 保留不变，新版本写入独立目录。
ID、标签、七维原始特征、训练划分、边端点/类型码/权重、群组成员和事件均保持不变。
转换脚本比较三个快照的训练数据指纹，任一变化即失败。

## 名称与来源

名称来源为 Companies House 官方 `BasicCompanyDataAsOneFile-2026-10-01.zip`。
按官方月度数据说明，其截止日期为 2026-09-30；这是名称来源时点，不能当成历史标签时点。
源 URL、下载字节 SHA-256、CSV 成员名和逻辑记录号保存在每个匹配节点的
`properties.nameSource` 中，经企业导出保留到工作台。逻辑记录号以表头为第 1 条，
不等于包含引号内换行的物理文本行号。

源文件保存在 `datasets/sources/companies-house-2026-10-01/`，不提交 Git。
包内 `name-evidence.csv` 仅保留匹配的官方名称记录，用于核对；官方源 ZIP 不重复塞入上传包。
关联使用字符串 ID，保留前导零；重复源编号直接报错，不任取一条。
未匹配企业的名称为 null，单列在 `unmatched-companies.csv`，页面回退显示 ID。
名称源中的公司状态仅作为名称来源的附加证据，不替换训练标签。

来源：[官方批量下载](https://download.companieshouse.gov.uk/en_output.html)。
Contains public sector information licensed under the
[Open Government Licence v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/).

## 关系解释

为了兼容既有适配器，保留历史关系类型码；用 `relation_kind` 补充语义：

| 类型码 | relation_kind | 解释 |
| --- | --- | --- |
| SAME_ADDRESS | shared_registered_address | 共享注册地址，不表示控制或持股 |
| EQUITY | accounting_parent_type_unspecified | 历史 GLEIF 母公司关系，原包未区分直接/最终母公司 |
| PREVNAME | previous_name_association | 原包的曾用名关联，不能视为所有权证据 |
| SAME_NAME | same_name_association | 原包的同名关联，不能视为所有权证据 |

普通关系增加稳定的 `relation_id` 与来源系统描述，不新增或删减边。
GLEIF 历史边缺少原始关系记录，本次不声称已重新核验其类型、方向与有效日期。
`weight` 保留为历史模型权重，不复制到 `existence_confidence`，不解释为持股比例。
行业/邮区群组标成属性群组，董事群组标成上游姓名匹配生成的关系群组。

## 保留的研究限制

- 标签是登记困境状态，不是未来违约概率；本次不训练或发布模型结果。
- 年龄按原脚本 2025-12-31 计算，其他来源时点不完整；不假装统一到名称快照日期。
- 董事特征依赖上游姓名匹配，原始身份记录不可用，不能保证消歧正确。
- 保留按地址组的划分和切分前计算的网络特征，不认证无泄漏或总体代表性。
- 样本为 LEI 锚点及其同址邻居，不覆盖全部英国企业。

历史审计原字节保存在包内 `legacy-audit/`，当前 `audit.json` 和 `export_meta.json`
重新计算快照摘要并引用旧摘要、训练数据指纹和名称源。新旧数据版本不可混用摘要。

## 复现与验证

从仓库根目录执行，输出目录必须不存在：

```bash
python3 scripts/redeliver_uk_dataset.py \
  --source-dir datasets/uk_dataset_v1 \
  --names-zip datasets/sources/companies-house-2026-10-01/BasicCompanyDataAsOneFile-2026-10-01.zip \
  --output datasets/archive/uk-research-20261017/uk-redelivery-20261017-v2 \
  --version 20261017-named-v2 --names-date 2026-09-30 \
  --names-url https://download.companieshouse.gov.uk/BasicCompanyDataAsOneFile-2026-10-01.zip
```

然后使用 `scripts/package-dataset` 的 `uk-companies` 预设打包 `data/`，
采用已更新、支持节点 `name` / `properties` 的模型环境执行完整 inspect。
企业 JSONL 导出核对名称/来源/计数，准备阶段验证新旧训练张量一致；不以打包成功代替全量校验。
上传单独的工作台 ZIP，新建数据集版本；外层资料 ZIP 用于归档，不直接上传。
