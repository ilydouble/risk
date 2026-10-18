# UK 财务 JSONL 接入

该适配器用于把已准备好的财务观测导入工作台，供部署的 Qwen3-0.6B LoRA 推理。
它不训练 RiskGNN，也不把旧 UK 七维注册/图特征转换为财务值。

## 交付文件

- `train.financial.jsonl`、`valid.financial.jsonl`、`test.financial.jsonl`：原始导出的 state/questions/expected。
- `sample-index.jsonl`：split、从 1 开始的 line、sample_id、company_id、观测月及 12 月目标窗口。
- `manifest.json`：`uk-labelled-decisions-v1`，来源文件摘要、大小、目标定义和各划分统计。

manifest 中可能列出 graph JSONL；本协议只消费上述财务文件，不要求或使用 graph 文件。
每行最多 1 MiB；总观测索引最多 500,000 条，ZIP 沿用 512 MiB/解压 2 GiB 的现有限制。
期望标签只用于来源统计与浏览，不进入预测提示。计数单位是带日期的观测，不是去重企业。

## 打包与使用

```bash
./scripts/package-dataset --preset uk-financial \
  --data-dir /path/to/full --dataset-version 20261018
```

上传生成的 ZIP 到模型工作台，完成全量校验和企业导入后，
可让助手调用 financial_risk_catalog → financial_risk_companies → predict_company_financial_risk。
预测必须复制 recordId；companyId 是注册编号，同一企业可能有多个观测期。

冻结协议来自 `models/uk_decision/releases/uk-financial-0.6b-v1/input-contract.json`。
校验检查每份文件摘要、所有行的字段/问题/标签、索引引用和统计，保留原划分。
企业导出保留数值、布尔值、字符串和缺失属性，不做标准化、填零或重新划分。
该包没有关系数据，图谱仅能显示企业节点，不能作为模型图解释。

模型服务负责输入转换和评分；业务后端负责账号与来源范围、版本和预测历史。
部署与模型数值范围见 [功能文档](../../../../docs/features/uk-decision-model/README.md)。
