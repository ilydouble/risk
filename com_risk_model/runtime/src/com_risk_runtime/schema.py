"""Validated interchange format. Raw MSGraphFin parsing awaits its data dictionary."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Node(Record):
    id: str = Field(min_length=1)
    kind: Literal["company", "person"] = "company"
    community: str = "unknown"
    features: list[float | None]
    label: Literal[0, 1] | None = None
    split: Literal["train", "valid", "test"] | None = None


class Edge(Record):
    source: str
    target: str
    relation: str
    weight: float = Field(default=1.0, gt=0)


class Hyperedge(Record):
    kind: str
    members: list[str] = Field(min_length=1)


class Event(Record):
    company: str
    cause: int = Field(ge=0, lt=11)
    court: int = Field(ge=0, lt=4)
    result: int = Field(ge=0, lt=4)
    age_months: float = Field(ge=0)


class Dataset(Record):
    schema_version: Literal[1] = 1
    name: str
    synthetic: bool = False
    # Only static transductive evaluation is supported in v1. No future-PD claim.
    evaluation: Literal["static_transductive", "isolated_snapshots"] = "static_transductive"
    target_description: str = Field(min_length=1)
    feature_names: list[str] = Field(min_length=1)
    relation_names: list[str] = Field(min_length=1)
    hyperedge_types: list[str] = Field(min_length=1)
    nodes: list[Node] = Field(min_length=1)
    edges: list[Edge] = Field(default_factory=list)
    hyperedges: list[Hyperedge] = Field(default_factory=list)
    events: list[Event] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_graph(self):
        for names in (self.feature_names, self.relation_names, self.hyperedge_types):
            if len(names) != len(set(names)) or any(not n for n in names):
                raise ValueError("schema names must be unique and nonempty")
        lookup = {n.id: n for n in self.nodes}
        if len(lookup) != len(self.nodes):
            raise ValueError("duplicate node IDs")
        for n in self.nodes:
            if len(n.features) != len(self.feature_names):
                raise ValueError(f"feature width mismatch: {n.id}")
            if n.split and (n.label is None or n.kind != "company"):
                raise ValueError("split nodes must be labelled companies")
            if n.kind == "person" and n.label is not None:
                raise ValueError("person labels are not supported")
        seen = set()
        for e in self.edges:
            if e.source not in lookup or e.target not in lookup:
                raise ValueError("edge references unknown node")
            if e.relation not in self.relation_names:
                raise ValueError("unknown relation")
            key = (e.source, e.target, e.relation)
            if key in seen:
                raise ValueError("duplicate directed edge; aggregate weights first")
            seen.add(key)
        for h in self.hyperedges:
            if h.kind not in self.hyperedge_types:
                raise ValueError("unknown hyperedge type")
            if len(h.members) != len(set(h.members)):
                raise ValueError("duplicate hyperedge member")
            if any(i not in lookup or lookup[i].kind != "company" for i in h.members):
                raise ValueError("hyperedges must reference known companies")
        for event in self.events:
            if event.company not in lookup or lookup[event.company].kind != "company":
                raise ValueError("event must reference known company")
        return self

    @classmethod
    def read(cls, path: str | Path):
        return cls.model_validate_json(Path(path).read_text())

    def write(self, path: str | Path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.model_dump_json(indent=2), encoding="utf-8")
