"""Beta-Binomial group prior; OOF training values enter the head, never messages."""

import numpy as np
from com_risk_runtime.prior import value
from sklearn.model_selection import StratifiedKFold


def fit_prior(data, seed=42):
    nodes = [n for n in data.nodes if n.split == "train"]
    y = np.array([n.label for n in nodes])
    groups = np.array([n.community for n in nodes])

    def aggregate(indices):
        target = y[indices]
        mu = float(target.mean())
        stats: dict[str, list[int]] = {}
        for i in indices:
            s, n = stats.get(groups[i], [0, 0])
            stats[groups[i]] = [s + int(y[i]), n + 1]
        rates = np.array([s / n for s, n in stats.values() if n >= 5])
        variance = float(rates.var()) if len(rates) > 1 else 0
        strength = float(np.clip(mu * (1 - mu) / max(variance, 1e-6) - 1, 2, 100))
        return {
            "alpha": max(mu * strength, 1e-3),
            "beta": max((1 - mu) * strength, 1e-3),
            "groups": stats,
        }

    full = aggregate(np.arange(len(nodes)))
    folds = min(5, int(np.bincount(y, minlength=2).min()))
    if folds < 2:
        raise ValueError("community OOF prior requires at least two examples per class")
    oof = {}
    for fit, hold in StratifiedKFold(folds, shuffle=True, random_state=seed).split(y, y):
        model = aggregate(fit)
        for i in hold:
            oof[nodes[i].id] = value(model, nodes[i].community)
    full["oof"] = oof
    full["method"] = (
        "industry Beta-Binomial, moment concentration clipped [2,100], 5-fold OOF where possible"
    )
    return full
