"""Compile only approved expressions and bind scope before any aggregation."""

from dataclasses import dataclass
from datetime import datetime
from operator import eq, ge, gt, le, lt, ne

from sqlalchemy import Select, func, select

from risk_api.modules.data_qa.catalog import CATALOG, sources
from risk_api.modules.data_qa.plan import QueryPlan


@dataclass
class CompiledQuery:
    statement: Select
    columns: list[dict]


def compile_query(owner: str, dataset: str | None, model: str | None, plan: QueryPlan):
    base = sources(owner)[plan.table].subquery("owned_data")
    fields = CATALOG[plan.table][2]

    def field(name):
        if name not in fields:
            raise ValueError(f"不支持字段：{name}")
        return base.c[name]

    conditions = []
    if dataset:
        conditions.append(base.c.dataset_id == dataset)
    if model and plan.table == "predictions":
        conditions.append(base.c.model_id == model)
    for item in plan.filters:
        column = field(item.field)
        kind = fields[item.field][1]
        value = item.value
        if kind == "json":
            raise ValueError("JSON属性暂仅支持展示，不能直接筛选或聚合")

        def typed(value, kind=kind):
            if value is None:
                return None
            if kind == "number":
                if type(value) not in {int, float}:
                    raise ValueError("数值字段需要数字")
                return value
            if not isinstance(value, str) or len(value) > 512:
                raise ValueError("文本或日期筛选值不合法")
            if kind == "datetime":
                result = datetime.fromisoformat(value.replace("Z", "+00:00"))
                if result.tzinfo is None:
                    raise ValueError("时间必须包含时区")
                return result
            return value

        if item.operator == "in":
            if not isinstance(value, list) or not 1 <= len(value) <= 50:
                raise ValueError("in需要1–50个值")
            conditions.append(column.in_([typed(v) for v in value]))
        elif item.operator == "is_null":
            if type(value) is not bool:
                raise ValueError("is_null需要布尔值")
            conditions.append(column.is_(None) if value else column.is_not(None))
        elif item.operator == "contains":
            if kind != "text" or not isinstance(value, str) or not value:
                raise ValueError("contains仅用于非空文本")
            conditions.append(column.icontains(typed(value), autoescape=True))
        else:
            if isinstance(value, list):
                raise ValueError("比较值不能是列表")
            value = typed(value)
            if value is None and item.operator not in {"eq", "ne"}:
                raise ValueError("空值仅能用于等于或不等于")
            compare = {"eq": eq, "ne": ne, "gt": gt, "gte": ge, "lt": lt, "lte": le}
            conditions.append(compare[item.operator](column, value))

    columns = []
    expressions = {}
    for name in plan.columns or plan.groupBy:
        if fields.get(name, (None, None))[1] == "json" and plan.groupBy:
            raise ValueError("不能按JSON分组")
        expressions[name] = field(name)
        columns.append({"id": name, "name": fields[name][0], "type": fields[name][1]})
    labels = {
        "count": "数量",
        "count_distinct": "去重数量",
        "sum": "总和",
        "avg": "平均值",
        "min": "最小值",
        "max": "最大值",
    }
    for metric in plan.metrics:
        if metric.alias in fields or metric.alias in expressions:
            raise ValueError("指标别名不能与现有字段重名")
        column = field(metric.field) if metric.field else None
        if metric.function != "count" and column is None:
            raise ValueError("该指标必须指定字段")
        if metric.field and fields[metric.field][1] == "json":
            raise ValueError("不能聚合JSON属性")
        if metric.function in {"sum", "avg", "min", "max"}:
            if not metric.field or fields[metric.field][1] != "number":
                raise ValueError("该聚合需要数值字段")
        if metric.function == "count_distinct":
            if column is None:
                raise ValueError("去重计数必须指定字段")
            expression = func.count(column.distinct())
        elif column is not None:
            expression = getattr(func, metric.function)(column)
        else:
            expression = func.count()
        expressions[metric.alias] = expression.label(metric.alias)
        label = labels[metric.function] + (f" · {fields[metric.field][0]}" if metric.field else "")
        columns.append({"id": metric.alias, "name": label, "type": "number"})
    statement = select(*expressions.values()).select_from(base).where(*conditions)
    if plan.groupBy:
        statement = statement.group_by(*[field(name) for name in plan.groupBy])
    for order in plan.orderBy:
        if order.field not in expressions:
            raise ValueError("排序字段必须出现在结果中")
        value = expressions[order.field]
        statement = statement.order_by(
            (value.desc() if order.direction == "desc" else value.asc()).nulls_last()
        )
    if not plan.orderBy:
        if plan.metrics and plan.groupBy:
            statement = statement.order_by(
                *[field(name).asc().nulls_last() for name in plan.groupBy]
            )
        elif not plan.metrics:
            keys = {
                "datasets": ["dataset_id"],
                "runs": ["run_id"],
                "models": ["model_id"],
                "imports": ["dataset_id"],
                "records": ["dataset_id", "sequence"],
                "enterprises": ["dataset_id", "sequence"],
                "predictions": ["model_id", "company_id"],
            }
            statement = statement.order_by(*[field(name) for name in keys[plan.table]])
    return CompiledQuery(statement.limit(plan.limit + 1), columns)
