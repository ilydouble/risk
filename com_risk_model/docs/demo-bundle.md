# SMEsD 数据与模型来源

474 家匿名测试企业、关联个人节点、观测关系及司法事件编码来自 SMEsD。
本仓库保留测试快照；训练/验证快照、原始 pickle 和其他实验权重不随 Git 提交。

## 来源与处理

- [ComRisk 官方仓库](https://github.com/shaopengw/ComRisk)，固定提交
  `a80524b3b67436cd2f74755f6ffa08a554ff2d02`。
- `training/fetch_smesd.py` 下载并校验固定的四个原始文件；`training/smesd.py` 转换。
- 按 train、valid、test 的先后归属消除跨集重复，原测试 491 家变为 474 家。
  资本 log1p、边权转换和端点过滤规则保持原实现。
- ComRisk-inspired 独立实现使用公开训练集，验证集选择、校准和拟合阈值。
  测试标签只用于评估，不用于参数更新。
- `smesd-v1-summary.json` 原样保留 18 次历史实验；选中 `no_hyper-seed42`。
  其中 `backend/artifacts/` 路径是历史记录，其他 17 个权重目录未提供。
- `legacy-demo-bundle-manifest.json` 原样保留合并时的来源和 SHA-256，旧路径仅用于追溯。
  当前加载使用 `weights/<版本>/manifest.json`，不读取历史清单。

## 本轮迁移

当前 `smesd-v1` 由原有已选权重迁移，weights、metadata、metrics 的字节完全保留。
测试快照移动到 `data/processed/smesd/test.json`，SHA-256 不变：
`5f9db7f71e2b3a797c0c6576207d2d5dc63ee9d188031f1320450b8b74492224`。

原清单不再用于服务加载，正式包采用清单版本 1、runtime API 版本 1，元数据仍为格式 2。
文件来源与现有数值回归已验证，本轮没有重新训练正式模型，没有发布 GitHub Release。
包的导出、手工分发和加载见[产物约定](../../docs/architecture/model-artifacts.md)。

## 范围与许可

此数据用于公开基准破产分类，不是未来固定窗口违约概率，不证明东南亚企业泛化。
特征遮蔽解释不是 SHAP，线性分数不是业务评分卡。
公开可下载与明确的再分发许可并不等同；当前尚未确认上游的明确再分发许可。
保留来源不构成对第三方数据重新授权，对外分发前需确认适用条款。
