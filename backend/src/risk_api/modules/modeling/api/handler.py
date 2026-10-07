from typing import Any

from dishka.integrations.fastapi import FromDishka
from fastapi import Request

from risk_api.modules.auth.api.handler import authorize_request
from risk_api.modules.auth.service import AuthService
from risk_api.modules.modeling.api import schemas as dto
from risk_api.modules.modeling.service import ModelingService
from risk_api.modules.modeling.workbench_model import Dataset, ModelVersion, Run
from risk_api.shared.api.envelope import ApiEnvelope
from risk_api.shared.api.response import success_response


def dataset_dto(item: Dataset) -> dto.DatasetDTO:
    execution = item.execution
    result = execution.get("result", {})
    status = execution.get("status", "queued" if item.confirmed else "pending_upload")
    return dto.DatasetDTO(
        dataFormat=result.get("protocol"),
        supportedRunnerIds=result.get(
            "supportedRunnerIds",
            ["riskgnn-node-edge"] if result.get("protocol") == "sg-comrisk-v1" else [],
        ),
        analysis=result.get("analysis"),
        profile=result.get("datasetProfile", {}),
        id=item.id,
        name=item.name,
        filename=item.filename,
        size=item.size,
        status="ready" if status == "completed" else status,
        stage=execution.get("stage", status),
        files=result.get("files", []),
        counts=result.get("counts", {}),
        labeledCount=result.get("labeledCount"),
        positiveCount=result.get("positiveCount"),
        sha256=result.get("sha256"),
        error=execution.get("error"),
        createdAt=item.created_at.isoformat(),
    )


def run_dto(item: Run) -> dto.RunDTO:
    execution = item.execution
    return dto.RunDTO(
        profile=execution.get("result", {}).get("profile", {}).get("experimentProfile"),
        runnerId=item.configuration.get("runnerId", "riskgnn-node-edge"),
        id=item.id,
        name=item.name,
        datasetId=item.dataset_id,
        retryOf=item.retry_of,
        status=execution.get("status", "queued"),
        stage=execution.get("stage", "queued"),
        epochs=item.configuration["epochs"],
        cancelRequested=execution.get("cancelRequested", False),
        attempts=execution.get("attempts", []),
        result=execution.get("result", {}),
        error=execution.get("error"),
        createdAt=item.created_at.isoformat(),
    )


def model_dto(item: ModelVersion) -> dto.ModelVersionDTO:
    return dto.ModelVersionDTO(
        runnerId=item.artifact.get("profile", {}).get("runnerId", "riskgnn-node-edge"),
        id=item.id,
        name=item.name,
        runId=item.run_id,
        sha256=item.artifact["sha256"],
        size=item.artifact["size"],
        report=item.artifact["report"],
        companies=item.artifact.get("companies", []),
        createdAt=item.created_at.isoformat(),
    )


async def owner(request: Request, auth: AuthService) -> str:
    identity: dict[str, Any] = await authorize_request(request, auth)
    return str(identity["user_id"])


async def create_upload(
    body: dto.RequestCreateDatasetUpload,
    request: Request,
    auth: FromDishka[AuthService],
    service: FromDishka[ModelingService],
) -> ApiEnvelope[dto.ResponseCreateDatasetUpload]:
    user = await owner(request, auth)
    ticket = await service.create_upload(
        user, body.name, body.filename, body.contentType, body.size
    )
    return success_response(dto.ResponseCreateDatasetUpload(**ticket))


async def complete_upload(
    body: dto.RequestCompleteDatasetUpload,
    request: Request,
    auth: FromDishka[AuthService],
    service: FromDishka[ModelingService],
) -> ApiEnvelope[dto.ResponseCompleteDatasetUpload]:
    user = await owner(request, auth)
    item = await service.complete_upload(user, str(body.datasetId), request.state.request_id)
    return success_response(dto.ResponseCompleteDatasetUpload(dataset=dataset_dto(item)))


async def get_dataset(
    body: dto.RequestGetDataset,
    request: Request,
    auth: FromDishka[AuthService],
    service: FromDishka[ModelingService],
) -> ApiEnvelope[dto.ResponseGetDataset]:
    user = await owner(request, auth)
    item = await service.get_dataset(user, str(body.datasetId))
    return success_response(dto.ResponseGetDataset(dataset=dataset_dto(item)))


async def create_run(
    body: dto.RequestCreateRun,
    request: Request,
    auth: FromDishka[AuthService],
    service: FromDishka[ModelingService],
) -> ApiEnvelope[dto.ResponseCreateRun]:
    user = await owner(request, auth)
    item = await service.create_run(
        user,
        str(body.datasetId),
        body.name,
        str(body.requestKey),
        body.epochs,
        request.state.request_id,
        runner_id=body.runnerId,
    )
    return success_response(dto.ResponseCreateRun(run=run_dto(item)))


async def get_run(
    body: dto.RequestGetRun,
    request: Request,
    auth: FromDishka[AuthService],
    service: FromDishka[ModelingService],
) -> ApiEnvelope[dto.ResponseGetRun]:
    user = await owner(request, auth)
    item = await service.get_run(user, str(body.runId))
    return success_response(dto.ResponseGetRun(run=run_dto(item)))


async def cancel_run(
    body: dto.RequestCancelRun,
    request: Request,
    auth: FromDishka[AuthService],
    service: FromDishka[ModelingService],
) -> ApiEnvelope[dto.ResponseCancelRun]:
    user = await owner(request, auth)
    item = await service.cancel(user, str(body.runId), request.state.request_id)
    return success_response(dto.ResponseCancelRun(run=run_dto(item)))


async def rerun(
    body: dto.RequestRerun,
    request: Request,
    auth: FromDishka[AuthService],
    service: FromDishka[ModelingService],
) -> ApiEnvelope[dto.ResponseRerun]:
    user = await owner(request, auth)
    item = await service.rerun(
        user, str(body.runId), str(body.requestKey), request.state.request_id
    )
    return success_response(dto.ResponseRerun(run=run_dto(item)))


async def run_events(
    body: dto.RequestRunEvents,
    request: Request,
    auth: FromDishka[AuthService],
    service: FromDishka[ModelingService],
) -> ApiEnvelope[dto.ResponseRunEvents]:
    user = await owner(request, auth)
    result = await service.events(user, str(body.runId), body.after)
    return success_response(dto.ResponseRunEvents(**result))


async def publish_model(
    body: dto.RequestPublishModel,
    request: Request,
    auth: FromDishka[AuthService],
    service: FromDishka[ModelingService],
) -> ApiEnvelope[dto.ResponsePublishModel]:
    user = await owner(request, auth)
    item = await service.publish(user, str(body.runId), body.name)
    return success_response(dto.ResponsePublishModel(model=model_dto(item)))


async def get_model(
    body: dto.RequestGetModel,
    request: Request,
    auth: FromDishka[AuthService],
    service: FromDishka[ModelingService],
) -> ApiEnvelope[dto.ResponseGetModel]:
    user = await owner(request, auth)
    item = await service.repository.version(user, str(body.modelId))
    return success_response(dto.ResponseGetModel(model=model_dto(item)))


async def download_model(
    body: dto.RequestDownloadModel,
    request: Request,
    auth: FromDishka[AuthService],
    service: FromDishka[ModelingService],
) -> ApiEnvelope[dto.ResponseDownloadModel]:
    user = await owner(request, auth)
    result = await service.download(user, str(body.modelId))
    return success_response(dto.ResponseDownloadModel(**result))


async def predict_model(
    body: dto.RequestPredictModel,
    request: Request,
    auth: FromDishka[AuthService],
    service: FromDishka[ModelingService],
) -> ApiEnvelope[dto.ResponsePredictModel]:
    user = await owner(request, auth)
    result = await service.predict(
        user, str(body.modelId), body.companyIds, request.state.request_id
    )
    return success_response(dto.ResponsePredictModel(**result))


async def list_datasets(
    body: dto.RequestListDatasets,
    request: Request,
    auth: FromDishka[AuthService],
    service: FromDishka[ModelingService],
) -> ApiEnvelope[dto.ResponseListDatasets]:
    user = await owner(request, auth)
    items, total = await service.repository.page(
        Dataset, user, body.pagination.page, body.pagination.pageSize
    )
    for item in items:
        await service.refresh(item)
    return success_response(
        dto.ResponseListDatasets(
            items=[dataset_dto(item) for item in items],
            total=total,
            page=body.pagination.page,
            pageSize=body.pagination.pageSize,
        )
    )


async def list_runs(
    body: dto.RequestListRuns,
    request: Request,
    auth: FromDishka[AuthService],
    service: FromDishka[ModelingService],
) -> ApiEnvelope[dto.ResponseListRuns]:
    user = await owner(request, auth)
    items, total = await service.repository.page(
        Run, user, body.pagination.page, body.pagination.pageSize
    )
    for item in items:
        await service.refresh(item)
    return success_response(
        dto.ResponseListRuns(
            items=[run_dto(item) for item in items],
            total=total,
            page=body.pagination.page,
            pageSize=body.pagination.pageSize,
        )
    )


async def list_models(
    body: dto.RequestListModels,
    request: Request,
    auth: FromDishka[AuthService],
    service: FromDishka[ModelingService],
) -> ApiEnvelope[dto.ResponseListModels]:
    user = await owner(request, auth)
    items, total = await service.repository.page(
        ModelVersion, user, body.pagination.page, body.pagination.pageSize
    )
    return success_response(
        dto.ResponseListModels(
            items=[model_dto(item) for item in items],
            total=total,
            page=body.pagination.page,
            pageSize=body.pagination.pageSize,
        )
    )


async def capabilities(
    body: dto.RequestModelingCapabilities,
    request: Request,
    auth: FromDishka[AuthService],
    service: FromDishka[ModelingService],
) -> ApiEnvelope[dto.ResponseModelingCapabilities]:
    await owner(request, auth)
    result = await service.capabilities()
    return success_response(dto.ResponseModelingCapabilities(**result))
