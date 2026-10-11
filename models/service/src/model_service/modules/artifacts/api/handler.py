from dishka.integrations.fastapi import FromDishka

from model_service.modules.jobs.api.schemas import RequestJob, ResponseJob
from model_service.modules.jobs.repository import Store
from model_service.shared.api.envelope import Envelope
from model_service.shared.api.response import success_response


async def artifact(body: RequestJob, store: FromDishka[Store]) -> Envelope[ResponseJob]:
    # Existing clients receive a job snapshot here, so its DTO remains owned by jobs.
    return success_response(ResponseJob.model_validate(await store.get(str(body.jobId))))
