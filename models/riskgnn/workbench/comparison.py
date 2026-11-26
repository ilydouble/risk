"""Run and publish graph comparisons with a shared preparation and fixed majority voting."""

import shutil
from itertools import combinations
from pathlib import Path
from time import monotonic

import numpy as np
import torch
from sklearn.metrics import average_precision_score, precision_recall_curve

from riskgnn.workbench.artifacts import read_json, seal, verify, write_json
from riskgnn.workbench.attribute_baselines import BoostedTrees, train_boosted_trees
from riskgnn.workbench.graph_baselines import baseline_network, train_baseline
from riskgnn.workbench.graph_to_state import ALGORITHM as G2S_ALGORITHM
from riskgnn.workbench.graph_to_state import FEATURES_FILE, transform

FORMAT = "riskgnn-comparison-v1"
PLUS = "riskgnn-plus"


def by_id(predictor, ids):
    return np.array([item["probability"] for item in predictor.predict(ids)])


class BaselinePredictor:
    def __init__(self, directory, context, meta, index, algorithm):
        weights = torch.load(
            directory / f"{algorithm}.pt",
            map_location="cpu",
            weights_only=True,
        )
        self.trees = None
        if algorithm in {"gbdt", G2S_ALGORITHM}:
            features = (
                np.load(directory / FEATURES_FILE, allow_pickle=False, mmap_mode="r")
                if algorithm == G2S_ALGORITHM
                else context["features"]
            )
            self.trees = BoostedTrees(weights, features)
        else:
            self.model = baseline_network(algorithm, meta, context)
            self.model.load_state_dict(weights)
            self.model.eval()
        self.context, self.meta, self.index = context, meta, index

    def predict(self, ids):
        if self.trees is not None:
            targets = [self.index[name] for name in ids]
            return [
                {"companyId": name, "probability": float(score)}
                for name, score in zip(ids, self.trees.scores(targets), strict=True)
            ]
        groups = {}
        for pos, name in enumerate(ids):
            index = self.index[name]
            groups.setdefault(str(self.context["snapshots"][index]), []).append((pos, index))
        rows = [None] * len(ids)
        with torch.inference_mode():
            for snapshot, group in groups.items():
                scores = self.model(snapshot, [index for _, index in group]).softmax(1)[:, 1]
                for (pos, _), score in zip(group, scores, strict=True):
                    rows[pos] = {"companyId": ids[pos], "probability": float(score)}
        return rows


class Comparison:
    def __init__(self, directory):
        verify(directory, FORMAT)
        self.directory = directory
        self.meta = read_json(directory / "metadata.json")
        self.ids = read_json(directory / "ids.json")
        self.index = {name: i for i, name in enumerate(self.ids[: self.meta["companyCount"]])}
        with np.load(directory / "context.npz", allow_pickle=False) as data:
            self.context = dict(data)

    def member(self, algorithm):
        if algorithm == PLUS:
            from riskgnn_plus.workbench.predictor import PlusPredictor

            return PlusPredictor(self.directory / PLUS)
        return BaselinePredictor(self.directory, self.context, self.meta, self.index, algorithm)

    def split(self, name):
        indices = np.flatnonzero(self.context["splits"] == name)
        return [self.ids[i] for i in indices], self.context["labels"][indices]

    def predict(self, ids, members=None, *, explain=False):
        rows = {m["algorithm"]: m for m in self.meta["members"] if m["status"] == "completed"}
        members = self.meta["recommended"] if members is None else members
        if len(members) != 3 or len(set(members)) != 3 or not set(members) <= rows.keys():
            raise ValueError("Majority vote requires three successful comparison members")
        if missing := next((name for name in ids if name not in self.index), None):
            raise KeyError(f"Unknown bound-graph enterprise: {missing}")
        if explain and len(ids) != 1:
            raise ValueError("Explanation requires one company")
        predictors = [self.member(name) for name in members] if explain else []
        scores = [by_id(predictor, ids) for predictor in predictors] if explain else [
            by_id(self.member(name), ids) for name in members
        ]
        thresholds = [rows[name]["threshold"] for name in members]
        predictions = []
        for company, company_scores in zip(ids, zip(*scores, strict=True), strict=True):
            details = [
                {
                    "algorithm": name,
                    "score": float(score),
                    "threshold": threshold,
                    "vote": int(score >= threshold),
                }
                for name, score, threshold in zip(members, company_scores, thresholds, strict=True)
            ]
            votes = sum(detail["vote"] for detail in details)
            predictions.append(
                {
                    "companyId": company,
                    "probability": votes / len(details),
                    "predictedLabel": int(votes >= 2),
                    "scoreKind": "vote_share",
                    "voting": {"positiveVotes": votes, "requiredVotes": 2, "members": details},
                }
            )
        if explain:
            from riskgnn.workbench.voting_explanation import explain as explain_vote

            predictions[0]["votingExplanation"] = explain_vote(
                self.context, self.meta, ids[0], predictors, predictions[0],
            )
        return predictions


def best_threshold(labels, probabilities):
    precision, recall, thresholds = precision_recall_curve(labels, probabilities)
    den = precision[:-1] + recall[:-1]
    scores = np.divide(2 * precision[:-1] * recall[:-1], den, out=np.zeros_like(den), where=den > 0)
    return float(thresholds[np.flatnonzero(scores == scores.max())[-1]])


def train_comparison(prepared: Path, output: Path, configuration, emit):
    from riskgnn_plus.workbench.predictor import PlusPredictor
    from riskgnn_plus.workbench.training import train as train_plus

    from riskgnn.workbench.training import code_version

    verify(prepared, "riskgnn-prepared-v1")
    parameters = configuration["resolvedParameters"]
    epochs = parameters["epochs"]
    output.mkdir(parents=True, exist_ok=True)
    for name in ("metadata.json", "ids.json", "context.npz"):
        shutil.copy2(prepared / name, output / name)
    meta = read_json(output / "metadata.json")
    ids = read_json(output / "ids.json")
    index = {name: i for i, name in enumerate(ids[: meta["companyCount"]])}
    with np.load(output / "context.npz", allow_pickle=False) as data:
        context = dict(data)
    validation = np.flatnonzero(context["splits"] == "val")
    valid_ids = [ids[i] for i in validation]
    y = context["labels"][validation]
    members = []
    for algorithm in parameters["comparison"]:
        started = monotonic()
        weights = output / f"{algorithm}.pt"
        emit({"kind": "stage", "stage": "training", "message": algorithm})

        def metric(row, algorithm=algorithm):
            for key, group in (("trainLoss", "train"), ("validationLoss", "validation")):
                emit(
                    {
                        "kind": "metric",
                        "name": "loss",
                        "group": f"{algorithm}:{group}",
                        "value": row[key],
                        "step": row["epoch"],
                    }
                )

        view = None
        try:
            if algorithm == PLUS:
                profile = train_plus(
                    prepared,
                    output / PLUS,
                    epochs,
                    configuration=configuration,
                    metric_callback=metric,
                )
                selected = profile["selectedEpoch"]
                predictor = PlusPredictor(output / PLUS)
            else:
                if algorithm == G2S_ALGORITHM:
                    features, view = transform(context, meta)
                    company_count = len(features)
                    tabular_context = {
                        "features": features,
                        "labels": context["labels"][:company_count],
                        "splits": context["splits"][:company_count],
                    }
                    selected = train_boosted_trees(
                        tabular_context,
                        weights,
                        epochs,
                        meta["seed"],
                        metric,
                    )
                    np.save(output / FEATURES_FILE, features, allow_pickle=False)
                    del tabular_context, features
                else:
                    selected = train_baseline(algorithm, prepared, weights, epochs, metric)
                predictor = BaselinePredictor(output, context, meta, index, algorithm)
            probabilities = by_id(predictor, valid_ids)
            if not np.isfinite(probabilities).all():
                raise ValueError("Non-finite validation predictions")
            member = {
                "status": "completed",
                "selectedEpoch": selected,
                "validationAp": float(average_precision_score(y, probabilities)),
                "threshold": best_threshold(y, probabilities),
                **({"featureView": view} if view is not None else {}),
            }
            np.save(output / f"{algorithm}-valid.npy", probabilities)
            del predictor
        except (ValueError, RuntimeError, OSError) as error:
            weights.unlink(missing_ok=True)
            (output / f"{algorithm}-valid.npy").unlink(missing_ok=True)
            if algorithm == PLUS:
                shutil.rmtree(output / PLUS, ignore_errors=True)
            if algorithm == G2S_ALGORITHM:
                (output / FEATURES_FILE).unlink(missing_ok=True)
            member = {"status": "failed", "error": str(error)[:600]}
        members.append({"algorithm": algorithm, "durationSeconds": monotonic() - started, **member})
    if not any(member["status"] == "completed" for member in members):
        raise ValueError(
            "All comparison members failed: "
            + "; ".join(f"{row['algorithm']}: {row['error']}" for row in members)
        )
    members.sort(key=lambda row: (-row.get("validationAp", -1), row["algorithm"]))
    recommended = [row["algorithm"] for row in members[:3] if row["status"] == "completed"]
    counts = meta["splitCounts"]
    meta.update(
        {
            "algorithm": "Majority vote",
            "runnerId": "riskgnn",
            "epochs": epochs,
            "members": members,
            "recommended": recommended,
            "codeVersion": code_version(),
            "configuration": configuration,
            "actualCounts": {
                "targets": meta["targetCount"],
                "train": counts["train"],
                "validation": counts["val"],
                "test": counts["test"],
            },
        }
    )
    write_json(output / "metadata.json", meta)
    seal(output, kind=FORMAT, metadata={"sourceSha256": meta["sourceSha256"]})
    return meta


def classification_metrics(labels, predictions):
    from riskgnn.workbench.training import metrics

    scores = metrics(labels, np.asarray(predictions, dtype=float))
    tn, fp = scores["confusionMatrix"][0]
    return {k: scores[k] for k in ("count", "precision", "recall", "f1", "confusionMatrix")} | {
        "falsePositiveRate": fp / (tn + fp) if tn + fp else None,
    }


def evaluate_comparison(directory, output):
    model = Comparison(directory)
    valid_ids, valid_y = model.split("val")
    test_ids, y = model.split("test")
    votes, rows, predictions = {}, [], {}
    splits = {
        "validation": {"ids": valid_ids, "labels": valid_y.tolist()},
        "test": {"ids": test_ids, "labels": y.tolist()},
    }
    for member in model.meta["members"]:
        algorithm = member["algorithm"]
        if member["status"] != "completed":
            rows.append(member)
            continue
        score = by_id(model.member(algorithm), test_ids)
        votes[algorithm] = score >= member["threshold"]
        if not np.isfinite(score).all():
            raise ValueError(f"Non-finite test predictions for {algorithm}")
        predictions[algorithm] = {
            "validation": np.load(
                directory / f"{algorithm}-valid.npy",
                allow_pickle=False,
            ).tolist(),
            "test": score.tolist(),
        }
        rows.append({**member, "test": classification_metrics(y, votes[algorithm])})
    options = [
        {
            "members": list(names),
            "test": classification_metrics(
                y,
                np.stack([votes[n] for n in names]).sum(axis=0) >= 2,
            ),
        }
        for names in combinations(votes, 3)
    ]
    report = {
        "split": "test",
        "algorithm": "Majority vote",
        "independentReload": True,
        "sourceSha256": model.meta["sourceSha256"],
        "selectionMetric": "validation_ap",
        "members": rows,
        "recommended": model.meta["recommended"],
        "votingOptions": options,
        "metrics": options[0]["test"] if options else {},
    }
    write_json(output / "metrics.json", report)
    write_json(output / "predictions.json", {"splits": splits, "scores": predictions})
    return report
