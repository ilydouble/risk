from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class GraphSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nodeCount: int = Field(ge=0)
    edgeCount: int = Field(ge=0)


class CompanyGraphReference(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["company_graph"] = "company_graph"
    companyId: str = Field(min_length=1, max_length=64)
    depth: int = Field(ge=1, le=3)
    lang: Literal["zh", "en"]
    title: str
    summary: GraphSummary
    demo: Literal[True] = True
