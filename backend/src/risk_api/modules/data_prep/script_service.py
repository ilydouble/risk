"""Persisted script workspaces; generated Python is only executed by the isolated runner."""

import ast
import base64
import hashlib
import io
import re
import zipfile
from datetime import UTC, datetime
from pathlib import PurePosixPath
from uuid import uuid4

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import defer

from risk_api.errors import AppError
from risk_api.modules.data_prep.model import ScriptPreparation, ScriptPreparationRun
from risk_api.shared.config import settings


def sha(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def check_script(code: str) -> None:
    if not code.strip() or len(code) > 100000:
        raise AppError(422, "DATA_PREP_SCRIPT_INVALID", "脚本不能为空，最多100000字符")
    try:
        ast.parse(code)
    except SyntaxError as error:
        raise AppError(422, "DATA_PREP_SCRIPT_INVALID",
                       f"Python语法错误，第{error.lineno}行：{error.msg}") from error


def pack_inputs(files: list[tuple[str, bytes]]) -> tuple[bytes, list[dict]]:
    if not 1 <= len(files) <= 16 or sum(len(data) for _, data in files) > 64 * 1024**2:
        raise AppError(422, "DATA_PREP_SIZE_INVALID", "最多16个文件，合计64 MiB")
    names: set[str] = set()
    metadata = []
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_STORED) as archive:
        for name, content in files:
            path = PurePosixPath(name)
            if (not name or len(name) > 255 or "\\" in name or ":" in name
                    or "\x00" in name or path.is_absolute() or path.as_posix() != name
                    or any(part in {".", "..", ""} for part in name.split("/"))
                    or name in names or not content):
                raise AppError(422, "DATA_PREP_CONTENT_INVALID", "文件名重复、路径无效或内容为空")
            if any(name.startswith(other + "/") or other.startswith(name + "/") for other in names):
                raise AppError(422, "DATA_PREP_CONTENT_INVALID", "文件路径与目录冲突")
            names.add(name)
            archive.writestr(name, content)
            metadata.append({"filename": name, "size": len(content), "sha256": sha(content)})
    return output.getvalue(), metadata


async def runner_call(action: str, body: dict) -> dict:
    try:
        async with httpx.AsyncClient(timeout=220, trust_env=False) as client:
            response = await client.post(
                settings.preparation_runner_url + "/" + action, json=body,
                headers={"Authorization": "Bearer " + settings.preparation_runner_token},
            )
            response.raise_for_status()
            return response.json()
    except (httpx.HTTPError, ValueError) as error:
        raise AppError(503, "DATA_PREP_RUNNER_UNAVAILABLE",
                       "脚本执行器暂不可用，请检查服务状态") from error


def input_files(task: ScriptPreparation) -> list[dict]:
    with zipfile.ZipFile(io.BytesIO(task.source)) as archive:
        return [{"filename": name, "contentBase64": base64.b64encode(archive.read(name)).decode()}
                for name in archive.namelist()]


def task_summary(task: ScriptPreparation) -> dict:
    return {"id": task.id, "name": task.name, "preset": task.preset,
            "revision": task.revision, "updatedAt": task.updated_at}


def run_summary(run: ScriptPreparationRun) -> dict:
    return {"id": run.id, "revision": run.revision, "script": run.script,
            "scriptSha256": run.script_sha, "status": run.status, "log": run.log,
            "error": run.error, "result": run.result, "artifactSha256": run.artifact_sha,
            "createdAt": run.created_at, "startedAt": run.started_at,
            "finishedAt": run.finished_at}


class ScriptPreparationService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, owner: str, identity: str, *, lock: bool = False) -> ScriptPreparation:
        query = select(ScriptPreparation).where(
            ScriptPreparation.id == identity, ScriptPreparation.owner_id == owner,
        )
        if lock:
            query = query.with_for_update()
        task = await self.session.scalar(query)
        if task is None:
            raise AppError(404, "DATA_PREP_TASK_NOT_FOUND", "数据准备任务不存在或无权访问")
        return task

    async def list_tasks(self, owner: str) -> list[dict]:
        items = await self.session.scalars(select(ScriptPreparation).options(
            defer(ScriptPreparation.source), defer(ScriptPreparation.messages),
            defer(ScriptPreparation.script),
        ).where(ScriptPreparation.owner_id == owner).order_by(
            ScriptPreparation.updated_at.desc(), ScriptPreparation.id,
        ).limit(100))
        return [task_summary(task) for task in items]

    async def create(self, owner: str, name: str, preset: str, dataset_key: str,
                     dataset_version: str, requirements: str,
                     files: list[tuple[str, bytes]]) -> ScriptPreparation:
        catalog = await runner_call("catalog", {})
        if preset not in {item["preset"] for item in catalog["items"]}:
            raise AppError(422, "DATA_PREP_SCRIPT_INVALID", "目标适配器预设不存在")
        source, metadata = pack_inputs(files)
        if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}", dataset_key):
            raise AppError(422, "DATA_PREP_SCRIPT_INVALID", "数据集标识格式无效")
        task = ScriptPreparation(id=str(uuid4()), owner_id=owner, name=name, preset=preset,
                                 dataset_key=dataset_key, dataset_version=dataset_version,
                                 source=source, source_sha=sha(source), files=metadata,
                                 requirements=requirements, script="", revision=1, messages=[])
        self.session.add(task)
        await self.session.commit()
        return task

    async def save(self, owner: str, identity: str, revision: int, code: str,
                   requirements: str, *, messages: list[dict] | None = None) -> ScriptPreparation:
        task = await self.get(owner, identity, lock=True)
        if task.revision != revision:
            raise AppError(409, "DATA_PREP_SCRIPT_STALE", "任务已被修改，请重新加载后保存")
        if code.strip():
            check_script(code)
        task.script, task.requirements = code, requirements
        task.revision += 1
        task.updated_at = datetime.now(UTC)
        if messages is not None:
            task.messages = messages[-40:]
        await self.session.commit()
        return task

    async def state(self, owner: str, identity: str) -> dict:
        task = await self.get(owner, identity)
        runs = list(await self.session.scalars(select(ScriptPreparationRun).options(
            defer(ScriptPreparationRun.artifact),
        ).where(ScriptPreparationRun.task_id == identity,
                ScriptPreparationRun.owner_id == owner).order_by(
                    ScriptPreparationRun.created_at.desc(), ScriptPreparationRun.id,
                ).limit(20)))
        return {**task_summary(task), "datasetKey": task.dataset_key,
                "datasetVersion": task.dataset_version, "sourceSha256": task.source_sha,
                "files": task.files, "requirements": task.requirements,
                "script": task.script, "messages": task.messages,
                "runs": [run_summary(run) for run in runs]}

    async def enqueue(self, owner: str, identity: str, revision: int) -> ScriptPreparationRun:
        task = await self.get(owner, identity, lock=True)
        if task.revision != revision:
            raise AppError(409, "DATA_PREP_SCRIPT_STALE", "请先保存当前脚本，再执行")
        check_script(task.script)
        active = await self.session.scalar(select(ScriptPreparationRun).where(
            ScriptPreparationRun.task_id == identity,
            ScriptPreparationRun.status.in_(["queued", "running"]),
        ))
        if active:
            if active.revision != revision:
                raise AppError(409, "DATA_PREP_SCRIPT_BUSY", "当前任务已有运行，请等待结束后重试")
            return active
        run = ScriptPreparationRun(
            id=str(uuid4()), owner_id=owner, task_id=identity, revision=revision,
            script=task.script, script_sha=sha(task.script.encode()),
            specification={"name": task.name, "preset": task.preset,
                           "datasetKey": task.dataset_key, "datasetVersion": task.dataset_version,
                           "requirements": task.requirements, "sourceSha256": task.source_sha},
            status="queued", log="", error="", result={}, artifact=None, artifact_sha=None,
        )
        self.session.add(run)
        await self.session.commit()
        return run

    async def owned_run(self, owner: str, identity: str, run_id: str,
                        *, lock: bool = False) -> ScriptPreparationRun:
        query = select(ScriptPreparationRun).where(ScriptPreparationRun.id == run_id,
            ScriptPreparationRun.task_id == identity, ScriptPreparationRun.owner_id == owner)
        if lock:
            query = query.with_for_update()
        run = await self.session.scalar(query)
        if run is None:
            raise AppError(404, "DATA_PREP_TASK_NOT_FOUND", "运行记录不存在或无权访问")
        return run

    async def artifact(self, owner: str, identity: str, run_id: str) -> dict:
        run = await self.owned_run(owner, identity, run_id)
        if run.status != "ready" or not run.artifact or sha(run.artifact) != run.artifact_sha:
            raise AppError(409, "DATA_PREP_SCRIPT_STALE", "运行没有有效数据包，请先完成执行与校验")
        return {"filename": f"dataset-{run.id}.zip",
                "contentBase64": base64.b64encode(run.artifact).decode()}
