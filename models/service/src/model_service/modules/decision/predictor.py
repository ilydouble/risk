"""Load once, then validate and score parsed inputs with the frozen model contract."""

import hashlib
import json
import math
import time
from pathlib import Path

import torch
from jevforge import Jev
from uk_decision_runtime.runtime import load_decision_model

from model_service.modules.decision.artifacts.manifest import Release, digest, verify_bundle
from model_service.modules.decision.calibration import calibrated
from model_service.modules.decision.contracts.input import (
    DEFINITION,
    InputContract,
    input_state,
    load_contract,
)
from model_service.modules.decision.contracts.prediction import (
    DecisionModelInfo,
    DecisionPrediction,
)

REVISION = "c1899de289a04d12100db370d81485cdf75e47ca"


class Predictor:
    def __init__(
        self,
        base: Path,
        adapter: Path,
        contract: InputContract,
        *,
        device: str,
        dtype: str,
        manifest_sha256: str = "",
        contract_sha256: str,
        calibration: Path | None = None,
        bundle_verified: bool = False,
    ):
        if device == "cuda" and not torch.cuda.is_available():
            raise ValueError("CUDA was requested but is unavailable")
        if device not in {"cpu", "cuda"}:
            raise ValueError("Unsupported inference device")
        self.contract, self.device, self.dtype = contract, device, dtype
        self.manifest_sha256, self.bundle_verified = manifest_sha256, bundle_verified
        self.temperature = None
        if calibration:
            self.temperature = float(json.loads(calibration.read_text())["temperature"])
            calibrated([0.5, 0.5], self.temperature)
        self.base_sha256 = digest(base / "config.json")
        self.adapter_sha256 = digest(adapter / "adapter_model.safetensors")
        self.runtime_sha256 = digest(adapter / "decision_runtime.json")
        self.contract_sha256 = contract_sha256
        started = time.perf_counter()
        raw, tokenizer = load_decision_model(str(base), adapter, device=device, dtype=dtype)
        raw.eval()
        self.model = Jev(raw, tokenizer, mode="tree")
        self.load_seconds = time.perf_counter() - started

    @classmethod
    def load(
        cls,
        directory: Path,
        release_path: Path,
        *,
        device: str,
        dtype: str,
        base: Path | None = None,
    ) -> "Predictor":
        base = base or directory / "base"
        release = Release.model_validate_json(release_path.read_bytes())
        manifest, contract = verify_bundle(directory, release, base=base)
        if manifest.model.base.repo_id != "Qwen/Qwen3-0.6B" or (
            manifest.model.base.revision != REVISION
        ):
            raise ValueError("Unsupported decision base model/revision")
        return cls(
            base,
            directory / "adapter",
            contract,
            device=device,
            dtype=dtype,
            manifest_sha256=release.manifest_sha256,
            bundle_verified=True,
            contract_sha256=digest(directory / "input-contract.json"),
            calibration=directory / "calibration.json"
            if "calibration.json" in manifest.files
            else None,
        )

    @classmethod
    def load_local(
        cls, base: Path, adapter: Path, *, device: str, dtype: str, calibration: Path | None = None
    ) -> "Predictor":
        # Research debugging compatibility; HTTP only accepts a verified version bundle.
        return cls(
            base,
            adapter,
            load_contract(),
            device=device,
            dtype=dtype,
            contract_sha256=digest(DEFINITION / "input-contract.json"),
            calibration=calibration,
        )

    def info(self) -> DecisionModelInfo:
        return DecisionModelInfo(
            modelVersion=self.contract.model_version,
            manifestSha256=self.manifest_sha256,
            baseRevision=REVISION,
            inputContractVersion=self.contract.contract_version,
            inputContractSha256=self.contract_sha256,
            target=self.contract.question.instructions,
            labels=self.contract.output.labels,
            calibrationAvailable=self.temperature is not None,
            device=self.device,
            dtype=self.dtype,
            maxTokens=self.contract.max_tokens,
        )

    def warmup(self, directory: Path) -> None:
        result = self.score(json.loads((directory / "acceptance/input.json").read_text()))
        reference = json.loads((directory / "acceptance/reference.json").read_text())
        for case in reference["cases"]:
            if case["device"] == self.device and case["dtype"] == self.dtype:
                for name, expected in case["probabilities"].items():
                    if (
                        abs(result.rawProbabilities.model_dump()[name] - expected)
                        > (case["absolute_tolerance"])
                    ):
                        raise ValueError("Engineering loading reference mismatch")
                if result.inputTokensIncludingCandidates != case["input_tokens"]:
                    raise ValueError("Engineering input token count mismatch")

    def score(self, document: dict) -> DecisionPrediction:
        state = input_state(document, self.contract)
        question = self.contract.question
        encoded = self.model.encode(state, list(question.criteria.values()), question.instructions)
        tokens = len(encoded.prompt_ids) + len(encoded.trie.nodes)
        if tokens > self.contract.max_tokens:
            raise ValueError("Input exceeds the trained token budget; truncation is disabled")
        if self.device == "cuda":
            torch.cuda.synchronize()
            torch.cuda.reset_peak_memory_stats()
        started = time.perf_counter()
        with torch.inference_mode():
            probabilities = self.model.decide(
                state,
                list(question.criteria.values()),
                question.instructions,
            )
        if self.device == "cuda":
            torch.cuda.synchronize()
        if (
            len(probabilities) != 2
            or not all(math.isfinite(p) and 0 <= p <= 1 for p in probabilities)
            or not math.isclose(sum(probabilities), 1, abs_tol=1e-5)
        ):
            raise RuntimeError("Model returned invalid candidate probabilities")
        labels = list(question.criteria)
        adjusted = (
            dict(zip(labels, calibrated(probabilities, self.temperature), strict=True))
            if self.temperature is not None
            else None
        )
        snapshot = json.loads(state)
        return DecisionPrediction.model_validate(
            {
                "modelVersion": self.contract.model_version,
                "manifestSha256": self.manifest_sha256,
                "expectedBaseRevision": REVISION,
                "baseConfigSha256": self.base_sha256,
                "inputContractSha256": self.contract_sha256,
                "bundleVerified": self.bundle_verified,
                "device": self.device,
                "dtype": self.dtype,
                "questionId": self.contract.question_id,
                "target": question.instructions,
                "rawProbabilities": dict(zip(labels, probabilities, strict=True)),
                "calibratedProbabilities": adjusted,
                "temperature": self.temperature,
                "inputTokensIncludingCandidates": tokens,
                "stateSha256": hashlib.sha256(state.encode()).hexdigest(),
                "adapterSha256": self.adapter_sha256,
                "runtimeSha256": self.runtime_sha256,
                "loadSeconds": round(self.load_seconds, 4),
                "inferenceSeconds": round(time.perf_counter() - started, 4),
                "peakAllocatedMiB": round(torch.cuda.max_memory_allocated() / 1024**2, 2)
                if self.device == "cuda"
                else None,
                "inputSnapshot": snapshot,
                "providedFeatures": list(snapshot["features"]),
                "limitations": [
                    "Matched research-cohort scores are not population default probabilities.",
                    "CPU/dtype/batch changes require separate numerical validation.",
                    "Calibration is unavailable."
                    if self.temperature is None
                    else "Calibration applies to the matched research cohort only.",
                    *(
                        ["No observed financial values; loading probe or missing-data case only."]
                        if set(snapshot["features"]) <= {"financial_missing"}
                        else []
                    ),
                ],
            }
        )
