import base64
import binascii
from copy import deepcopy

from dishka.integrations.fastapi import FromDishka
from fastapi import Request

from risk_api.errors import AppError
from risk_api.modules.auth.api.handler import authorize_request
from risk_api.modules.auth.service import AuthService
from risk_api.modules.chat.service import ChatService
from risk_api.modules.data_prep.api.schemas import ResponsePreparationBundle
from risk_api.modules.data_prep.api.script_schemas import (
    RequestCreateScriptTask,
    RequestGenerateScript,
    RequestGetScriptTask,
    RequestRunScriptTask,
    RequestSaveScriptTask,
    RequestScriptArtifact,
    RequestScriptCatalog,
    ResponseScriptCatalog,
    ResponseScriptDelivery,
    ResponseScriptTask,
    ResponseScriptTaskList,
)
from risk_api.modules.data_prep.script_agent import propose_script
from risk_api.modules.data_prep.script_delivery import deliver
from risk_api.modules.data_prep.script_service import ScriptPreparationService, runner_call
from risk_api.modules.modeling.service import ModelingService
from risk_api.shared.api.envelope import ApiEnvelope
from risk_api.shared.api.response import success_response
from risk_api.shared.logging import current_request_id


async def catalog(_: RequestScriptCatalog, request: Request, auth: FromDishka[AuthService]
                  ) -> ApiEnvelope[ResponseScriptCatalog]:
    await authorize_request(request, auth)
    return success_response(ResponseScriptCatalog.model_validate(await runner_call("catalog", {})))


async def list_tasks(_: RequestScriptCatalog, request: Request, auth: FromDishka[AuthService],
                     scripts: FromDishka[ScriptPreparationService]
                     ) -> ApiEnvelope[ResponseScriptTaskList]:
    user = await authorize_request(request, auth)
    return success_response(ResponseScriptTaskList.model_validate(
        {"items": await scripts.list_tasks(user["user_id"])}))


async def create(body: RequestCreateScriptTask, request: Request, auth: FromDishka[AuthService],
                 scripts: FromDishka[ScriptPreparationService]) -> ApiEnvelope[ResponseScriptTask]:
    user = await authorize_request(request, auth)
    try:
        files = [(item.filename, base64.b64decode(item.contentBase64, validate=True))
                 for item in body.files]
    except binascii.Error as error:
        raise AppError(422, "DATA_PREP_CONTENT_INVALID", "文件内容无效") from error
    task = await scripts.create(user["user_id"], body.name, body.preset, body.datasetKey,
                                body.datasetVersion, body.requirements, files)
    return success_response(ResponseScriptTask.model_validate(
        await scripts.state(user["user_id"], task.id)))


async def get(body: RequestGetScriptTask, request: Request, auth: FromDishka[AuthService],
              scripts: FromDishka[ScriptPreparationService]) -> ApiEnvelope[ResponseScriptTask]:
    user = await authorize_request(request, auth)
    return success_response(ResponseScriptTask.model_validate(
        await scripts.state(user["user_id"], str(body.taskId))))


async def save(body: RequestSaveScriptTask, request: Request, auth: FromDishka[AuthService],
               scripts: FromDishka[ScriptPreparationService]) -> ApiEnvelope[ResponseScriptTask]:
    user = await authorize_request(request, auth)
    await scripts.save(user["user_id"], str(body.taskId), body.revision,
                       body.script, body.requirements)
    return success_response(ResponseScriptTask.model_validate(
        await scripts.state(user["user_id"], str(body.taskId))))


async def run(body: RequestRunScriptTask, request: Request, auth: FromDishka[AuthService],
              scripts: FromDishka[ScriptPreparationService]) -> ApiEnvelope[ResponseScriptTask]:
    user = await authorize_request(request, auth)
    await scripts.enqueue(user["user_id"], str(body.taskId), body.revision)
    return success_response(ResponseScriptTask.model_validate(
        await scripts.state(user["user_id"], str(body.taskId))))


async def generate(body: RequestGenerateScript, request: Request, auth: FromDishka[AuthService],
                   scripts: FromDishka[ScriptPreparationService], chat: FromDishka[ChatService]
                   ) -> ApiEnvelope[ResponseScriptTask]:
    user = await authorize_request(request, auth)
    owner, identity = user["user_id"], str(body.taskId)
    task = await scripts.get(owner, identity)
    if task.revision != body.revision:
        raise AppError(409, "DATA_PREP_SCRIPT_STALE", "请先保存当前任务再调用智能体")
    state = await scripts.state(owner, identity)
    history = deepcopy(task.messages)
    # Release the read transaction while the model works; save checks the revision again.
    scripts.session.expunge(task)
    await scripts.session.rollback()
    catalog = await runner_call("catalog", {})
    target = next((item for item in catalog["items"] if item["preset"] == task.preset), None)
    if target is None:
        raise AppError(422, "DATA_PREP_SCRIPT_INVALID", "目标适配器已不可用")
    selected = chat
    if body.connection:
        selected = chat.configured(
            body.connection.url, body.connection.apiKey, body.connection.model)
    proposal = await propose_script(
        task, target, state["runs"], body.message, selected, body.maxTokens)
    history.extend([{"role": "user", "content": body.message},
                    {"role": "assistant", "content": proposal["message"],
                     "toolTrace": proposal["toolTrace"]}])
    updated = await scripts.save(owner, identity, body.revision, proposal["script"],
                                 task.requirements, messages=history)
    if body.runAfter and proposal["proposed"]:
        await scripts.enqueue(owner, identity, updated.revision)
    return success_response(ResponseScriptTask.model_validate(await scripts.state(owner, identity)))


async def artifact(body: RequestScriptArtifact, request: Request, auth: FromDishka[AuthService],
                   scripts: FromDishka[ScriptPreparationService]
                   ) -> ApiEnvelope[ResponsePreparationBundle]:
    user = await authorize_request(request, auth)
    return success_response(ResponsePreparationBundle.model_validate(
        await scripts.artifact(user["user_id"], str(body.taskId), str(body.runId))))


async def deliver_artifact(body: RequestScriptArtifact, request: Request,
                          auth: FromDishka[AuthService],
                          scripts: FromDishka[ScriptPreparationService],
                          modeling: FromDishka[ModelingService]
                          ) -> ApiEnvelope[ResponseScriptDelivery]:
    user = await authorize_request(request, auth)
    identity = await deliver(scripts, modeling, user["user_id"], str(body.taskId),
                             str(body.runId), current_request_id() or "")
    return success_response(ResponseScriptDelivery(datasetId=identity))
