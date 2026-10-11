from riskgnn.dataset_adapters.snapshot_schema import Snapshot

FEATURES = ["log_registered_capital", "log_paid_capital", "age_months"]
RELATIONS = [
    "supervised",
    "supervise",
    "executed",
    "execute",
    "stakeholderd",
    "stakeholder",
    "invest_CC",
    "invested_CC",
    "invest_CP",
    "invested_CP",
    "branch",
    "branched",
]
HYPEREDGES = ["industry", "area", "qualify"]


def check(snapshots: dict[str, Snapshot]) -> None:
    for snapshot in snapshots.values():
        if (
            snapshot.feature_names != FEATURES
            or snapshot.relation_names != RELATIONS
            or snapshot.hyperedge_types != HYPEREDGES
        ):
            raise ValueError("Unsupported SMEsD V5 schema")
        if any(
            n.kind == "person" and any(v is not None for v in n.features) for n in snapshot.nodes
        ):
            raise ValueError("SMEsD person nodes must not contain company attributes")
        if any(e.strength is None or e.existence_confidence != 1 for e in snapshot.edges):
            raise ValueError("SMEsD V5 requires separate strength and unit confidence")
        for group in snapshot.hyperedges:
            expected = "relational" if group.kind == "qualify" else "attribute"
            if group.semantic_kind != expected:
                raise ValueError("SMEsD hyperedge semantics do not match V5")
