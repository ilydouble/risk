"""Durable queue worker; execution is delegated to a disposable networkless container."""

import asyncio
import base64
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update

from risk_api.errors import AppError
from risk_api.modules.auth import model as auth_model  # noqa: F401
from risk_api.modules.data_prep.model import ScriptPreparation, ScriptPreparationRun
from risk_api.modules.data_prep.script_service import input_files, runner_call, sha
from risk_api.modules.modeling import workbench_model as workbench_model  # noqa: F401
from risk_api.shared.db import session_factory

logger = logging.getLogger(__name__)


async def work_once(sessions=session_factory, execute=runner_call) -> bool:
    async with sessions() as session:
        now = datetime.now(UTC)
        await session.execute(update(ScriptPreparationRun).where(
            ScriptPreparationRun.status == "running",
            ScriptPreparationRun.started_at < now - timedelta(minutes=5),
        ).values(status="failed", error="执行中断或超过运行期限，请重新运行", finished_at=now))
        run = await session.scalar(select(ScriptPreparationRun).where(
            ScriptPreparationRun.status == "queued",
        ).order_by(ScriptPreparationRun.created_at).with_for_update(skip_locked=True).limit(1))
        if run is None:
            await session.commit()
            return False
        task = await session.get(ScriptPreparation, run.task_id)
        if task is None or sha(task.source) != run.specification["sourceSha256"]:
            run.status, run.error, run.finished_at = "failed", "原始文件摘要异常", now
            await session.commit()
            return True
        run.status, run.started_at = "running", now
        body = {**run.specification, "files": input_files(task), "script": run.script,
                "scriptSha256": run.script_sha, "revision": run.revision}
        identity = run.id
        await session.commit()
    try:
        result = await execute("run", body)
        artifact = base64.b64decode(result.pop("artifactBase64", ""), validate=True) or None
        artifact_sha = result.pop("artifactSha256", None)
        ready = (result.get("status") == "ready" and artifact
                 and len(artifact) <= 64 * 1024**2 and sha(artifact) == artifact_sha)
        if result.get("status") == "ready" and not ready:
            raise ValueError("Invalid executor artifact")
    except Exception as error:
        result = {"status": "failed", "log": "", "error": (
            error.message if isinstance(error, AppError) else "执行器返回异常，请重新运行"
        )}
        artifact, artifact_sha, ready = None, None, False
    async with sessions() as session:
        current = await session.get(ScriptPreparationRun, identity, with_for_update=True)
        if current is not None and current.status == "running":
            current.status = "ready" if ready else "failed"
            current.log = result.pop("log", "")[-32000:]
            current.error = result.pop("error", "")[:2000]
            current.result = result
            current.artifact = artifact if ready else None
            current.artifact_sha = artifact_sha if ready else None
            current.finished_at = datetime.now(UTC)
            await session.commit()
    return True


async def main():
    while True:
        try:
            active = await work_once()
        except Exception:
            logger.exception("preparation.worker_failed")
            active = False
        if not active:
            await asyncio.sleep(2)


if __name__ == "__main__":
    asyncio.run(main())
