from typing import Any

WARNING_CODES = {
    "name suggests ID or post-outcome data": "SUSPICIOUS_FEATURE_NAME",
    "near-perfect training AUC": "NEAR_PERFECT_TRAINING_SIGNAL",
}


def normalize(raw: dict[str, Any], *, total_rows: int, scope: str = "full") -> dict[str, Any]:
    quality = raw["quality"]
    signals = {item["name"]: item for item in raw.get("signals", [])}
    features = []
    for item in quality["columns"]:
        signal = signals.get(item["name"], {})
        features.append(
            {
                **{
                    k: item[k]
                    for k in (
                        "name",
                        "kind",
                        "missingCount",
                        "missingRate",
                        "uniqueCount",
                        "constant",
                    )
                },
                "iv": signal.get("iv"),
                "mutualInformation": signal.get("mutualInformation"),
                "univariateAuc": signal.get("univariateAuc"),
            }
        )
    return {
        "version": 1,
        "scope": scope,
        "totalRows": total_rows,
        "analyzedRows": quality["rowCount"],
        "duplicateSampleIds": quality.get("duplicateSampleIds", 0),
        "features": features,
        "splits": [
            {"name": name, **{k: item[k] for k in ("rows", "positives", "positiveRate")}}
            for name, item in raw["splits"].items()
        ],
        "drift": [
            {"split": split, **item}
            for split, items in raw.get("drift", {}).items()
            for item in items
        ],
        "correlations": raw.get("correlations", []),
        "warnings": [
            {
                "feature": item["feature"],
                "code": WARNING_CODES.get(item["reason"], "REVIEW_FEATURE"),
            }
            for item in raw.get("leakageWarnings", [])
        ],
        "graph": raw.get("graph", {}),
    }
