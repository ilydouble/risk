from dataclasses import asdict, dataclass

DEFAULT_MODEL = "riskgnn-node-edge"


@dataclass(frozen=True)
class ModelCapability:
    id: str
    name: str
    datasetFormats: tuple[str, ...]
    trainable: bool
    reason: str | None = None


MODELS = (
    ModelCapability(DEFAULT_MODEL, "RiskGNN · node + edge", ("sg-comrisk-v1",), True),
    ModelCapability("riskgnn-node-only", "RiskGNN · node only", ("sg-comrisk-v1",), True),
    ModelCapability("comrisk-baseline", "ComRisk baseline", (), False, "ARTIFACT_ADAPTER_PENDING"),
    ModelCapability("riskgnn-plus", "RiskGNN+", (), False, "RESEARCH_VALIDATION_PENDING"),
)


def capabilities() -> list[dict]:
    return [asdict(model) for model in MODELS]


def require_model(identity: str, dataset_format: str = "sg-comrisk-v1") -> ModelCapability:
    model = next((item for item in MODELS if item.id == identity), None)
    if model is None or not model.trainable:
        raise ValueError("Model is not available for training")
    if dataset_format not in model.datasetFormats:
        raise ValueError("Model does not support this dataset format")
    return model


def supported_models(dataset_format: str) -> list[str]:
    return [m.id for m in MODELS if m.trainable and dataset_format in m.datasetFormats]
