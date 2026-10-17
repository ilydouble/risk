"""Financial history must retain disclosure time, source versions and comparison units."""

import sys
from decimal import Decimal
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from test_uk_financials import document
from uk_financials.facts import parse_document  # noqa: E402
from uk_financials.trends import choose_history, trend_features  # noqa: E402


def period(end, facts, report="base", available="2024-02-29"):
    return {
        "history_id": report + end,
        "company_id": "00012345",
        "report_id": report,
        "report_end": "2023-12-31",
        "end": end,
        "available": available,
        "currency": "GBP",
        "facts": facts,
    }


def test_comparatives_are_separate_and_do_not_change_baseline():
    raw = document("""<ix:nonFraction name="core:CurrentAssets" contextRef="current"
      unitRef="GBP">100</ix:nonFraction>
      <ix:nonFraction name="core:CurrentAssets" contextRef="old"
      unitRef="GBP">80</ix:nonFraction>""")
    single = parse_document(raw, "00012345", "2023-12-31")
    periods = parse_document(raw, "00012345", "2023-12-31", include_comparatives=True)
    assert periods["2023-12-31"] == single
    assert periods["2022-12-31"]["facts"]["current_assets"]["value"] == "8E+1"
    assert "2023-12-31" not in parse_document(
        raw, "00012345", "2022-12-31", include_comparatives=True
    )


def test_period_versions_use_baseline_and_reject_future_disclosures():
    baseline = period("2023-12-31", {"cash": ("100", "GBP", None)})
    own = period("2022-12-31", {"cash": ("80", "GBP", None)})
    alternative = period("2022-12-31", {"cash": ("70", "GBP", None)}, "other", "2023-01-31")
    future = period("2021-12-31", {"cash": ("60", "GBP", None)}, "future", "2024-03-31")
    selected = choose_history(baseline, [alternative, own, future])
    assert [row["report_id"] for row in selected] == ["base", "base"]
    with pytest.raises(ValueError, match="another company"):
        choose_history(baseline, [{**own, "company_id": "00054321"}])


@pytest.mark.parametrize(
    "old,unit,gap,status,delta,relative",
    [
        ("80", "GBP", "2022-12-31", "comparable", "2E+1", "0.25"),
        ("0", "GBP", "2022-12-31", "comparable", "1E+2", ""),
        ("-50", "GBP", "2022-12-31", "comparable", "1.5E+2", ""),
        ("80", "EUR", "2022-12-31", "unit_mismatch", "", ""),
        ("80", "GBP", "2021-12-31", "nonannual_period_end_gap", "", ""),
    ],
)
def test_signed_changes_zero_bases_units_and_annual_spacing(
    old, unit, gap, status, delta, relative
):
    result = trend_features(
        [
            period("2023-12-31", {"equity": ("100", "GBP", None)}),
            period(gap, {"equity": (old, unit, None)}),
        ]
    )
    assert result["equity_previous"] == old
    assert result["equity_delta"] == delta and result["equity_relative_change"] == relative
    assert result["equity_trend_status"] == status
    assert result["equity_previous_missing"] is False


def test_interim_flow_is_not_treated_as_annual_growth():
    result = trend_features(
        [
            period("2023-12-31", {"revenue": ("100", "GBP", "2023-01-01")}),
            period("2022-12-31", {"revenue": ("80", "GBP", "2022-12-01")}),
        ]
    )
    assert result["revenue_previous"] == "80"
    assert result["revenue_delta_missing"] is True
    assert result["revenue_trend_status"] == "nonannual_flow_duration"


def test_metric_specific_comparisons_and_three_period_slope_keep_dates():
    rows = [
        period("2023-12-31", {"cash": ("100", "GBP", None)}),
        period("2023-01-01", {"equity": ("5", "GBP", None)}),
        period("2022-12-31", {"cash": ("80", "GBP", None)}),
        period("2021-12-31", {"cash": ("60", "GBP", None)}),
    ]
    result = trend_features(rows)
    assert result["cash_previous_period_end"] == "2022-12-31"
    assert result["cash_delta"] == "2E+1"
    assert Decimal(result["cash_three_period_slope_per_year"]) > 0
    assert result["cash_slope_period_ends"] == "2023-12-31|2022-12-31|2021-12-31"


def test_ratios_require_positive_denominator_and_keep_zero_numerator():
    rows = [
        period(
            "2023-12-31", {"cash": ("0", "GBP", None), "current_liabilities": ("10", "GBP", None)}
        ),
        period(
            "2022-12-31", {"cash": ("5", "GBP", None), "current_liabilities": ("0", "GBP", None)}
        ),
    ]
    result = trend_features(rows)
    assert result["cash_ratio"] == "0" and result["cash_ratio_missing"] is False
    assert result["cash_ratio_previous_missing"] is True
