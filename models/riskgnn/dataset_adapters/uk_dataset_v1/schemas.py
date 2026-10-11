from riskgnn.dataset_adapters.snapshot_schema import Snapshot

FEATURES = [
    "age_months",
    "n_charges",
    "n_charges_outstanding",
    "addr_company_count",
    "n_net_dir",
    "max_span",
    "sum_span",
]
RELATIONS = ["SAME_ADDRESS", "EQUITY", "PREVNAME", "SAME_NAME"]
HYPEREDGES = ["sic_section", "postcode_area", "director_group"]


def check(snapshots: dict[str, Snapshot]) -> None:
    for snapshot in snapshots.values():
        if (
            snapshot.feature_names != FEATURES
            or snapshot.relation_names != RELATIONS
            or snapshot.hyperedge_types != HYPEREDGES
        ):
            raise ValueError("Unsupported UK seven-feature, three-hyperedge schema")
        if snapshot.events or any(n.kind != "company" for n in snapshot.nodes):
            raise ValueError("UK v1 contains companies only and no events")
        if any(v is None or v < 0 for n in snapshot.nodes for v in n.features):
            raise ValueError("UK v1 requires nonnegative observed features")
        if any(not 0.3 <= e.weight <= 1 for e in snapshot.edges):
            raise ValueError("Invalid UK evidence weight")
        if any(
            e.existence_confidence is not None or e.strength is not None for e in snapshot.edges
        ):
            raise ValueError("UK v1 weight is not a calibrated probability or business strength")
