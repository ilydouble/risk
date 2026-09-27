export default {
  modeling: {
    eyebrow: "Metadata-driven Risk Modeling",
    title: "元数据驱动风险建模工作台",
    subtitle: "上传外部适配器生成的标准 ZIP 数据包，由本地 Worker 完成数据分析、特征选择、模型阶梯训练与消融评估。",
    retry: "刷新", loading: "正在加载…",
    empty: "还没有标准数据包。请先使用外部适配脚本生成 Bundle v1 ZIP。",
    datasets: "数据包", experiments: "比较实验",
    steps: { data: "数据包", quality: "数据分析", build: "实验构建", evaluate: "模型评估" },
    task: { loan_application: "贷款申请风险", entity_snapshot: "企业经营风险", legacy_tabular: "旧版表格数据" },
    status: { pending_upload: "等待上传", queued: "已排队", running: "运行中", ready: "分析完成", completed: "实验完成", failed: "失败", legacy: "旧版只读" },
    welcome: { title: "从标准数据包开始", subtitle: "系统不做客户字段映射，只接受已经物化 samples 表并声明标签、划分和图快照的 Bundle v1。" },
    upload: { title: "上传标准数据包", subtitle: "RustFS 直传，Worker 异步校验", drop: "拖入 ZIP 或点击选择", limit: "Bundle v1 · 最大 512 MB · CSV / Parquet", name: "数据集名称", namePlaceholder: "例如：赛题贷款申请样本 v1", action: "上传并排队分析", uploading: "正在上传…", queueing: "正在创建分析任务…" },
    bundle: { title: "数据包清单", schema: "契约版本", task: "任务语义", status: "处理状态", rows: "样本数", target: "标签定义", positive: "风险正类", window: "预测窗口", files: "文件清单", staticWarning: "该数据包声明为静态图方法实验，不得将结果描述为严格未来预测。" },
    analysis: { views: { quality: "质量", signal: "特征信号", drift: "划分漂移", graph: "图结构" }, rows: "样本数", columns: "字段数", duplicates: "重复样本 ID", leakage: "泄漏提示", fields: "字段画像", field: "字段", group: "特征组", type: "类型", missing: "缺失率", unique: "唯一值", leakageHints: "潜在泄漏", signalTitle: "训练集单变量信号", graphTitle: "图结构画像", noGraph: "数据包没有合法图组件，仅开放表格模型。", noRawPreview: "为保护客户数据，工作台不保存或展示原始行预览。" },
    builder: { title: "构建比较实验", subtitle: "使用固定划分横向运行基线、图统计和 GNN 消融", name: "实验名称", target: "目标", seed: "随机种子", featureMode: "特征模式", recommended: "推荐特征", manual: "手工选择", models: "模型阶梯", events: "事件编码", relations: "关系传播", hyperedges: "超图传播", requiresGraph: "需要合法 nodes + relations 快照", requiresHyper: "需要 hyperedges", method: "所有填补、缩放、类别词表和特征选择仅在训练划分拟合；验证集用于早停和阈值，测试集只做最终报告。", run: "排队运行实验", queueing: "正在创建任务…" },
    result: { completed: "实验已完成", comparison: "模型阶梯与消融比较", duration: "耗时", threshold: "阈值评估", explainability: "解释结果", relationGate: "自身风险门均值", hyperWeights: "超边类型权重" },
  },
};
