from dataclasses import dataclass, field
from os import getenv
from pathlib import Path

from model_service.modules.decision.contracts.input import DEFINITION, VERSION
from model_service.shared.paths import model_root


@dataclass(frozen=True)
class DecisionSettings:
    enabled: bool = field(default_factory=lambda: getenv("DECISION_ENABLED", "true") == "true")
    model_dir: Path = field(
        default_factory=lambda: Path(
            getenv("DECISION_MODEL_DIR", str(model_root() / "weights" / VERSION))
        )
    )
    release: Path = field(
        default_factory=lambda: Path(getenv("DECISION_RELEASE", str(DEFINITION / "release.json")))
    )
    device: str = field(default_factory=lambda: getenv("DECISION_DEVICE", "cpu"))
    dtype: str = field(default_factory=lambda: getenv("DECISION_DTYPE", "float32"))
    threads: int = field(default_factory=lambda: int(getenv("DECISION_CPU_THREADS", "4")))
    timeout: float = field(default_factory=lambda: float(getenv("DECISION_TIMEOUT_SECONDS", "60")))

    def __post_init__(self) -> None:
        if getenv("DECISION_ENABLED", "true") not in {"true", "false"}:
            raise ValueError("DECISION_ENABLED must be true or false")
        if self.device not in {"cpu", "cuda"} or self.dtype not in {"float32", "bfloat16"}:
            raise ValueError("Invalid decision device/dtype")
        if not 1 <= self.threads <= 32 or not 0 < self.timeout <= 300:
            raise ValueError("Invalid decision threads/timeout")
