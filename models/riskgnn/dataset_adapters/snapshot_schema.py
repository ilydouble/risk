"""Structural JSON snapshot format shared by SMEsD and UK; no dataset policy."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, strict=True)


class Node(Record):
    id: str = Field(min_length=1)
    kind: Literal["company", "person"]
    name: str | None = None
    properties: dict[str, JsonValue] = Field(default_factory=dict)
    community: str
    features: list[float | None]
    label: Literal[0, 1] | None
    split: Literal["train", "valid", "test"] | None


class Edge(Record):
    source: str
    target: str
    relation: str
    weight: float = Field(gt=0)
    relation_id: str | None = None
    strength: float | None = Field(default=None, ge=0)
    existence_confidence: float | None = Field(default=None, ge=0, le=1)
    source_system: str | None = None
    evidence_count: int | None = Field(default=None, ge=0)
    observed_at: str | None = None
    valid_from: str | None = None
    valid_to: str | None = None
    is_inferred: bool | None = None
    relation_kind: str | None = None


class Hyperedge(Record):
    kind: str
    members: list[str] = Field(min_length=1)
    hyperedge_confidence: float | None = Field(default=None, ge=0, le=1)
    membership_confidence: list[float] | None = None
    source_system: str | None = None
    semantic_kind: Literal["attribute", "relational", "unknown"] | None = None
    is_inferred: bool | None = None
    recommended: bool | None = None
    recommendation_note: str | None = None


class Event(Record):
    company: str
    cause: int = Field(ge=0, lt=11)
    court: int = Field(ge=0, lt=4)
    result: int = Field(ge=0, lt=4)
    age_months: float = Field(ge=0)


class Snapshot(Record):
    schema_version: Literal[1]
    name: str
    synthetic: Literal[False]
    evaluation: Literal["isolated_snapshots"]
    target_description: str = Field(min_length=1)
    feature_names: list[str] = Field(min_length=1)
    relation_names: list[str] = Field(min_length=1)
    hyperedge_types: list[str] = Field(min_length=1)
    nodes: list[Node] = Field(min_length=1)
    edges: list[Edge]
    hyperedges: list[Hyperedge]
    events: list[Event]

    @model_validator(mode="after")
    def references(self):
        for names in (self.feature_names, self.relation_names, self.hyperedge_types):
            if len(set(names)) != len(names) or any(not name for name in names):
                raise ValueError("Duplicate or empty schema names")
        nodes = {node.id: node for node in self.nodes}
        if len(nodes) != len(self.nodes):
            raise ValueError("Duplicate node ID")
        for node in self.nodes:
            if len(node.features) != len(self.feature_names):
                raise ValueError("Feature width mismatch")
            if node.kind == "person" and (node.label is not None or node.split is not None):
                raise ValueError("Persons cannot be supervised targets")
        seen = set()
        for edge in self.edges:
            key = (edge.source, edge.target, edge.relation)
            if edge.source not in nodes or edge.target not in nodes:
                raise ValueError("Unknown edge endpoint")
            if edge.relation not in self.relation_names or key in seen:
                raise ValueError("Unknown or duplicate directed relation")
            seen.add(key)
        for group in self.hyperedges:
            if group.kind not in self.hyperedge_types or len(set(group.members)) != len(
                group.members
            ):
                raise ValueError("Unknown hyperedge kind or duplicate member")
            if any(
                member not in nodes or nodes[member].kind != "company" for member in group.members
            ):
                raise ValueError("Hyperedge references unknown company")
            if group.membership_confidence is not None and (
                len(group.membership_confidence) != len(group.members)
                or any(not 0 <= value <= 1 for value in group.membership_confidence)
            ):
                raise ValueError("Invalid membership confidence")
        if any(e.company not in nodes or nodes[e.company].kind != "company" for e in self.events):
            raise ValueError("Event references unknown company")
        return self
