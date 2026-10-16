import base64
import binascii
import io
import zipfile

from dishka.integrations.fastapi import FromDishka
from fastapi import Request

from risk_api.errors import AppError
from risk_api.modules.auth.api.handler import authorize_request
from risk_api.modules.auth.service import AuthService
from risk_api.modules.chat.service import ChatService
from risk_api.modules.data_prep.agent import analyze_profile
from risk_api.modules.data_prep.api.schemas import (
    RequestGetConversion,
    RequestGetPreparation,
    RequestImportConversion,
    RequestInspectData,
    RequestListPreparations,
    RequestModelDefaults,
    RequestSaveConversionPlan,
    RequestSavePreparationMapping,
    RequestSavePreparationReport,
    RequestSuggestMapping,
    RequestTestModel,
    ResponseConversionState,
    ResponseInspectData,
    ResponseListPreparations,
    ResponseModelDefaults,
    ResponsePreparation,
    ResponsePreparationBundle,
    ResponseSuggestMapping,
    ResponseTestModel,
)
from risk_api.modules.data_prep.conversion_service import ConversionService
from risk_api.modules.data_prep.model import Preparation
from risk_api.modules.data_prep.service import PreparationService
from risk_api.shared.api.envelope import ApiEnvelope
from risk_api.shared.api.response import success_response
from risk_api.shared.config import settings


async def save_conversion_plan(
    body: RequestSaveConversionPlan, request: Request, auth: FromDishka[AuthService],
    conversions: FromDishka[ConversionService],
) -> ApiEnvelope[ResponseConversionState]:
    user = await authorize_request(request, auth)
    return success_response(ResponseConversionState.model_validate(await conversions.save_plan(
        user["user_id"], str(body.preparationId), body.plan,
    )))


async def trial_conversion(
    body: RequestGetPreparation, request: Request, auth: FromDishka[AuthService],
    conversions: FromDishka[ConversionService],
) -> ApiEnvelope[ResponseConversionState]:
    user = await authorize_request(request, auth)
    return success_response(ResponseConversionState.model_validate(await conversions.trial(
        user["user_id"], str(body.preparationId),
    )))


async def get_conversion(
    body: RequestGetConversion, request: Request, auth: FromDishka[AuthService],
    conversions: FromDishka[ConversionService],
) -> ApiEnvelope[ResponseConversionState]:
    user = await authorize_request(request, auth)
    return success_response(ResponseConversionState.model_validate(await conversions.state(
        user["user_id"], str(body.preparationId), str(body.taskId) if body.taskId else None,
    )))


async def import_conversion(
    body: RequestImportConversion, request: Request, auth: FromDishka[AuthService],
    conversions: FromDishka[ConversionService],
) -> ApiEnvelope[ResponseConversionState]:
    user = await authorize_request(request, auth)
    return success_response(ResponseConversionState.model_validate(await conversions.import_task(
        user["user_id"], str(body.preparationId), str(body.taskId),
    )))


async def inspect_data(
    body: RequestInspectData, request: Request, auth: FromDishka[AuthService],
    preparations: FromDishka[PreparationService],
) -> ApiEnvelope[ResponseInspectData]:
    user = await authorize_request(request, auth)
    if not body.filename.lower().endswith(".csv"):
        raise AppError(422, "DATA_PREP_FORMAT_UNSUPPORTED", "当前试用版支持 UTF-8 CSV")
    try:
        content = base64.b64decode(body.contentBase64, validate=True)
    except binascii.Error as error:
        raise AppError(422, "DATA_PREP_CONTENT_INVALID", "文件内容无效") from error
    item = await preparations.create(user["user_id"], body.filename, content)
    return success_response(ResponseInspectData.model_validate(
        {**item.profile, "preparationId": item.id}
    ))


async def suggest_mapping(
    body: RequestSuggestMapping,
    request: Request,
    auth: FromDishka[AuthService],
    chat: FromDishka[ChatService],
    preparations: FromDishka[PreparationService],
) -> ApiEnvelope[ResponseSuggestMapping]:
    user = await authorize_request(request, auth)
    profile = body.profile
    if profile.preparationId:
        item = await preparations.repository.get(user["user_id"], profile.preparationId)
        profile = ResponseInspectData.model_validate(item.profile)
        await preparations.repository.session.rollback()
    selected = chat
    if body.connection is not None:
        selected = chat.configured(
            body.connection.url, body.connection.apiKey, body.connection.model
        )
    report = await analyze_profile(profile, selected, body.maxTokens)
    if body.profile.preparationId:
        await preparations.report(user["user_id"], body.profile.preparationId, report.model_dump())
    return success_response(report)


def preparation_response(item: Preparation) -> ResponsePreparation:
    return ResponsePreparation.model_validate({
        "id": item.id, "filename": item.filename,
        "profile": {**item.profile, "preparationId": item.id},
        "report": item.report, "mapping": item.mapping, "confirmed": item.confirmed,
        "inWorkbench": item.in_workbench, "updatedAt": item.updated_at,
    })


async def list_preparations(body: RequestListPreparations, request: Request,
                            auth: FromDishka[AuthService],
                            preparations: FromDishka[PreparationService]
                            ) -> ApiEnvelope[ResponseListPreparations]:
    user = await authorize_request(request, auth)
    items = await preparations.repository.list(user["user_id"], workbench_only=body.workbenchOnly)
    return success_response(ResponseListPreparations(
        items=[preparation_response(item) for item in items[:100]], truncated=len(items) > 100,
    ))


async def get_preparation(body: RequestGetPreparation, request: Request,
                          auth: FromDishka[AuthService],
                          preparations: FromDishka[PreparationService]
                          ) -> ApiEnvelope[ResponsePreparation]:
    user = await authorize_request(request, auth)
    return success_response(preparation_response(
        await preparations.repository.get(user["user_id"], str(body.preparationId))
    ))


async def save_report(body: RequestSavePreparationReport, request: Request,
                      auth: FromDishka[AuthService], preparations: FromDishka[PreparationService]
                      ) -> ApiEnvelope[ResponsePreparation]:
    user = await authorize_request(request, auth)
    return success_response(preparation_response(await preparations.report(
        user["user_id"], str(body.preparationId), body.report.model_dump(),
    )))


async def save_mapping(body: RequestSavePreparationMapping, request: Request,
                       auth: FromDishka[AuthService], preparations: FromDishka[PreparationService]
                       ) -> ApiEnvelope[ResponsePreparation]:
    user = await authorize_request(request, auth)
    return success_response(preparation_response(await preparations.save_mapping(
        user["user_id"], str(body.preparationId), [item.model_dump() for item in body.mapping],
        body.confirmed, body.handoff,
    )))


async def export_preparation(body: RequestGetPreparation, request: Request,
                             auth: FromDishka[AuthService],
                             preparations: FromDishka[PreparationService]
                             ) -> ApiEnvelope[ResponsePreparationBundle]:
    user = await authorize_request(request, auth)
    item = await preparations.repository.get(user["user_id"], str(body.preparationId))
    output = io.BytesIO()
    # This is an adaptation handoff, not a model-ready contract archive.
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("source.csv", item.source)
        archive.writestr("preparation.json", preparation_response(item).model_dump_json())
        archive.writestr("README.txt", "原始案例与映射交付包，尚未执行转换，不是可训练数据包。\n"
                         "请按目标模型适配器补齐关系来源、标签语义和独立划分。\n")
    return success_response(ResponsePreparationBundle(
        filename=f"preparation-{item.id}.zip",
        contentBase64=base64.b64encode(output.getvalue()).decode(),
    ))


async def model_defaults(
    _: RequestModelDefaults, request: Request, auth: FromDishka[AuthService]
) -> ApiEnvelope[ResponseModelDefaults]:
    await authorize_request(request, auth)
    return success_response(
        ResponseModelDefaults(
            url=settings.llm_url,
            model=settings.llm_model,
            keyConfigured=bool(settings.llm_api_key.strip()),
        )
    )


async def test_model(
    body: RequestTestModel,
    request: Request,
    auth: FromDishka[AuthService],
    chat: FromDishka[ChatService],
) -> ApiEnvelope[ResponseTestModel]:
    await authorize_request(request, auth)
    selected = chat
    if body.connection is not None:
        selected = chat.configured(
            body.connection.url, body.connection.apiKey, body.connection.model
        )
    reply = await selected.complete(
        [
            {"role": "system", "content": "Reply with OK."},
            {"role": "user", "content": "OK"},
        ],
        max_tokens=128,
    )
    return success_response(ResponseTestModel(model=reply.model, elapsedMs=reply.elapsed_ms))
