from stellarmesh_objectstorage import StorageError

from risk_api.errors import AppError
from risk_api.modules.data_prep.script_service import ScriptPreparationService, sha
from risk_api.modules.modeling.service import ModelingService


async def deliver(scripts: ScriptPreparationService, modeling: ModelingService,
                  owner: str, task_id: str, run_id: str, request_id: str) -> str:
    run = await scripts.owned_run(owner, task_id, run_id, lock=True)
    if run.status != "ready" or not run.artifact or sha(run.artifact) != run.artifact_sha:
        raise AppError(409, "DATA_PREP_SCRIPT_STALE", "请先执行脚本并通过数据集校验")
    result = dict(run.result)
    dataset_id = result.get("deliveryDatasetId")
    if not dataset_id:
        ticket = await modeling.create_upload(
            owner, run.specification["name"], f"dataset-{run.id}.zip", "application/zip",
            len(run.artifact), commit=False,
        )
        dataset_id = ticket["datasetId"]
        dataset = await modeling.repository.dataset(owner, dataset_id)
        dataset.mapping_snapshot = {
            "scriptTaskId": task_id, "scriptRunId": run_id, "revision": run.revision,
            "sourceSha256": run.specification["sourceSha256"],
            "scriptSha256": run.script_sha, "artifactSha256": run.artifact_sha,
            "runtimeImage": result.get("runtimeImage"),
        }
        result["deliveryDatasetId"] = dataset_id
        run.result = result
        # Save the dataset identity atomically so failed uploads retry the same object.
        await scripts.session.commit()
    dataset = await modeling.repository.dataset(owner, dataset_id)
    if not dataset.confirmed:
        try:
            await modeling.storage.upload_bytes(
                dataset.object_key, run.artifact, content_type="application/zip",
            )
        except StorageError as error:
            raise AppError(503, "DATA_PREP_RUNNER_UNAVAILABLE",
                           "交付上传失败，可重试同一次交付") from error
        await modeling.complete_upload(owner, dataset_id, request_id)
    if not run.result.get("deliveryCompleted"):
        run.result = {**run.result, "deliveryCompleted": True}
        await scripts.session.commit()
    return dataset_id
