"""Re-score every voting member under the same attribute intervention."""

import numpy as np
from riskgnn_plus.workbench.explanation import original_value

from riskgnn.workbench.attribute_baselines import BoostedTrees
from riskgnn.workbench.graph_to_state import ALGORITHM as G2S
from riskgnn.workbench.graph_to_state import transform


def intervention_score(algorithm, predictor, company, column, reference, training):
    node = predictor.index[company]
    context = predictor.context
    if algorithm == G2S:
        features = context["features"]
        previous = features[node, column]
        try:
            features[node, column] = reference
            view, _ = transform(context, predictor.meta, reference_values=training)
            trees = BoostedTrees(predictor.trees.weights, view[node : node + 1])
            return float(trees.scores([0])[0])
        finally:
            features[node, column] = previous

    if algorithm in {"gcn", "rgcn", "hgt"}:
        mapping, features, *_ = predictor.model.graphs[str(context["snapshots"][node])]
        node = int(mapping[node])
    else:
        features = context["features"]

    previous = float(features[node, column])
    try:
        features[node, column] = float(reference)
        return predictor.predict([company])[0]["probability"]
    finally:
        features[node, column] = previous


def explain(context, meta, company, predictors, baseline):
    node = predictors[0].index[company]
    training = context["features"][context["splits"] == "train"]
    if not len(training):
        raise ValueError("Training reference population is unavailable")
    references = np.median(training, axis=0)
    original = context["features"][node]
    voting = baseline["voting"]
    features = []
    for column, (name, reference) in enumerate(zip(meta["features"], references, strict=True)):
        members = []
        for member, predictor in zip(voting["members"], predictors, strict=True):
            score = member["score"]
            if original[column] != reference:
                score = intervention_score(
                    member["algorithm"], predictor, company, column, reference, training,
                )
            members.append({
                "algorithm": member["algorithm"],
                "scoreAtReference": score,
                "delta": member["score"] - score,
                "voteAtReference": int(score >= member["threshold"]),
            })
        votes = sum(member["voteAtReference"] for member in members)
        features.append({
            "feature": name,
            "value": original_value(meta, original[column], column),
            "referenceValue": original_value(meta, reference, column),
            "positiveVotesAtReference": votes,
            "predictedLabelAtReference": int(votes >= voting["requiredVotes"]),
            "members": members,
        })
    features.sort(key=lambda row: (
        row["predictedLabelAtReference"] != baseline["predictedLabel"],
        sum(before["vote"] != after["voteAtReference"]
            for before, after in zip(voting["members"], row["members"], strict=True)),
        max(abs(member["delta"]) for member in row["members"]),
    ), reverse=True)
    return {
        "method": "voting-training-median-intervention-v1",
        "referenceCount": len(training),
        "sourceSha256": meta["sourceSha256"],
        "features": features,
    }
