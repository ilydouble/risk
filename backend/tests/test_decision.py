"""Financial model HTTP adapter and business history against an isolated PostgreSQL schema."""

import asyncio
import hashlib
import json
import os
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from risk_api.errors import AppError
from risk_api.modules.auth.model import User
from risk_api.modules.decision.client import DecisionClient
from risk_api.modules.decision.model import DeployedFinancialModel, FinancialPrediction
from risk_api.modules.decision.repository import DecisionRepository
from risk_api.modules.decision.service import DecisionService
from risk_api.modules.modeling.client import ModelClient
from risk_api.modules.modeling.workbench_model import Dataset, EnterpriseImport, EnterpriseRecord
from risk_api.shared.logging import request_log_context


def model_info():
    return {
        "modelVersion": "financial-contract-v1",
        "manifestSha256": "a" * 64,
        "baseRevision": "b" * 40,
        "inputContractVersion": 1,
        "inputContractSha256": "c" * 64,
        "target": "Matched research-cohort event within 12 months",
        "labels": ["no_event", "event"],
        "calibrationAvailable": False,
        "device": "cpu",
        "dtype": "float32",
        "maxTokens": 2048,
        "supportedDatasetFormats": ["uk-financial-jsonl-v1"],
        "supportedAdapters": [{"id": "uk-financial-jsonl", "version": "1"}],
    }


def computed(info, state):
    return {
        "model": info,
        "prediction": {
            "modelVersion": info["modelVersion"],
            "manifestSha256": info["manifestSha256"],
            "expectedBaseRevision": info["baseRevision"],
            "inputContractSha256": info["inputContractSha256"],
            "bundleVerified": True,
            "questionId": "formal_insolvency_12m",
            "target": info["target"],
            "rawProbabilities": {"no_event": 0.75, "event": 0.25},
            "calibratedProbabilities": None,
            "temperature": None,
            "device": "cpu",
            "dtype": "float32",
            "inputTokensIncludingCandidates": 118,
            "stateSha256": hashlib.sha256(
                json.dumps(state, separators=(",", ":")).encode()
            ).hexdigest(),
            "inputSnapshot": state,
            "providedFeatures": list(state["features"]),
            "inferenceSeconds": 0.01,
            "limitations": ["Matched cohort; calibration unavailable"],
        },
    }


def test_financial_inference_ownership_idempotency_and_persistence():
    url = os.getenv("RISK_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set RISK_TEST_DATABASE_URL for the financial prediction contract")

    async def exercise():
        schema = "test_financial_" + uuid4().hex
        admin = create_async_engine(url)
        async with admin.begin() as connection:
            await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        engine = create_async_engine(
            url, connect_args={"server_settings": {"search_path": schema}}, hide_parameters=True
        )
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        owner, other, dataset_id = [str(uuid4()) for _ in range(3)]
        remote = {"ready": True, "corrupt": False, "info": model_info()}

        async def respond(request):
            assert request.headers["X-Request-ID"] == "financial-business-contract"
            body = json.loads(request.content)
            if request.url.path.endswith("/status"):
                result = {
                    "ready": remote["ready"],
                    "model": remote["info"] if remote["ready"] else None,
                    "errorCode": None if remote["ready"] else "DECISION_MODEL_UNAVAILABLE",
                }
            else:
                await asyncio.sleep(0.03)
                state = (
                    {"features": body["attributes"]}
                    if "attributes" in body
                    else body["input"]["state"]
                )
                result = computed(remote["info"], state)
                if remote["corrupt"]:
                    result["prediction"]["stateSha256"] = "0" * 64
            return httpx.Response(
                200, json={"code": 200, "internal_code": "SUCCESS", "message": "OK", "data": result}
            )

        async with httpx.AsyncClient(
            base_url="http://models", transport=httpx.MockTransport(respond)
        ) as http:
            client = DecisionClient(ModelClient(http))

            async def invoke(method, *args):
                async with sessions() as session:
                    service = DecisionService(DecisionRepository(session), client)
                    with request_log_context("financial-business-contract"):
                        return await getattr(service, method)(*args)

            try:
                async with engine.begin() as connection:
                    for model in (
                        User,
                        Dataset,
                        EnterpriseImport,
                        EnterpriseRecord,
                        DeployedFinancialModel,
                        FinancialPrediction,
                    ):
                        await connection.run_sync(model.__table__.create)
                async with sessions() as session:
                    session.add_all(
                        [
                            User(
                                id=identity,
                                username=identity,
                                password_hash="hash",
                                display_name=identity,
                            )
                            for identity in (owner, other)
                        ]
                    )
                    await session.flush()
                    session.add(
                        Dataset(
                            id=dataset_id,
                            owner_id=owner,
                            name="Financial observations",
                            filename="source.zip",
                            object_key=dataset_id,
                            content_type="application/zip",
                            size=1,
                            confirmed=True,
                            execution={"status": "completed"},
                        )
                    )
                    await session.flush()
                    session.add(
                        EnterpriseImport(
                            dataset_id=dataset_id,
                            sha256="d" * 64,
                            manifest={
                                "datasetContract": {
                                    "adapter": {"id": "uk-financial-jsonl", "version": "1"}
                                },
                                "sourceSha256": "e" * 64,
                            },
                            counts={"company": 1},
                        )
                    )
                    await session.flush()
                    session.add(
                        EnterpriseRecord(
                            dataset_id=dataset_id,
                            sequence=1,
                            kind="company",
                            snapshot="test",
                            node_id="observation-1",
                            members=[],
                            data={
                                "name": "Company",
                                "label": 1,
                                "properties": {
                                    "company_id": "000001",
                                    "observation_month": "2024-01",
                                },
                                "attributes": {
                                    "financial_missing": False,
                                    "cash": 0,
                                    "financial_currency": "GBP",
                                },
                            },
                        )
                    )
                    await session.commit()
                catalog = await invoke("catalog", owner)
                assert catalog["ready"] and catalog["datasets"][0].datasetId == dataset_id
                page = await invoke("companies", owner, dataset_id, "000001", 1, 20)
                assert page["total"] == 1 and page["items"][0].recordId == "observation-1"
                assert (await invoke("companies", owner, dataset_id, "Comp", 1, 20))["total"] == 1
                assert (await invoke("companies", owner, dataset_id, "absent", 1, 20))["total"] == 0
                for method, args in (
                    ("companies", (other, dataset_id, "", 1, 20)),
                    ("predict_company", (other, str(uuid4()), dataset_id, "observation-1")),
                ):
                    with pytest.raises(AppError) as denied:
                        await invoke(method, *args)
                    assert denied.value.status == 404
                key = str(uuid4())
                a, b = await asyncio.gather(
                    *[
                        invoke("predict_company", owner, key, dataset_id, "observation-1")
                        for _ in range(2)
                    ]
                )
                assert a.id == b.id and a.result.rawProbabilities.event == 0.25
                assert a.source.companyId == "000001" and a.source.recordId == "observation-1"
                with pytest.raises(AppError) as conflict:
                    await invoke("predict_company", owner, key, dataset_id, "different")
                assert conflict.value.code == "DECISION_REQUEST_CONFLICT"
                with pytest.raises(AppError) as denied:
                    await invoke("get", other, a.id)
                assert denied.value.status == 404
                preview = await invoke(
                    "predict_input",
                    owner,
                    str(uuid4()),
                    {"state": {"features": {"financial_missing": True}}},
                    "probe",
                )
                assert preview.source.kind == "input" and preview.source.datasetId is None
                assert (await invoke("history", owner, 1, 20))["total"] == 2
                assert (await invoke("history", other, 1, 20))["total"] == 0
                remote["ready"] = False
                assert not (await invoke("catalog", owner))["ready"]
                assert (await invoke("get", owner, a.id)).id == a.id
                with pytest.raises(AppError) as failed:
                    await invoke(
                        "predict_company", owner, str(uuid4()), dataset_id, "observation-1"
                    )
                assert failed.value.code == "DECISION_MODEL_UNAVAILABLE"
                remote["ready"], remote["corrupt"] = True, True
                with pytest.raises(AppError) as corrupt:
                    await invoke(
                        "predict_company", owner, str(uuid4()), dataset_id, "observation-1"
                    )
                assert corrupt.value.code == "DECISION_PROTOCOL_INVALID"
                remote["corrupt"] = False
                remote["info"]["manifestSha256"] = "f" * 64
                with pytest.raises(AppError) as version:
                    await invoke("catalog", owner)
                assert version.value.code == "DECISION_VERSION_CONFLICT"
                async with sessions() as session:
                    assert (
                        await session.scalar(select(func.count()).select_from(FinancialPrediction))
                        == 2
                    )
                    stored = await session.get(FinancialPrediction, a.id)
                    assert (
                        hashlib.sha256(stored.input_serialized.encode()).hexdigest()
                        == a.result.stateSha256
                    )
                    assert (
                        "label" not in stored.input_serialized
                        and "expected" not in stored.input_serialized
                    )
            finally:
                await engine.dispose()
                async with admin.begin() as connection:
                    await connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
                await admin.dispose()

    asyncio.run(exercise())


def test_decision_failures_keep_internal_code_and_field():
    async def exercise():
        async with httpx.AsyncClient(
            base_url="http://models",
            transport=httpx.MockTransport(
                lambda _: httpx.Response(
                    503,
                    json={
                        "code": 503,
                        "internal_code": "DECISION_BUSY",
                        "message": "busy",
                        "data": {"field": "input", "reason": "busy"},
                    },
                )
            ),
        ) as http:
            with pytest.raises(AppError) as failure:
                await ModelClient(http).call("decision/predict", {})
            assert failure.value.status == 503 and failure.value.code == "DECISION_BUSY"
            assert failure.value.field == "input"

    asyncio.run(exercise())
