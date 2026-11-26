"""Derive per-company features from bound ordinary relations and hyperedges."""

import numpy as np

ALGORITHM = "g2s-gbdt"
FEATURES_FILE = "g2s-features.npy"
PERCENTILE_COLUMNS = 8


def percentiles(values, reference_values):
    varying = np.flatnonzero(np.ptp(reference_values, axis=0))[:PERCENTILE_COLUMNS]
    ranks = np.empty((len(values), len(varying)), dtype=np.float32)
    for i, column in enumerate(varying):
        reference = np.sort(reference_values[:, column])
        score = values[:, column]
        lower = np.searchsorted(reference, score, side="left")
        upper = np.searchsorted(reference, score, side="right")
        ranks[:, i] = (lower + upper) / (2 * len(reference))
    return ranks, varying


def divide(numerator, denominator):
    return np.divide(
        numerator,
        denominator,
        out=np.zeros_like(numerator, dtype=np.float32),
        where=denominator > 0,
    )


def ordinary_state(edges, ranks):
    company_count = len(ranks)
    result = []
    for relation in np.unique(edges[:, 2]):
        pairs = edges[edges[:, 2] == relation, :2]
        for source, peer in (pairs.T, pairs[:, ::-1].T):
            target = source < company_count
            same_type = target & (peer < company_count)
            own, other = source[same_type], peer[same_type]
            degree = np.bincount(source[target], minlength=company_count)
            comparable = np.bincount(own, minlength=company_count)
            result.append(np.log1p(degree, dtype=np.float32))
            result.append(np.log1p(degree - comparable, dtype=np.float32))
            for column in ranks.T:
                distance = np.abs(column[own] - column[other])
                result.append(
                    divide(
                        np.bincount(own, weights=distance, minlength=company_count),
                        comparable,
                    )
                )
    return result


def group_state(context, kinds, ranks):
    company_count = len(ranks)
    result = []
    for i in range(kinds):
        nodes = context[f"hyper_nodes_{i}"]
        group = context[f"hyper_groups_{i}"]
        if not len(nodes):
            continue
        group_size = np.bincount(group)
        peers = group_size[group] - 1
        memberships = np.bincount(nodes, minlength=company_count)
        result.append(np.log1p(memberships, dtype=np.float32))
        peer_total = np.bincount(nodes, weights=peers, minlength=company_count)
        result.append(np.log1p(divide(peer_total, memberships)))
        for column in ranks.T:
            total = np.bincount(group, weights=column[nodes])
            peer_mean = divide(total[group] - column[nodes], peers)
            distance = np.abs(column[nodes] - peer_mean)
            result.append(
                divide(
                    np.bincount(nodes, weights=distance, minlength=company_count),
                    memberships,
                )
            )
    return result


def transform(context, metadata, *, reference_values=None):
    company_count = metadata["companyCount"]
    values = context["features"][:company_count]
    if reference_values is None:
        reference_values = values[context["splits"][:company_count] == "train"]
    ranks, columns = percentiles(values, reference_values)
    edges = context["edges"]
    source, target = edges[:, 0], edges[:, 1]
    same_snapshot = context["snapshots"][source] == context["snapshots"][target]
    edges = edges[(source != target) & same_snapshot]
    state = ordinary_state(edges, ranks)
    state += group_state(context, len(metadata["hyperedgeTypes"]), ranks)
    if not state:
        raise ValueError("Graph-to-State requires ordinary edges or hypergraph memberships")
    features = np.column_stack((values, *state)).astype(np.float32, copy=False)
    return features, {
        "id": "graph-to-state-v1",
        "referenceSplit": "train",
        "percentileFeatures": [metadata["features"][int(i)] for i in columns],
        "structuralFeatureCount": len(state),
    }
