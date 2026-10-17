"""Deterministic field-level quarantine, keeping every source fact for review."""

from decimal import Decimal

POLICY_VERSION = "uk-financial-quality-v1"


def validate_facts(facts, company_id):
    accepted, issues = {}, []
    for metric, fact in facts.items():
        value = Decimal(fact["value"])
        reasons, warnings = [], []
        if not value.is_finite():
            reasons.append("nonfinite")
        elif metric == "average_employees":
            if value < 0:
                reasons.append("negative_employee_count")
            if company_id.isdigit() and value == int(company_id):
                reasons.append("employee_count_equals_company_number")
            if value > 100000:
                reasons.append("employee_count_above_review_threshold")
            if int(fact.get("scale", "0")) != 0:
                reasons.append("employee_count_nonzero_scale_requires_review")
        else:
            if fact["unit"] in {"GBP", "EUR", "USD"} and abs(value) >= Decimal("1e11"):
                reasons.append("amount_above_review_threshold")
            if value < 0 and metric in {"fixed_assets", "current_assets", "stocks", "debtors"}:
                warnings.append("negative_asset_balance_requires_review")
        for reason in reasons + warnings:
            issues.append(
                {
                    "metric": metric,
                    "reason": reason,
                    "action": "quarantine" if reason in reasons else "retain_with_warning",
                    "source_fact": fact,
                }
            )
        if not reasons:
            accepted[metric] = fact
    # Rounded disclosures and legitimate negative balances need review, not an
    # automatic arithmetic rewrite or deletion of all facts from the report.
    required = {"current_assets", "current_liabilities", "net_current_assets"}
    if required <= accepted.keys():
        selected = [accepted[key] for key in sorted(required)]
        if len({fact["unit"] for fact in selected}) == 1:
            amounts = {key: Decimal(accepted[key]["value"]) for key in required}
            residual = (
                amounts["current_assets"]
                - amounts["current_liabilities"]
                - amounts["net_current_assets"]
            )
            tolerance = max(Decimal(3), max(map(abs, amounts.values())) * Decimal("0.01"))
            if abs(residual) > tolerance:
                issues.append(
                    {
                        "metric": "current_assets|current_liabilities|net_current_assets",
                        "reason": "current_balance_identity_mismatch",
                        "action": "retain_with_warning",
                        "residual": str(residual),
                        "tolerance": str(tolerance),
                        "source_facts": selected,
                    }
                )
    return accepted, issues
