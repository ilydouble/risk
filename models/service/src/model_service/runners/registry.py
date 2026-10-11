from model_service.execution.contracts import Operation
from model_service.execution.runtime import runtime_spec

DEFAULT_MODEL = "riskgnn"


def capabilities() -> list[dict]:
    spec = runtime_spec()
    return [
        {
            "id": DEFAULT_MODEL,
            "name": spec.name,
            "datasetFormats": spec.dataset_formats,
            "trainable": Operation.TRAIN in spec.operations,
            "reason": None,
        }
    ]
