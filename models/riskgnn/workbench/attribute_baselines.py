"""Attribute-only baselines with graph-independent, weights-only artifacts."""

import numpy as np
import torch
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import log_loss
from torch import nn


class AttributeNetwork(nn.Module):
    def __init__(self, algorithm, context):
        super().__init__()
        self.features = torch.as_tensor(context["features"], dtype=torch.float32)
        width = self.features.shape[1]
        self.classifier = (
            nn.Linear(width, 2)
            if algorithm == "lr"
            else nn.Sequential(nn.Linear(width, 64), nn.ReLU(), nn.Linear(64, 2))
        )

    def forward(self, _snapshot, targets):
        return self.classifier(self.features[targets])


class BoostedTrees:
    def __init__(self, weights, features):
        self.weights, self.features = weights, features

    def scores(self, targets):
        features = self.features[targets]
        rows = np.arange(len(features))
        logits = np.zeros(len(features))
        for tree in self.weights["trees"]:
            left, right, column, threshold, value = (entry.numpy() for entry in tree)
            nodes = np.zeros(len(features), dtype=np.int64)
            while (branch := left[nodes] != -1).any():
                parent = nodes[branch]
                use_left = features[rows[branch], column[parent]] <= threshold[parent]
                nodes[branch] = np.where(use_left, left[parent], right[parent])
            logits += value[nodes]
        return torch.special.expit(torch.from_numpy(logits * self.weights["learning_rate"])).numpy()


def train_boosted_trees(context, output, epochs, seed, callback):
    features, labels = context["features"], context["labels"]
    train, valid = (context["splits"] == name for name in ("train", "val"))
    model = GradientBoostingClassifier(
        n_estimators=epochs,
        init="zero",
        random_state=seed,
    ).fit(features[train], labels[train])
    history = zip(
        model.staged_predict_proba(features[train]),
        model.staged_predict_proba(features[valid]),
        strict=True,
    )
    best, selected = float("inf"), 0
    for epoch, (train_scores, valid_scores) in enumerate(history, 1):
        validation = float(log_loss(labels[valid], valid_scores, labels=[0, 1]))
        if validation < best:
            best, selected = validation, epoch
        callback(
            {
                "epoch": epoch,
                "trainLoss": float(log_loss(labels[train], train_scores, labels=[0, 1])),
                "validationLoss": validation,
            }
        )
    # Store public tree arrays instead of a pickled sklearn estimator.
    trees = []
    for estimator in model.estimators_[:selected, 0]:
        tree = estimator.tree_
        trees.append(
            [
                torch.as_tensor(value.copy())
                for value in (
                    tree.children_left,
                    tree.children_right,
                    tree.feature,
                    tree.threshold,
                    tree.value[:, 0, 0],
                )
            ]
        )
    weights = {"learning_rate": model.learning_rate, "trees": trees}
    expected = next(
        value[:, 1]
        for epoch, value in enumerate(model.staged_predict_proba(features[valid]), 1)
        if epoch == selected
    )
    actual = BoostedTrees(weights, features).scores(np.flatnonzero(valid))
    if not np.allclose(expected, actual, rtol=1e-10, atol=1e-12):
        raise ValueError("Boosted-tree export does not match validation scores")
    torch.save(weights, output)
    return selected
