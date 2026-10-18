"""Real Strands streaming preserves the server's financial result as a display item."""

import asyncio
import json
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import uuid4

import httpx
import pytest
from openai import AsyncOpenAI
from pydantic import TypeAdapter

from risk_api.errors import AppError
from risk_api.modules.assistant import runtime
from risk_api.modules.assistant.protocol.items import Item
from risk_api.modules.assistant.runtime import ModelSettings, StrandsRuntime
from risk_api.modules.assistant.tools import financial_risk
from risk_api.modules.decision.contracts import SavedFinancialPrediction


@pytest.mark.parametrize("unavailable", [False, True])
def test_financial_tool_result_is_owner_bound_and_replayable(monkeypatch, unavailable):
    dataset, prediction, model = [str(uuid4()) for _ in range(3)]
    calls, requests = [], []

    @asynccontextmanager
    async def sessions():
        yield object()

    class Service:
        def __init__(self, *_args):
            pass

        async def predict_company(self, owner, key, dataset_id, record_id):
            calls.append((owner, dataset_id, record_id))
            if unavailable:
                raise AppError(503, "DECISION_MODEL_UNAVAILABLE", "财务模型未就绪。")
            return SavedFinancialPrediction.model_validate({
                "id": prediction,
                "model": {
                    "id": model, "modelVersion": "financial-v1", "manifestSha256": "a" * 64,
                    "baseRevision": "b" * 40, "inputContractVersion": 1,
                    "inputContractSha256": "c" * 64, "target": "Matched cohort event",
                    "labels": ["no_event", "event"], "calibrationAvailable": False,
                    "device": "cpu", "dtype": "float32", "maxTokens": 2048,
                    "supportedDatasetFormats": ["uk-financial-jsonl-v1"],
                    "supportedAdapters": [{"id": "uk-financial-jsonl", "version": "1"}],
                },
                "source": {"kind": "company", "datasetId": dataset, "recordId": record_id,
                           "companyId": "000001", "companyName": "Source company",
                           "observationMonth": "2024-01"},
                "result": {
                    "modelVersion": "financial-v1", "manifestSha256": "a" * 64,
                    "expectedBaseRevision": "b" * 40, "inputContractSha256": "c" * 64,
                    "bundleVerified": True, "questionId": "formal_insolvency_12m",
                    "target": "Matched cohort event",
                    "rawProbabilities": {"no_event": 0.7, "event": 0.3},
                    "calibratedProbabilities": None, "temperature": None,
                    "device": "cpu", "dtype": "float32", "inputTokensIncludingCandidates": 100,
                    "stateSha256": "d" * 64, "inferenceSeconds": 0.1,
                    "providedFeatures": ["financial_missing", "cash"],
                    "limitations": ["Calibration unavailable; matched research cohort"],
                },
                "createdAt": datetime.now(UTC),
            })

    monkeypatch.setattr(financial_risk, "DecisionService", Service)

    def respond(request):
        payload = json.loads(request.content)
        requests.append(payload)
        if len(requests) == 1:
            tools = {row["function"]["name"]: row["function"] for row in payload["tools"]}
            assert {"financial_risk_catalog", "financial_risk_companies",
                    "predict_company_financial_risk"} <= tools.keys()
            parameters = tools["predict_company_financial_risk"]["parameters"]
            assert set(parameters["properties"]) == {"dataset_id", "record_id"}
            delta = {"tool_calls": [{"index": 0, "id": "financial", "type": "function",
                      "function": {"name": "predict_company_financial_risk", "arguments":
                          json.dumps({"dataset_id": dataset, "record_id": "observation-1"})}}]}
            stop = "tool_calls"
        else:
            output = next(row for row in payload["messages"] if row["role"] == "tool")
            assert ("DECISION_MODEL_UNAVAILABLE" if unavailable else prediction) in str(output)
            assert "inputSnapshot" not in str(output)
            delta, stop = {"content": "模型未就绪" if unavailable else "评分已保存"}, "stop"
        chunks = [
            {"id": "c", "object": "chat.completion.chunk", "created": 1, "model": "test",
             "choices": [{"index": 0, "delta": delta, "finish_reason": None}]},
            {"id": "c", "object": "chat.completion.chunk", "created": 1, "model": "test",
             "choices": [{"index": 0, "delta": {}, "finish_reason": stop}]},
        ]
        body = "".join(f"data: {json.dumps(chunk)}\n\n" for chunk in chunks) + "data: [DONE]\n\n"
        return httpx.Response(200, text=body, headers={"Content-Type": "text/event-stream"})

    async def exercise():
        client = AsyncOpenAI(api_key="test", http_client=httpx.AsyncClient(
            transport=httpx.MockTransport(respond)
        ))
        monkeypatch.setattr(runtime, "AsyncOpenAI", lambda **_kwargs: client)
        agent, items = StrandsRuntime(sessions, model_client=object()), {}
        async for batch in agent.stream(
            "对该公司财务观测评分", [],
            ModelSettings("http://model/v1/chat/completions", "test", 1024, "key"),
            "financial-request", "bound-owner",
        ):
            for item in batch:
                items[item.id] = item
        item = next(row for row in items.values() if row.kind == "tool_call")
        assert item.status == ("failed" if unavailable else "completed")
        restored = TypeAdapter(Item).validate_json(item.model_dump_json())
        if unavailable:
            assert restored.financialPrediction is None
        else:
            reference = restored.financialPrediction
            assert reference.predictionId == prediction and reference.recordId == "observation-1"
            assert reference.eventScore == 0.3 and reference.calibratedEventScore is None
            assert reference.limitations == ["Calibration unavailable; matched research cohort"]

    asyncio.run(exercise())
    assert calls == [("bound-owner", dataset, "observation-1")]
