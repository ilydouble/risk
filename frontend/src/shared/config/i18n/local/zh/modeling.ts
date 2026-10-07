export default {
  "modeling": {
    "title": "模型工作台",
    "subtitle": "上传数据、检查质量与划分，选择已接入的模型配置进行训练、测试和发布。",
    "disclaimer": "当前为 smoke-v1 真实子集实验：2,000 个有标签目标、固定静态图、CPU 训练。输出反映新加坡企业困境标签，不是授信违约概率；两轮训练仅用于验证链路。",
    "refresh": "刷新",
    "loading": "正在加载…",
    "scope": "仅显示当前用户的数据集、实验与模型。旧 Bundle 实验保留在数据库中，不转换为新版本。",
    "tabs": {
      "dataset": "数据集",
      "run": "实验",
      "model": "模型版本"
    },
    "errors": {
      "unavailable": "模型服务暂不可用，请稍后重试。",
      "notReady": "请等待数据集校验通过。",
      "state": "当前状态不支持此操作。",
      "missing": "找不到企业或模型资源。",
      "file": "ZIP 文件无效或超过限制。",
      "incompatible": "所选模型配置不支持当前数据协议。"
    },
    "upload": {
      "title": "上传训练数据包",
      "pick": "选择 ZIP 数据包",
      "note": "支持 comrisk_export 与 Bundle v1，最大 512 MiB。服务端按协议校验文件与数据，包内脚本不会执行。",
      "progress": "上传处理中",
      "action": "上传并校验",
      "verifiedFiles": "服务端校验文件索引"
    },
    "name": "数据集名称",
    "epochs": "训练轮数",
    "train": "创建实验",
    "cancelling": "正在取消",
    "cancel": "取消实验",
    "rerun": "重新运行",
    "trainLoss": "训练损失",
    "validationLoss": "验证损失",
    "attempt": "执行尝试",
    "report": "独立测试报告",
    "reportNote": "使用新进程重载已选检查点，仅在冻结测试划分评估；验证集用于选择检查点。",
    "publish": "发布不可变模型版本",
    "events": "执行事件与诊断日志",
    "emptyRun": "选择一个实验，或在数据集校验通过后创建实验。",
    "modelNote": "该版本绑定已测试的模型包和数据指纹。发布不会切换生产模型。",
    "download": "下载完整模型包",
    "predict": "企业预测",
    "predictNote": "只支持该模型图内的企业，一次最多 32 个 ID；结果保持输入顺序。",
    "enterpriseIds": "企业 ID（换行或逗号分隔）",
    "fillExamples": "填入模型内企业",
    "probability": "困境分类分数",
    "label": "预测标签",
    "emptyModel": "完成独立测试后，从实验中发布模型。",
    "retired": "旧基准功能已停用",
    "retiredNote": "SMEsD 基准入口已由独立 RiskGNN 模型工作台替代。历史数据与模型文件仍保留。",
    "status": {
      "pending_upload": "等待上传",
      "queued": "排队中",
      "running": "运行中",
      "ready": "校验完成",
      "failed": "失败",
      "cancelled": "已取消",
      "completed": "已完成",
      "starting": "启动中",
      "validating": "全量校验",
      "preparing": "准备子集",
      "training": "训练",
      "testing": "独立测试",
      "uploading": "上传产物",
      "expired": "租约过期",
      "retrying": "等待重试"
    },
    "metrics": {
      "rocAuc": "ROC-AUC",
      "prAuc": "PR-AUC",
      "ks": "KS",
      "brier": "Brier",
      "f1": "F1",
      "count": "测试样本数",
      "positiveCount": "测试正例数",
      "precision": "精确率",
      "recall": "召回率"
    },
    "confusion": "混淆矩阵（行：真实标签；列：预测标签）",
    "modelChoice": "模型配置",
    "catalog": "模型能力",
    "available": "可训练与发布",
    "analysisOnly": "数据分析已完成；该数据协议暂没有已接入的训练配置。",
    "dataFormat": "数据协议",
    "models": {
      "riskgnn-node-edge": "RiskGNN · 自身特征与图关系",
      "riskgnn-node-only": "RiskGNN · 仅自身特征",
      "comrisk-baseline": "ComRisk 原始基线",
      "riskgnn-plus": "RiskGNN+"
    },
    "capabilityReasons": {
      "ARTIFACT_ADAPTER_PENDING": "尚未接入模型包",
      "RESEARCH_VALIDATION_PENDING": "等待研究链路验收"
    },
    "analysis": {
    "iv": "IV",
    "mutualInformation": "互信息",
      "title": "数据分析",
      "rows": "行",
      "driftSample": "PSI 抽样行数",
      "splitCounts": "样本数 · 正例比例",
      "feature": "特征",
      "missing": "缺失率",
      "unique": "不同值数量",
      "auc": "训练集单特征 AUC",
      "validationPsi": "验证集 PSI",
      "testPsi": "测试集 PSI",
      "constant": "常量",
      "warnings": "需复核的特征",
      "correlations": "训练集特征相关性",
      "graph": "图数据概况",
      "scopes": {
        "full": "基于全部上传样本计算",
        "full_quality_sampled_drift": "全量质量统计；PSI 使用每个划分最多 5,000 行的固定抽样"
      },
      "splits": {
        "train": "训练集",
        "validation": "验证集",
        "test": "测试集"
      },
      "warningCodes": {
        "SUSPICIOUS_FEATURE_NAME": "名称可能包含 ID 或结果发生后的信息",
        "NEAR_PERFECT_TRAINING_SIGNAL": "训练集单特征信号接近完美，需检查泄漏",
        "REVIEW_FEATURE": "请检查特征定义"
      }
    },
    "profile": {
      "title": "实验档案",
      "target": "预测目标",
      "sgTarget": "新加坡企业登记困境／清算代理标签",
      "selection": "检查点选择",
      "bestEpoch": "选定轮次",
      "features": "实际特征",
      "preprocessing": "预处理拟合划分",
      "provenance": "数据与实现版本",
      "datasetHash": "数据包 SHA-256",
      "sourceHash": "模型与适配代码 SHA-256",
      "dependencies": "依赖版本",
      "criteria": {
        "validation_loss": "验证集损失"
      }
    }
  }
};
