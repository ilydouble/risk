"""Compare disclosed periods with explicit units, annual spacing and duration checks."""

from datetime import date
from decimal import Decimal

from uk_financials.facts import ALIASES

FLOWS = {
    "revenue",
    "profit_loss",
    "operating_profit_loss",
    "profit_before_tax",
    "average_employees",
}
ANNUAL_MIN_DAYS = 330
ANNUAL_MAX_DAYS = 400


def comparison_status(metric, current, previous, current_end, previous_end):
    if current is None:
        return "missing_current_metric"
    if previous is None:
        return "missing_previous_metric"
    if current[1] != previous[1]:
        return "unit_mismatch"
    gap = (date.fromisoformat(current_end) - date.fromisoformat(previous_end)).days
    if not ANNUAL_MIN_DAYS <= gap <= ANNUAL_MAX_DAYS:
        return "nonannual_period_end_gap"
    if metric in FLOWS:
        try:
            starts = [date.fromisoformat(fact[2]) for fact in [current, previous]]
        except (TypeError, ValueError):
            return "missing_or_invalid_duration"
        ends = [date.fromisoformat(end) for end in [current_end, previous_end]]
        lengths = [(end - start).days + 1 for end, start in zip(ends, starts, strict=True)]
        if not all(ANNUAL_MIN_DAYS <= length <= ANNUAL_MAX_DAYS for length in lengths):
            return "nonannual_flow_duration"
        if abs(lengths[0] - lengths[1]) > 31:
            return "flow_duration_difference_exceeds_31_days"
        if ends[1] >= starts[0]:
            return "overlapping_flow_periods"
    return "comparable"


def choose_history(baseline, candidates):
    selected = {baseline["end"]: baseline}

    def priority(row):
        return (
            row["report_id"] == baseline["report_id"],
            row["available"],
            row["report_end"],
            row["report_id"],
        )

    for candidate in candidates:
        if candidate["company_id"] != baseline["company_id"]:
            raise ValueError("History contains another company")
        if (
            candidate["available"] > baseline["available"]
            or candidate["end"] >= baseline["end"]
            or candidate["report_end"] > baseline["end"]
            or not candidate["facts"]
        ):
            continue
        previous = selected.get(candidate["end"])
        if previous is None or priority(candidate) > priority(previous):
            selected[candidate["end"]] = candidate
    return [selected[end] for end in sorted(selected, reverse=True)]


def ratio(row, numerator, denominator):
    upper, lower = row["facts"].get(numerator), row["facts"].get(denominator)
    if upper is None or lower is None or upper[1] != lower[1] or Decimal(lower[0]) <= 0:
        return ""
    return str((Decimal(upper[0]) / Decimal(lower[0])).normalize())


def trend_features(history):
    current = history[0]
    previous = history[1] if len(history) > 1 else None
    result = {
        "financial_period_count": len(history),
        "financial_comparative_period_count": len(history) - 1,
        "financial_previous_period_end": previous["end"] if previous else "",
        "financial_previous_report_id": previous["report_id"] if previous else "",
        "financial_previous_available_by_assumed": previous["available"] if previous else "",
        "financial_previous_currency": previous["currency"] if previous else "",
        "financial_previous_gap_days": (
            date.fromisoformat(current["end"]) - date.fromisoformat(previous["end"])
        ).days
        if previous
        else "",
        "financial_previous_missing": previous is None,
    }
    for metric in ALIASES:
        now = current["facts"].get(metric)
        candidates = [row for row in history[1:] if metric in row["facts"]]
        comparable = [
            row
            for row in candidates
            if comparison_status(metric, now, row["facts"][metric], current["end"], row["end"])
            == "comparable"
        ]
        prior = next(iter(comparable or candidates), None)
        before = prior["facts"][metric] if prior else None
        last = before[0] if before else ""
        delta = relative = slope = ""
        status = (
            comparison_status(metric, now, before, current["end"], prior["end"])
            if prior
            else "missing_previous_period"
        )
        if status == "comparable":
            delta = str((Decimal(now[0]) - Decimal(before[0])).normalize())
            if Decimal(before[0]) > 0:
                relative = str((Decimal(delta) / Decimal(before[0])).normalize())
        older = [
            row
            for row in history[1:]
            if prior
            and row["end"] < prior["end"]
            and comparison_status(
                metric, before, row["facts"].get(metric), prior["end"], row["end"]
            )
            == "comparable"
        ]
        if status == "comparable" and older:
            triple = [current, prior, older[0]]
            facts = [row["facts"].get(metric) for row in triple]
            if all(
                comparison_status(
                    metric, facts[i], facts[i + 1], triple[i]["end"], triple[i + 1]["end"]
                )
                == "comparable"
                for i in range(2)
            ):
                dates = [
                    Decimal(
                        (date.fromisoformat(row["end"]) - date.fromisoformat(triple[2]["end"])).days
                    )
                    for row in triple
                ]
                values = [Decimal(fact[0]) for fact in facts]
                x_mean, y_mean = sum(dates) / 3, sum(values) / 3
                numerator = sum(
                    (x - x_mean) * (y - y_mean) for x, y in zip(dates, values, strict=True)
                )
                denominator = sum((x - x_mean) ** 2 for x in dates)
                slope = str((numerator / denominator * Decimal("365.25")).normalize())
        for suffix, value in [
            ("previous", last),
            ("delta", delta),
            ("relative_change", relative),
            ("three_period_slope_per_year", slope),
        ]:
            result[f"{metric}_{suffix}"] = value
            result[f"{metric}_{suffix}_missing"] = value == ""
        result[f"{metric}_trend_status"] = status
        result[f"{metric}_relative_change_status"] = (
            status if status != "comparable" else "defined" if relative else "nonpositive_previous"
        )
        result[f"{metric}_previous_period_end"] = prior["end"] if prior else ""
        result[f"{metric}_previous_unit"] = before[1] if before else ""
        result[f"{metric}_slope_period_ends"] = (
            "|".join(row["end"] for row in triple) if slope else ""
        )
    for name, numerator in [("current_ratio", "current_assets"), ("cash_ratio", "cash")]:
        now = ratio(current, numerator, "current_liabilities")
        candidates = [row for row in history[1:] if ratio(row, numerator, "current_liabilities")]
        annual = [
            row
            for row in candidates
            if ANNUAL_MIN_DAYS
            <= (date.fromisoformat(current["end"]) - date.fromisoformat(row["end"])).days
            <= ANNUAL_MAX_DAYS
        ]
        prior = next(iter(annual or candidates), None)
        before = ratio(prior, numerator, "current_liabilities") if prior else ""
        valid_gap = prior is not None and prior in annual
        delta = (
            str((Decimal(now) - Decimal(before)).normalize())
            if now and before and valid_gap
            else ""
        )
        for suffix, value in [("", now), ("_previous", before), ("_delta", delta)]:
            result[name + suffix] = value
            result[name + suffix + "_missing"] = value == ""
        result[name + "_previous_period_end"] = prior["end"] if prior else ""
    return result
