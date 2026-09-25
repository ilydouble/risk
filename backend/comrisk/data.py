"""Validated interchange format. Raw MSGraphFin parsing awaits its data dictionary."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

import numpy as np
import torch
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
        for e in self.events:
            if e.company not in lookup or lookup[e.company].kind != "company":
                raise ValueError("event must reference known company")
        return self

    @classmethod
    def read(cls, path: str | Path):
        return cls.model_validate_json(Path(path).read_text())

    def write(self, path: str | Path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.model_dump_json(indent=2), encoding="utf-8")


def fit_preprocessor(data: Dataset) -> dict:
    # No validation/test features participate in fitting imputation or scaling.
    raw = np.array([n.features for n in data.nodes if n.split == "train"], dtype=float)
    if not len(raw):
        raise ValueError("no training rows")
    median = np.array([np.median(col[np.isfinite(col)]) if np.isfinite(col).any() else 0
                       for col in raw.T])
    clean = np.where(np.isnan(raw), median, raw)
    std = clean.std(0)
    return {"median": median.tolist(), "mean": clean.mean(0).tolist(),
            "std": np.where(std < 1e-8, 1, std).tolist()}


def tensorize(data: Dataset, preprocessor: dict) -> dict:
    index = {n.id: i for i, n in enumerate(data.nodes)}
    raw = np.array([n.features for n in data.nodes], dtype=float)
    clean = np.where(np.isnan(raw), preprocessor["median"], raw)
    values = np.clip((clean - preprocessor["mean"]) / preprocessor["std"], -10, 10)
    # Missingness remains observable after median imputation.
    x = torch.tensor(np.concatenate([values, np.isnan(raw)], axis=1), dtype=torch.float32)
    relations = []
    for name in data.relation_names:
        edges = [e for e in data.edges if e.relation == name]
        relations.append((torch.tensor([index[e.source] for e in edges], dtype=torch.long),
                          torch.tensor([index[e.target] for e in edges], dtype=torch.long),
                          torch.tensor([e.weight for e in edges], dtype=torch.float32)))
    incidence = []
    for name in data.hyperedge_types:
        groups = [h for h in data.hyperedges if h.kind == name]
        pairs = [(index[n], j) for j, h in enumerate(groups) for n in h.members]
        incidence.append((torch.tensor([p[0] for p in pairs], dtype=torch.long),
                          torch.tensor([p[1] for p in pairs], dtype=torch.long), len(groups)))
    events = torch.tensor([[index[e.company], e.cause, e.court, e.result, e.age_months]
                           for e in data.events], dtype=torch.float32).reshape(-1, 5)
    return {"x": x, "kinds": torch.tensor([n.kind == "person" for n in data.nodes], dtype=torch.long),
            "relations": relations, "incidence": incidence, "events": events,
            "y": torch.tensor([n.label if n.label is not None else -1 for n in data.nodes], dtype=torch.float32),
            "masks": {s: torch.tensor([n.split == s for n in data.nodes]) for s in ("train", "valid", "test")}}


def dump_json(path: str | Path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
