DEFAULT_MODEL = "riskgnn"


def capabilities() -> list[dict]:
    return [
        {
            "id": DEFAULT_MODEL,
            "name": "RiskGNN",
            "datasetFormats": ["sg-comrisk-v1"],
            "trainable": True,
            "reason": None,
        }
    ]
