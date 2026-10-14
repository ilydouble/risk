"""Resume validated uploads into enterprise browsing without a browser polling them."""

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import exists, func, select

from risk_api.errors import AppError
from risk_api.modules.modeling.enterprise_data import FORMAT
from risk_api.modules.modeling.enterprise_service import EnterpriseService
from risk_api.modules.modeling.service import ModelingService
from risk_api.modules.modeling.workbench_model import Dataset, EnterpriseImport

logger = logging.getLogger(__name__)


async def synchronize(service: ModelingService, dataset: Dataset) -> None:
    await service.refresh(dataset)
    if dataset.execution.get("status") != "completed":
        return
    artifact = dataset.execution.get("result", {}).get("enterpriseArtifact", {})
    if artifact.get("format") != FORMAT:
        return
    if await service.session.get(EnterpriseImport, dataset.id):
        return
    retry = dataset.execution.get("enterpriseSync", {}).get("retryAfter")
    if retry and datetime.fromisoformat(retry) > datetime.now(UTC):
        return
    identity, owner = dataset.id, dataset.owner_id
    try:
        await EnterpriseService(service).import_dataset(owner, identity)
    except AppError as error:
        # Import rolls back on malformed artifacts. Re-read rather than touching expired ORM state.
        await service.session.rollback()
        item = await service.repository.dataset(owner, identity)
        item.execution = {
            **item.execution,
            "enterpriseSync": {
                "status": "failed",
                "errorCode": error.code,
                "retryAfter": (datetime.now(UTC) + timedelta(seconds=60)).isoformat(),
            },
        }
        await service.session.commit()
        logger.warning(
            "enterprise.sync_failed", extra={"dataset_id": identity, "internal_code": error.code}
        )


async def enterprise_sync_loop(container) -> None:
    cursor = ""
    while True:
        delay = 2.0
        try:
            # Each scope/session is closed after one dataset; no transaction survives a sleep.
            async with container() as scope:
                service = await scope.get(ModelingService)
                dataset = await service.session.scalar(
                    select(Dataset)
                    .where(
                        Dataset.confirmed.is_(True),
                        Dataset.protocol_generation == 2,
                        Dataset.id > cursor,
                        ~exists().where(EnterpriseImport.dataset_id == Dataset.id),
                        func.coalesce(Dataset.execution["status"].astext, "queued").notin_(
                            ["failed", "cancelled"]
                        ),
                    )
                    .order_by(Dataset.id)
                    .limit(1)
                )
                if dataset is None:
                    cursor = ""
                else:
                    delay = 0.1
                    cursor = dataset.id
                    await synchronize(service, dataset)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("enterprise.sync_unavailable")
        await asyncio.sleep(delay)
