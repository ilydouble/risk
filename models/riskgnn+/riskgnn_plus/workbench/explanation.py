"""Single-feature interventions on frozen inputs; these are not causal attributions."""

import numpy as np
import torch


def explain(predictor, company_id: str) -> dict:
    node = predictor.index[company_id]
    context, meta = predictor.context, predictor.meta
    train = context["splits"] == "train"
    if not train.any():
        raise ValueError("Training reference population is unavailable")
    features = context["features"]
    references = np.median(features[train], axis=0)
    preprocessing = meta["preprocessing"]
    means = preprocessing.get("mean", [0.0] * len(meta["features"]))
    scales = preprocessing.get("scale", [1.0] * len(meta["features"]))
    logs = preprocessing.get("log1p", [])

    def original(value, column, name):
        raw = float(value) * scales[column] + means[column]
        if name in preprocessing.get("signedLog1p", []):
            return float(np.sign(raw) * np.expm1(abs(raw)))
        return float(np.expm1(raw)) if name in logs else raw

    original_row = features[node].copy()
    impacts = []
    with torch.inference_mode():
        baseline = float(predictor.model([node]).probabilities[0, 1])
        try:
            for column, name in enumerate(meta["features"]):
                features[node, column] = references[column]
                score = float(predictor.model([node]).probabilities[0, 1])
                features[node, column] = original_row[column]
                impacts.append({
                    "feature": name,
                    "value": original(original_row[column], column, name),
                    "referenceValue": original(references[column], column, name),
                    "probabilityAtReference": score,
                    "delta": baseline - score,
                })
        finally:
            features[node] = original_row
    return {
        "method": "training-median-intervention-v1",
        "referenceSplit": "train",
        "referenceCount": int(train.sum()),
        "features": sorted(impacts, key=lambda item: abs(item["delta"]), reverse=True),
        "sourceSha256": meta["sourceSha256"],
        "limitations": [
            "逐项将当前企业的模型输入替换为训练目标企业中位数，固定权重、嵌入和关系图。",
            "delta=原分数-替换后分数；正值表示该输入相对参考值提高分数，负值表示降低。",
            "数值为模型使用的输入值，缺失可能已填补；参考值逆变换回原单位。",
            "这不是SHAP或因果解释，各项变化不能相加；相关特征替换可能产生少见组合。",
            "关系仅作为来源证据展示，未计算单条关系的风险贡献。分类分数未经概率校准。",
        ],
    }
