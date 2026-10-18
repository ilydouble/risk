import asyncio
import json
import os
from pathlib import Path
from threading import Event
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from model_service.app import create_app
from model_service.modules.decision.contracts.input import input_state, load_contract
from model_service.modules.decision.errors import DecisionError
from model_service.modules.decision.mapping import record_input
from model_service.modules.decision.service import DecisionService
from model_service.modules.decision.settings import DecisionSettings
from model_service.shared.paths import model_root


def test_financial_record_mapping_preserves_observed_values_and_excludes_labels():
    attributes = {
        "financial_missing": 0.0,
        "cash": 0.0,
        "equity": -1000.0,
        "cat:financial_currency:GBP": 1.0,
        "cat:financial_currency:USD": 0.0,
        "cat:historical_legal_form:__unknown__": 1.0,
        "label": 1.0,
        "adverse_status": 1.0,
    }
    document, warnings = record_input("uk-dataset-v1", "2", attributes, load_contract())
    assert json.loads(input_state(document))["features"] == {
        "financial_missing": False,
        "cash": 0,
        "equity": -1000,
        "financial_currency": "GBP",
    }
    assert warnings and "historical_legal_form" in warnings[0]
    with pytest.raises(DecisionError, match="protocol"):
        record_input("uk-dataset-v1", "1", {"age_months": 12}, load_contract())
    for features in (
        {"cash": 100},
        {"financial_missing": None},
        {**attributes, "cat:financial_currency:USD": 1},
    ):
        with pytest.raises(DecisionError):
            record_input("uk-dataset-v1", "2", features, load_contract())
    native, _ = record_input(
        "uk-financial-jsonl", "1", {"financial_missing": False, "cash": 1.0}, load_contract()
    )
    assert '"cash":1.0' in input_state(native)


def test_cancellation_and_timeout_keep_the_real_compute_slot_occupied():
    async def exercise():
        entered, release = Event(), Event()

        class BlockingPredictor:
            def info(self):
                return SimpleNamespace(manifestSha256="a" * 64)

            def score(self, document):
                entered.set()
                release.wait(5)
                raise ValueError("bad input")

        service = DecisionService(DecisionSettings(enabled=False, timeout=0.1))
        service.predictor = BlockingPredictor()
        try:
            task = asyncio.create_task(service.predict({}))
            assert await asyncio.to_thread(entered.wait, 2)
            with pytest.raises(DecisionError) as timed_out:
                await task
            assert timed_out.value.code == "DECISION_TIMEOUT"
            with pytest.raises(DecisionError) as busy:
                await service.predict({})
            assert busy.value.code == "DECISION_BUSY"
            release.set()
            await asyncio.gather(service.pending, return_exceptions=True)
            entered.clear()
            release.clear()
            task = asyncio.create_task(service.predict({}))
            assert await asyncio.to_thread(entered.wait, 2)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            with pytest.raises(DecisionError) as busy:
                await service.predict({})
            assert busy.value.code == "DECISION_BUSY"
        finally:
            release.set()
            await service.close()

    asyncio.run(exercise())


def test_model_unavailable_does_not_break_other_routes(monkeypatch, tmp_path):
    monkeypatch.setenv("DECISION_ENABLED", "true")
    monkeypatch.setenv("DECISION_MODEL_DIR", str(tmp_path / "missing"))
    monkeypatch.setenv("RISK_GNN_API_TOKEN", "test-decision")
    with TestClient(create_app(), raise_server_exceptions=False) as client:
        headers = {"Authorization": "Bearer test-decision", "X-Request-ID": "unavailable"}
        assert client.post("/internal/v1/decision/status", json={}).status_code == 401
        response = client.post("/internal/v1/decision/status", json={}, headers=headers)
        assert not response.json()["data"]["ready"]
        failed = client.post("/internal/v1/decision/predict", json={"input": {}}, headers=headers)
        assert failed.status_code == failed.json()["code"] == 503
        assert failed.json()["internal_code"] == "DECISION_MODEL_UNAVAILABLE"
        assert failed.headers["X-Request-ID"] == "unavailable"
        assert client.get("/health/live").status_code == 200
        assert (
            client.post("/internal/v1/models/capabilities", json={}, headers=headers).status_code
            == 200
        )


def test_real_decision_http_model(monkeypatch, request):
    if not request.config.getoption("--require-decision-model"):
        pytest.skip("Pass --require-decision-model to exercise real weights")
    root = Path(os.environ.get(
        "RISK_DECISION_TEST_MODEL_DIR", str(model_root() / "weights/uk-financial-0.6b-v1-verified")
    )).resolve()
    if not (root / "manifest.json").is_file():
        pytest.fail(f"Required model is missing: {root}")
    monkeypatch.setenv("DECISION_ENABLED", "true")
    monkeypatch.setenv("DECISION_MODEL_DIR", str(root))
    monkeypatch.setenv("DECISION_DEVICE", os.environ.get("RISK_DECISION_TEST_DEVICE", "cpu"))
    monkeypatch.setenv("DECISION_DTYPE", os.environ.get("RISK_DECISION_TEST_DTYPE", "float32"))
    monkeypatch.setenv("RISK_GNN_API_TOKEN", "test-decision")
    with TestClient(create_app(), raise_server_exceptions=False) as client:
        headers = {"Authorization": "Bearer test-decision", "X-Request-ID": "real-decision"}
        model = client.post("/internal/v1/decision/status", json={}, headers=headers).json()["data"]
        assert model["ready"], model
        digest = model["model"]["manifestSha256"]
        document = json.loads((root / "acceptance/input.json").read_text())
        for _ in range(2):
            response = client.post(
                "/internal/v1/decision/predict",
                headers=headers,
                json={"input": document, "expectedManifestSha256": digest},
            )
            assert response.status_code == 200, response.text
            assert response.headers["X-Request-ID"] == "real-decision"
            prediction = response.json()["data"]["prediction"]
            references = json.loads((root / "acceptance/reference.json").read_text())
            reference = next(c for c in references["cases"] if c["device"] == prediction["device"])
            assert prediction["rawProbabilities"] == pytest.approx(
                reference["probabilities"], abs=reference["absolute_tolerance"]
            )
            assert prediction["calibratedProbabilities"] is None
        invalid = client.post(
            "/internal/v1/decision/predict",
            headers=headers,
            json={"input": {"state": {"features": {"label": 1}}}},
        )
        assert (
            invalid.status_code == 422
            and invalid.json()["internal_code"] == "DECISION_INPUT_INVALID"
        )
        changed = client.post(
            "/internal/v1/decision/predict",
            headers=headers,
            json={"input": document, "expectedManifestSha256": "0" * 64},
        )
        assert changed.status_code == 409
        data_root = os.getenv("RISK_DECISION_TEST_DATA_DIR")
        if data_root:
            with (Path(data_root) / "test.financial.jsonl").open() as stream:
                document = json.loads(stream.readline())
            result = client.post("/internal/v1/decision/predict", headers=headers,
                                 json={"input": document, "expectedManifestSha256": digest})
            assert result.status_code == 200, result.text
            prediction = result.json()["data"]["prediction"]
            assert prediction["inputSnapshot"] == document["state"]
            assert "expected" not in prediction["inputSnapshot"]
