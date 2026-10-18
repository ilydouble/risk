"""One model instance and one compute thread per HTTP process."""

import asyncio
import contextvars
import logging
from concurrent.futures import ThreadPoolExecutor
from functools import partial

import torch

from model_service.modules.decision.contracts.prediction import (
    DecisionModelInfo,
    DecisionPrediction,
)
from model_service.modules.decision.errors import DecisionError
from model_service.modules.decision.mapping import record_input
from model_service.modules.decision.predictor import Predictor
from model_service.modules.decision.settings import DecisionSettings

logger = logging.getLogger("model_service.decision")


class DecisionService:
    def __init__(self, settings: DecisionSettings):
        self.settings = settings
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="financial-inference")
        self.predictor: Predictor | None = None
        self.pending: asyncio.Future | None = None
        self.error_code = (
            "DECISION_MODEL_DISABLED" if not settings.enabled else "DECISION_MODEL_UNAVAILABLE"
        )
        self.closed = False

    async def start(self) -> None:
        if not self.settings.enabled:
            return
        try:
            await asyncio.get_running_loop().run_in_executor(self.executor, self._load)
            logger.info(
                "decision.ready",
                extra={
                    "model_version": self.info().modelVersion,
                    "device": self.settings.device,
                    "dtype": self.settings.dtype,
                },
            )
        except Exception:
            self.predictor = None
            logger.exception("decision.load_failed", extra={"code": self.error_code})

    def _load(self) -> None:
        torch.set_num_threads(self.settings.threads)
        predictor = Predictor.load(
            self.settings.model_dir,
            self.settings.release,
            device=self.settings.device,
            dtype=self.settings.dtype,
        )
        predictor.warmup(self.settings.model_dir)
        self.predictor = predictor

    def info(self) -> DecisionModelInfo:
        if self.predictor is None or self.closed:
            raise DecisionError(503, self.error_code, "Financial model is unavailable")
        return self.predictor.info()

    async def predict(
        self, document: dict, request_id: str = "", *, expected_digest: str | None = None
    ) -> DecisionPrediction:
        info = self.info()
        if expected_digest is not None and expected_digest != info.manifestSha256:
            raise DecisionError(409, "DECISION_VERSION_CHANGED", "Deployed model version changed")
        if self.pending is not None and not self.pending.done():
            raise DecisionError(503, "DECISION_BUSY", "Financial inference slot is busy")
        assert self.predictor is not None
        context = contextvars.copy_context()
        work = partial(context.run, self.predictor.score, document)
        self.pending = asyncio.get_running_loop().run_in_executor(self.executor, work)
        # A disconnected/timed-out request must not leave an unobserved future exception.
        self.pending.add_done_callback(
            lambda task: task.exception() if not task.cancelled() else None
        )
        try:
            result = await asyncio.wait_for(asyncio.shield(self.pending), self.settings.timeout)
            logger.info(
                "decision.predicted",
                extra={
                    "request_id": request_id,
                    "model_version": result.modelVersion,
                    "state_sha256": result.stateSha256,
                    "inference_seconds": result.inferenceSeconds,
                },
            )
            return result
        except TimeoutError as error:
            # shield keeps the actual compute slot occupied until the underlying operation ends.
            raise DecisionError(
                503, "DECISION_TIMEOUT", "Financial prediction timed out"
            ) from error
        except ValueError as error:
            raise DecisionError(422, "DECISION_INPUT_INVALID", str(error), "input") from error
        except Exception as error:
            logger.exception("decision.predict_failed", extra={"request_id": request_id})
            raise DecisionError(
                503, "DECISION_PREDICTION_FAILED", "Financial prediction failed"
            ) from error

    async def predict_record(
        self,
        adapter_id: str,
        adapter_version: str,
        attributes: dict,
        request_id: str,
        expected_digest: str | None,
    ) -> DecisionPrediction:
        self.info()
        assert self.predictor is not None
        document, warnings = record_input(
            adapter_id, adapter_version, attributes, self.predictor.contract
        )
        result = await self.predict(document, request_id, expected_digest=expected_digest)
        result.limitations.extend(warnings)
        return result

    async def close(self) -> None:
        self.closed = True
        if self.pending is not None:
            await asyncio.gather(asyncio.shield(self.pending), return_exceptions=True)
        await asyncio.to_thread(self.executor.shutdown, wait=True, cancel_futures=True)
        self.predictor = None
