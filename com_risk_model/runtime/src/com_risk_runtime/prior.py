"""Apply persisted Beta-Binomial priors, including original training OOF values."""

import torch


def value(model, group):
    s, n = model["groups"].get(group, [0, 0])
    return (s + model["alpha"]) / (n + model["alpha"] + model["beta"])


def add_prior(graph, data, model, training=False):
    # Persisted OOF values for all original training IDs, even if input labels/splits are removed.
    vals = [model["oof"].get(n.id, value(model, n.community)) for n in data.nodes]
    graph["prior"] = torch.tensor(vals, dtype=torch.float32).unsqueeze(1)
    return graph
