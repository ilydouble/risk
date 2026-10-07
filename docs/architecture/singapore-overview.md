# 新加坡企业概览

## 定位

`/overview` 展示 ACRA/GLEIF ComRisk 新加坡导出包的数据集概况，用于开发联调和理解训练数据能力。它不是授信结果页，也不把企业状态标签解释为贷款逾期、违约概率或信用分。

页面数据分成两层：

- 全量聚合：从 2,111,884 家企业和 3,006,200 条关系直接计算统计值；
- 调试样本：按困境、正常、未标注各固定抽取 100 家，共 300 家，用于页面、API 和后续模型链路测试。

分层样本为人为均衡，不代表总体类别比例。系统不把 211 万企业逐行复制到 PostgreSQL，也不污染现有八家产品演示企业。

## 数据流

```text
ComRisk v2 ZIP
  → service.tools.sg_overview 离线校验与聚合
  → backend/seed/overview/*.json
  → 幂等 seed
  → PostgreSQL overview_snapshots(JSONB)
  → POST /api/v1/overview/get
  → React /overview、/search、/company/:datasetId/:companyId
```

生成命令：

```bash
cd models
source service/.venv/bin/activate
python -m service.tools.sg_overview \
  --source /path/to/comrisk_export.zip \
  --output ../backend/seed/overview/sg-comrisk-v2-20260925.json \
  --sample-per-class 100
```

适配器要求 v2 ZIP 中存在企业属性、标签、普通关系、三个高阶分组、风险表和导出元数据；它拒绝缺文件、重复成员与加密成员。输出记录源 ZIP 的 SHA-256，便于确认快照来源。

## 持久化和接口

`V0004` 新增全局只读 `overview_snapshots`：

- `id`：数据集版本；
- `dataset_name`：展示名称；
- `source_sha256`：源包唯一摘要；
- `payload`：聚合、质量、图结构和调试样本；
- `created_at`：入库时间。

`V0005` 允许同一源包产生多个版本化派生快照；`source_sha256` 保留普通索引用于溯源，不再作为唯一身份。种子仍使用 `ON CONFLICT DO NOTHING`，只补缺失快照、不覆盖已有数据。接口要求登录 Session，返回最新快照；没有导入时返回稳定错误码 `OVERVIEW_DATA_UNAVAILABLE`。

`/overview/search-companies` 在快照中的 300 家调试样本上执行名称/UEN/登记状态关键词检索、类别与 SSIC 筛选、排序和分页。主产品 `/search` 与顶栏联想使用这个接口；原 `/company/search` 继续只服务八家演示企业的画像与图谱链路。真实样本没有对应画像时，检索结果不会链接到演示详情页。

`/overview/get-company` 用 `datasetId + companyId` 定位一条调试样本，返回独立的真实画像契约。搜索结果进入 `/company/:datasetId/:companyId`，展示：

- 可核验的登记与经营事实；
- 原始观察标签及其任务定义；
- 按关系类型统计的一跳结构和最多 12 条邻居摘要；
- 行业、邮编地区和实体资质群组归属及全量群组规模；
- 资本、诉讼、银行征信和模型输出的数据可用性；
- 数据集版本、源包摘要和使用限制。

真实画像不复用八家演示企业的 `CompanyProfile`、评分、报告或授信组件。普通边和群组归属是结构事实，不是传染概率；未绑定有效模型制品时只显示“模型尚未运行”。

## 已知数据边界

- 标签只描述企业存续状态中的正常或清算/财务困境；行政终止保持未标注。
- 已标注企业中只有约 3.80% 出现在普通关系边里。
- 普通关系几乎全部是共享注册地址，不能等同于股权或担保关系。
- 当前导出资本字段覆盖率为 0，企业级诉讼记录为 0。
- 企业年龄存在明显观察时间混杂，年龄分布只能描述数据，不能作因果解释。

因此页面只展示数据集统计、图能力、质量和真实抽样行，不展示虚构的实时评估量、平均信用分、PD、模型指标或服务运行状态。
