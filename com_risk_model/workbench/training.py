from __future__ import annotations

import asyncio
import hashlib
import io
import json
import zipfile
from typing import TYPE_CHECKING, Any

from workbench.data import load_bundle
from workbench.tabular import TabularSuite, train_tabular_suite

if TYPE_CHECKING:
    from workbench.worker import Job, ModelingWorker


def _artifact(suite: TabularSuite, results: dict[str, Any]) -> bytes:
    stream = io.BytesIO()
    selection = {
        "selected": suite.selection.selected,
        "excluded": suite.selection.excluded,
        "ranking": suite.selection.ranking,
        "configuration": suite.selection.configuration,
    }
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("results.json", json.dumps(results, ensure_ascii=False, indent=2))
        archive.writestr(
            "feature-selection.json", json.dumps(selection, ensure_ascii=False, indent=2)
        )
        for variant in suite.variants:
            archive.writestr(f"models/{variant.name}.joblib", variant.artifact)
    return stream.getvalue()


def _train(data: Any, request: dict[str, Any]) -> tuple[TabularSuite, dict[str, Any]]:
    configuration = request["configuration"]
    suite = train_tabular_suite(
        data,
        requested_models=list(request["requested_models"]),
        feature_mode=str(configuration["featureMode"]),
        manual_features=list(request["feature_columns"]),
        seed=int(configuration["seed"]),
    )
    task_type = data.metadata.task_type
    results = {
        "taskType": task_type,
        "targetName": data.metadata.target.name,
        "targetDefinition": data.metadata.target.business_definition,
        "variants": [variant.result for variant in suite.variants],
        "featureSelection": {
            "selected": suite.selection.selected,
            "excluded": suite.selection.excluded,
            "ranking": suite.selection.ranking,
            "configuration": suite.selection.configuration,
        },
        "disclaimer": (
            "该结果是贷款申请级离线实验，不代表已投入生产授信。"
            if task_type == "loan_application"
            else "该结果是企业快照级经营风险实验，不是贷款违约概率。"
        ),
    }
    return suite, results


async def run_experiment(worker: ModelingWorker, job: Job) -> None:
    request = await worker.store.experiment_request(job)
    await worker.store.progress(job, "downloading", 5)
    payload = await worker._download(str(job.payload["objectKey"]))
    await worker.store.progress(job, "validating", 10)
    data = await asyncio.to_thread(load_bundle, payload)
    await worker.store.progress(job, "training_tabular", 25)
    suite, results = await asyncio.to_thread(_train, data, request)
    requested = set(request["requested_models"])
    completed = {variant.name for variant in suite.variants}
    unsupported = requested.difference(completed)
    if unsupported:
        raise RuntimeError(f"requested model variants are not implemented: {sorted(unsupported)}")
    await worker.store.progress(job, "saving_artifacts", 90)
    artifact = await asyncio.to_thread(_artifact, suite, results)
    object_key = (
        f"modeling/{job.owner_id}/{job.dataset_id}/experiments/"
        f"{job.experiment_id}/artifact.zip"
    )
    await worker.storage.upload_bytes(object_key, artifact, content_type="application/zip")
    artifact_manifest = {
        "objectKey": object_key,
        "sizeBytes": len(artifact),
        "sha256": hashlib.sha256(artifact).hexdigest(),
        "format": "workbench-experiment-v1",
        "autoPublished": False,
    }
    await worker.store.complete_experiment(
        job, suite.selection.selected, results, artifact_manifest
    )
