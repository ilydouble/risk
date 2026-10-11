from dishka.integrations.fastapi import FromDishka
from fastapi import Request

from model_service.modules.jobs.api.schemas import (
    RequestEvents,
    RequestJob,
    RequestSubmitJob,
    ResponseEvents,
    ResponseJob,
)
from model_service.modules.jobs.repository import Store
from model_service.shared.api.envelope import Envelope
from model_service.shared.api.response import success_response


async def submit(
    body: RequestSubmitJob, request: Request, store: FromDishka[Store]
) -> Envelope[ResponseJob]:
    await store.submit(
        str(body.jobId),
        body.kind,
        body.payload.model_dump(mode="json", exclude_none=True),
        request.state.request_id,
    )
    return success_response(ResponseJob.model_validate(await store.get(str(body.jobId))))


async def get(body: RequestJob, store: FromDishka[Store]) -> Envelope[ResponseJob]:
    return success_response(ResponseJob.model_validate(await store.get(str(body.jobId))))


async def cancel(body: RequestJob, store: FromDishka[Store]) -> Envelope[ResponseJob]:
    await store.cancel(str(body.jobId))
    return success_response(ResponseJob.model_validate(await store.get(str(body.jobId))))


async def events(body: RequestEvents, store: FromDishka[Store]) -> Envelope[ResponseEvents]:
    await store.get(str(body.jobId))
    return success_response(
        ResponseEvents.model_validate({"items": await store.events(str(body.jobId), body.after)})
    )
