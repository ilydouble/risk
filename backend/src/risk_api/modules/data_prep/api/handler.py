import base64
import binascii
import json

from dishka.integrations.fastapi import FromDishka
from fastapi import Request
from pydantic import ValidationError

from risk_api.errors import AppError
from risk_api.modules.auth.api.handler import authorize_request
from risk_api.modules.auth.service import AuthService
from risk_api.modules.chat.service import ChatService
from risk_api.modules.data_prep.api.schemas import (
    RequestInspectData,
    RequestModelDefaults,
    RequestSuggestMapping,
    RequestTestModel,
    ResponseInspectData,
    ResponseModelDefaults,
    ResponseSuggestMapping,
    ResponseTestModel,
)
from risk_api.modules.data_prep.profile import inspect_csv
from risk_api.shared.api.envelope import ApiEnvelope
from risk_api.shared.api.response import success_response
from risk_api.shared.config import settings


async def inspect_data(
    body: RequestInspectData, request: Request, auth: FromDishka[AuthService]
) -> ApiEnvelope[ResponseInspectData]:
    await authorize_request(request, auth)
    if not body.filename.lower().endswith(".csv"):
        raise AppError(422, "DATA_PREP_FORMAT_UNSUPPORTED", "当前试用版支持 UTF-8 CSV")
    try:
        content = base64.b64decode(body.contentBase64, validate=True)
    except binascii.Error as error:
        raise AppError(422, "DATA_PREP_CONTENT_INVALID", "文件内容无效") from error
    return success_response(ResponseInspectData.model_validate(inspect_csv(content)))


async def suggest_mapping(
    body: RequestSuggestMapping,
    request: Request,
    auth: FromDishka[AuthService],
    chat: FromDishka[ChatService],
) -> ApiEnvelope[ResponseSuggestMapping]:
    await authorize_request(request, auth)
    context = {
        "rowCount": body.profile.rowCount,
        "rowsWithMissing": body.profile.rowsWithMissing,
        "duplicateRows": body.profile.duplicateRows,
        "fields": [
            {
                "name": field.name,
                "typeHint": field.typeHint,
                "missingCount": field.missingCount,
                "distinctCount": field.distinctCount,
                "numericRate": field.numericRate,
                "dateRate": field.dateRate,
                "topValues": [item.model_dump() for item in field.topValues],
                "numericSummary": field.numericSummary.model_dump()
                if field.numericSummary
                else None,
            }
            for field in body.profile.fields
        ],
        "qualityIssues": [item.model_dump() for item in body.profile.issues[:30]],
        "keyCandidates": [item.model_dump() for item in body.profile.keyCandidates],
        "labelCandidates": [item.model_dump() for item in body.profile.labelCandidates],
    }
    selected = chat
    if body.connection is not None:
        selected = chat.configured(
            body.connection.url, body.connection.apiKey, body.connection.model
        )
    reply = await selected.complete(
        [
            {
                "role": "system",
                "content": (
                    "你是企业不良状态数据分析助手。只根据提供的统计信息提出待人工确认的建议。"
                    "先分析缺失、重复、混合格式、离群值、疑似标识/关联键和标签分布，"
                    "再建议字段用途与下一步核查。不得根据 0/1 推断哪类是不良状态；"
                    "只能引用已有字段名，不得编造事实、标签含义或跨表关系。"
                    "统计线索不是字段语义的证明。只输出 JSON："
                    '{"summary":"...","qualityFindings":["..."],"suggestions":[{"field":"...",'
                    '"role":"identity|feature|label|relation|time|ignore|unknown","reason":"..."}],'
                    '"questions":["..."],"nextChecks":["..."]}。'
                    "角色不确定时填 unknown；不要要求执行 SQL、修改数据或训练模型。"
                ),
            },
            {"role": "user", "content": json.dumps(context, ensure_ascii=False)},
        ],
        max_tokens=body.maxTokens,
    )
    try:
        content = reply.content.strip().removeprefix("```json").removesuffix("```").strip()
        output = ResponseSuggestMapping.model_validate_json(content)
    except ValidationError as error:
        raise AppError(502, "DATA_PREP_SUGGESTION_INVALID", "智能分析结果格式异常") from error
    names = {field.name for field in body.profile.fields}
    roles = {"identity", "feature", "label", "relation", "time", "ignore", "unknown"}
    if any(item.field not in names or item.role not in roles for item in output.suggestions):
        raise AppError(502, "DATA_PREP_SUGGESTION_INVALID", "智能分析引用了未知字段或用途")
    return success_response(output)


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
