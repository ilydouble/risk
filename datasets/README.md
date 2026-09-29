# 本地数据集

本目录统一保存模型实验所需的本地数据。除本说明外，数据文件默认不提交 Git；请通过受控介质、比赛数据分发渠道或已有导出包同步。

当前约定：

```text
datasets/
├── smesd/                # 上游 ComRisk 原始 pickle 与预训练嵌入
└── comrisk_export_v5/
    ├── acra/             # 新加坡 ACRA/GLEIF 横截面数据
    └── smesd/            # SMEsD 的 V5 JSON 转换快照
```

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
