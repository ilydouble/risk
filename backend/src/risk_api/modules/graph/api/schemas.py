from typing import Any, Literal

from pydantic import BaseModel, Field

from risk_api.modules.company.api.schemas import RiskLevel


class GraphNode(BaseModel):
    id: str
    label: str
    type: Literal[
        "company",
        "owner",
        "subsidiary",
        "supplier",
        "guarantor",
        "client",
        "counterparty",
        "person",
        "bank",
        "fund",
    ]
    riskLevel: RiskLevel
    hop: int
    relation: str
    exposure: str
    industry: str | None = None
    country: str | None = None
    companyId: str | None = None
    note: str | None = None


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    type: Literal["equity", "control", "guarantee", "supply", "trade", "loan"]
    label: str
    riskFlow: bool
    strength: float


class GraphData(BaseModel):
    rootId: str
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class RequestGetGraph(BaseModel):
    companyId: str
    lang: Literal["zh", "en"] = "zh"
    depth: int = Field(default=3, ge=1, le=3)


class ResponseGetGraph(BaseModel):
    graph: GraphData
    demo: Literal[True] = True


class RequestGetDatasetGraph(BaseModel):
    datasetId: str = Field(min_length=1, max_length=64)
    companyId: str = Field(min_length=1, max_length=512)
    depth: int = Field(default=1, ge=1, le=3)
    lang: Literal["zh", "en"] = "zh"


class DatasetGraphNode(BaseModel):
    id: str
    entityId: str | None
    kind: Literal["company", "person", "hyperedge", "event"]
    label: str
    recordSequence: int | None
    data: dict[str, Any]


class DatasetGraphEdge(BaseModel):
    id: str
    source: str
    target: str
    kind: Literal["edge", "hyperedge", "event"]
    label: str
    directed: bool
    recordSequence: int | None
    data: dict[str, Any]


class ResponseGetDatasetGraph(BaseModel):
    datasetId: str
    datasetName: str
    snapshot: str
    companyId: str
    depth: int
    demo: bool
    rootId: str
    nodes: list[DatasetGraphNode]
    edges: list[DatasetGraphEdge]
    truncated: bool
    truncationReasons: list[str]
    omittedMembers: int
    limits: dict[str, int]
