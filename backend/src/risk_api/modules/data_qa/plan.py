"""Bounded query language: the model supplies data, never executable SQL."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Scalar = str | float | int | bool | None


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class QueryFilter(StrictModel):
    field: str = Field(max_length=64)
    operator: Literal["eq", "ne", "gt", "gte", "lt", "lte", "contains", "in", "is_null"]
    value: Scalar | list[Scalar] = None


class QueryMetric(StrictModel):
    function: Literal["count", "count_distinct", "sum", "avg", "min", "max"]
    field: str | None = Field(default=None, max_length=64)
    alias: str = Field(pattern=r"^[a-z][a-z0-9_]{0,31}$")


class QueryOrder(StrictModel):
    field: str = Field(max_length=64)
    direction: Literal["asc", "desc"] = "desc"


class QueryPlan(StrictModel):
    table: Literal["datasets", "runs", "models", "imports", "records", "enterprises", "predictions"]
    columns: list[str] = Field(default_factory=list, max_length=12)
    filters: list[QueryFilter] = Field(default_factory=list, max_length=12)
    groupBy: list[str] = Field(default_factory=list, max_length=3)
    metrics: list[QueryMetric] = Field(default_factory=list, max_length=6)
    orderBy: list[QueryOrder] = Field(default_factory=list, max_length=3)
    limit: int = Field(default=50, ge=1, le=100)

    @model_validator(mode="after")
    def shape(self):
        if bool(self.columns) == bool(self.metrics):
            raise ValueError("Choose detail columns OR aggregate metrics")
        if self.groupBy and not self.metrics:
            raise ValueError("Grouping requires metrics")
        names = self.columns or [*self.groupBy, *[m.alias for m in self.metrics]]
        if len(set(names)) != len(names):
            raise ValueError("Duplicate output fields")
        return self
