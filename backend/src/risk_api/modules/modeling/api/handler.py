from typing import Any

from dishka.integrations.fastapi import FromDishka
from fastapi import Request

from risk_api.modules.auth.api.handler import authorize_request
from risk_api.modules.auth.service import AuthService
from risk_api.modules.modeling.api.schemas import (
    DatasetDTO,
    ExperimentDTO,
    RequestCompleteDatasetUpload,
    RequestCreateDatasetUpload,
    RequestGetDataset,
    RequestGetExperiment,
    RequestListDatasets,
    RequestListExperiments,
    RequestRunExperiment,
    ResponseCompleteDatasetUpload,
    ResponseCreateDatasetUpload,
    ResponseGetDataset,
    ResponseGetExperiment,
    ResponseListDatasets,
    ResponseListExperiments,
    ResponseRunExperiment,
)
from risk_api.modules.modeling.model import ModelingDataset, ModelingExperiment
from risk_api.modules.modeling.service import ModelingService
from risk_api.shared.api.envelope import ApiEnvelope
from risk_api.shared.api.response import success_response


def dataset_to_dto(dataset: ModelingDataset) -> DatasetDTO:
    return DatasetDTO.model_validate(
        {
            "id": dataset.id,
            "name": dataset.name,
            "filename": dataset.filename,
            "contentType": dataset.content_type,
            "size": dataset.size,
            "status": dataset.status,
            "rowCount": dataset.row_count,
            "columnCount": dataset.column_count,
            "analysis": dataset.analysis,
            "preview": dataset.preview,
            "error": dataset.error,
            "createdAt": dataset.created_at.isoformat() if dataset.created_at else "",
        }
    )


def experiment_to_dto(experiment: ModelingExperiment) -> ExperimentDTO:
    return ExperimentDTO.model_validate(
        {
            "id": experiment.id,
            "datasetId": experiment.dataset_id,
            "name": experiment.name,
            "modelType": experiment.model_type,
            "status": experiment.status,
            "targetColumn": experiment.target_column,
            "positiveValue": experiment.positive_value,
            "featureColumns": experiment.feature_columns,
            "configuration": experiment.configuration,
            "metrics": experiment.metrics,
            "coefficients": experiment.coefficients,
            "createdAt": experiment.created_at.isoformat() if experiment.created_at else "",
        }
    )


async def _owner(request: Request, auth: AuthService) -> str:
    identity: dict[str, Any] = await authorize_request(request, auth)
    return str(identity["user_id"])


async def create_dataset_upload(
    body: RequestCreateDatasetUpload,
    request: Request,
    auth: FromDishka[AuthService],
    service: FromDishka[ModelingService],
) -> ApiEnvelope[ResponseCreateDatasetUpload]:
    owner_id = await _owner(request, auth)
    ticket = await service.create_upload(
        owner_id, body.name, body.filename, body.contentType, body.size
    )
    return success_response(
        ResponseCreateDatasetUpload(
            datasetId=ticket.dataset_id, url=ticket.url, headers=ticket.headers
        )
    )


async def complete_dataset_upload(
    body: RequestCompleteDatasetUpload,
    request: Request,
    auth: FromDishka[AuthService],
    service: FromDishka[ModelingService],
) -> ApiEnvelope[ResponseCompleteDatasetUpload]:
    dataset = await service.complete_upload(await _owner(request, auth), body.datasetId)
    return success_response(ResponseCompleteDatasetUpload(dataset=dataset_to_dto(dataset)))


async def list_datasets(
    _: RequestListDatasets,
    request: Request,
    auth: FromDishka[AuthService],
    service: FromDishka[ModelingService],
) -> ApiEnvelope[ResponseListDatasets]:
    datasets = await service.list_datasets(await _owner(request, auth))
    return success_response(ResponseListDatasets(items=[dataset_to_dto(item) for item in datasets]))


async def get_dataset(
    body: RequestGetDataset,
    request: Request,
    auth: FromDishka[AuthService],
    service: FromDishka[ModelingService],
) -> ApiEnvelope[ResponseGetDataset]:
    dataset = await service.get_dataset(await _owner(request, auth), body.datasetId)
    return success_response(ResponseGetDataset(dataset=dataset_to_dto(dataset)))


async def run_experiment(
    body: RequestRunExperiment,
    request: Request,
    auth: FromDishka[AuthService],
    service: FromDishka[ModelingService],
) -> ApiEnvelope[ResponseRunExperiment]:
    experiment = await service.run_experiment(
        await _owner(request, auth),
        body.datasetId,
        body.name,
        body.targetColumn,
        body.positiveValue,
        body.featureColumns,
        body.seed,
    )
    return success_response(ResponseRunExperiment(experiment=experiment_to_dto(experiment)))


async def list_experiments(
    _: RequestListExperiments,
    request: Request,
    auth: FromDishka[AuthService],
    service: FromDishka[ModelingService],
) -> ApiEnvelope[ResponseListExperiments]:
    experiments = await service.list_experiments(await _owner(request, auth))
    return success_response(
        ResponseListExperiments(items=[experiment_to_dto(item) for item in experiments])
    )


async def get_experiment(
    body: RequestGetExperiment,
    request: Request,
    auth: FromDishka[AuthService],
    service: FromDishka[ModelingService],
) -> ApiEnvelope[ResponseGetExperiment]:
    experiment = await service.get_experiment(await _owner(request, auth), body.experimentId)
    return success_response(ResponseGetExperiment(experiment=experiment_to_dto(experiment)))
