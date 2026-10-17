# 本地数据集

本目录统一保存模型实验所需的本地数据。除本说明外，数据文件默认不提交 Git；请通过受控介质、比赛数据分发渠道或已有导出包同步。

当前英国研究数据统一从 **`datasets/uk_research/`** 使用，完整压缩包为
`datasets/uk_research.zip`。不再拼接独立图谱/财务/地区扩展版本。

```text
datasets/
├── uk_research/          # 当前英国研究完整数据：财务趋势、标签、最新图及行政地区
├── uk_research.zip       # 上述目录的完整交付
├── sources/              # 原始来源与缓存
├── archive/
│   ├── uk-research-20261017/ # 旧版交付、过程输出、日志和原始证据包
│   └── imports/          # 历史导入压缩包、旧结构包和构建工具包
├── smesd/                # 上游 ComRisk 原始 pickle 与预训练嵌入
├── comrisk_export_v5/    # 新加坡 ACRA/GLEIF 和 SMEsD V5 JSON
└── uk_dataset_v1/        # 旧英国静态基准，保持原始快照
```

`uk_research/dataset.json` 是机器入口；`features.csv` 已包含多期财务与趋势，
`labels.csv` 按观察关联；全部最新行政地区与行业交叉超边已纳入图谱。
不良事件只作标签依据，不属于图结构。研究原始数据包仍须经适配器转换后才能上传工作台。
完整规则见 [统一交付](../docs/architecture/uk-unified-dataset.md)。

根目录旧 `outputs/` 已整体归档；旧 `exports/` 的离线部署包移至
`backup/distributions/`；演示数据准备样例已移除。没有删除原始研究企业或来源数据。

`models/baseline/data` 是指向 `datasets/smesd` 的符号链接。原始 SMEsD 文件固定来自 `shaopengw/ComRisk` 提交 `a80524b3b67436cd2f74755f6ffa08a554ff2d02`：

| 文件 | SHA-256 |
| --- | --- |
| `train_data.pkl` | `73e69100353945bf4e2c99cb8c057093d7fc9f4640f5271dc3d68bbf327f1e5c` |
| `validate_data.pkl` | `b1614e44f0eb8c3133fbcdf47922ff263fd65a76289b75605ab2a3f047a1e8bb` |
| `test_data.pkl` | `c58a1d3af63330105c889cf03f9cdaf312592f30a66a3bb488b45eb0ef38da4d` |
| `split_data_idx.pkl` | `d81780ffcad976cb6977fc5bb74b7e3a6085623c982eb824383c3aaba358c035` |
| `node2index.pkl` | `23aaa7493490fde5cee6fbc3cf72ac2920ba39566bb6f94c85c4c28dd01cc47c` |
| `meta_emb.pkl` | `ee065231bf2f7801bfb72052a97ab77437e27120dacdf08648b3062ab649a42d` |

pickle 可能执行任意代码，只允许加载固定来源且哈希匹配的文件。新加坡标签是登记困境/清算代理，不是贷款违约；该数据用于方法学对照和工程验证，不代表格兰德正式赛题数据。

工作台必须按单个数据集打包并添加契约；原始 Pickle 不直接上传。
专用说明见 [ACRA](../models/riskgnn/dataset_adapters/acra/README.md)、
[SMEsD](../models/riskgnn/dataset_adapters/smesd/README.md)、
[UK](../models/riskgnn/dataset_adapters/uk_dataset_v1/README.md)。
