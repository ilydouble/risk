# UK 企业数据体检样例

将 [uk-company-profile-demo.csv](uk-company-profile-demo.csv) 上传到侧栏「数据准备」。
该页面目前接收单张 UTF-8 CSV；本文件带 UTF-8 BOM，便于常见表格软件打开。

样本来自 `datasets/uk_dataset_v1/train.json` 的企业节点。按企业 ID 的 SHA-256
排序，选取 96 条标签 0 和 4 条标签 1；只用于展示数据体检，不能代表完整 UK 数据分布，
也不包含图的原始边或超边。`adverse_status` 是登记状态快照：
1 表示企业正处于困境程序，0 表示 Active，不能解释为未来违约标签或违约概率。

为了测试脏数据检测，样例在抽样后作了三处**演示性改动**：

- 第一行的 `n_charges` 清空。
- 第二行的 `max_span` 写为「未知」。
- 复制第三行作为最后一行。

因此上传后应看到 101 行、1 行完全重复，`n_charges` 和 `max_span` 各缺失 1 个值。
源数据中还有 4 行 `community` 为「未知」，当前体检规则也会将它计为缺失。
原始 UK 数据和模型训练集均未修改。智能体建议只供确认；此样例不能直接训练 RiskGNN+。
