"""Trusted entrypoint of the disposable preparation container, never an API server."""

import base64
import hashlib
import json
import os
import resource
import signal
import subprocess
import sys
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from riskgnn.dataset_adapters.archive import check_archive
from riskgnn.dataset_adapters.contract import CONTRACT_NAME, validate_contract
from riskgnn.dataset_adapters.delivery import catalog, preset_details, relative_file
from riskgnn.dataset_adapters.packaging import source_files


def definitions():
    result = []
    for definition in catalog():
        for name in definition.presets:
            item = preset_details(name)
            item.pop("definition", None)
            item["guide"] = (definition.path.parent / "README.md").read_text()[:16000]
            item["inputSchemaCode"] = "\n".join(
                f"# {name}\n" + (definition.path.parent / name).read_text()[:18000]
                for name in ("schemas.py", "validation.py", "adapter.py")
                if (definition.path.parent / name).exists()
            )[:40000]
            item["inputSchemaCode"] += "\n# snapshot_schema.py\n" + (
                definition.path.parent.parent / "snapshot_schema.py").read_text()
            item["inputSchemaCode"] += "\n# snapshot_io.py\n" + (
                definition.path.parent.parent / "snapshot_io.py").read_text()
            result.append(item)
    return result


def demote():
    os.setgroups([])
    os.setgid(65534)
    os.setuid(65534)
    resource.setrlimit(resource.RLIMIT_FSIZE, (64 * 1024**2, 64 * 1024**2))
    resource.setrlimit(resource.RLIMIT_CPU, (60, 60))
    resource.setrlimit(resource.RLIMIT_NOFILE, (128, 128))


def run(body):
    root = Path("/work")
    inputs, output = root / "input", root / "output"
    inputs.mkdir(mode=0o755)
    output.mkdir()
    output.chmod(0o777)
    for file in body["files"]:
        path = inputs / relative_file(file["filename"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(base64.b64decode(file["contentBase64"], validate=True))
        path.chmod(0o444)
    for folder in inputs.rglob("*"):
        if folder.is_dir():
            folder.chmod(0o555)
    inputs.chmod(0o555)
    script = root / "convert.py"
    script.write_text(body["script"])
    script.chmod(0o444)
    env = {"PATH": "/opt/venv/bin:/usr/local/bin:/usr/bin:/bin", "HOME": "/tmp",
           "PYTHONPATH": "/app/models", "INPUT_DIR": str(inputs), "OUTPUT_DIR": str(output),
           "PYTHONDONTWRITEBYTECODE": "1", "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1"}
    logfile = root / "script.log"
    with logfile.open("wb") as logs:
        process = subprocess.Popen([sys.executable, "-u", str(script)], cwd=output, env=env,
                                   stdout=logs, stderr=logs, preexec_fn=demote,
                                   start_new_session=True)
        timed_out = False
        try:
            process.wait(timeout=65)
        except subprocess.TimeoutExpired:
            timed_out = True
        finally:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
    with logfile.open("rb") as logs:
        logs.seek(max(0, logfile.stat().st_size - 16000))
        log = logs.read().decode("utf-8", errors="replace")
    result = {"status": "failed", "log": log, "exitCode": process.returncode,
              "validation": {}, "files": [], "error": ""}
    if timed_out or process.returncode:
        result["error"] = "脚本执行超过65秒" if timed_out else "脚本执行失败，请根据日志修复"
        return result
    try:
        details = preset_details(body["preset"])
        files = source_files(output)
        if (output / "_preparation").exists():
            raise ValueError("_preparation is reserved for execution provenance")
        required = details["requiredFiles"]
        missing = [name for name in required if not (output / name).is_file()]
        if missing:
            raise ValueError("Missing required output files: " + ", ".join(missing))
        if sum(path.stat().st_size for path in files) > 128 * 1024**2:
            raise ValueError("Outputs exceed 128 MiB; reduce the conversion scope")
        contract = {"contract_version": 1,
                    "dataset": {"id": body["datasetKey"], "name": body["name"],
                                "version": f"{body['datasetVersion']}-r{body['revision']}"},
                    "adapter": {**details["adapter"], "config": details["config"]}}
        validate_contract(contract)
        archive_path = root / "dataset.zip"
        manifest = {key: body[key] for key in ("sourceSha256", "scriptSha256", "revision",
                                              "datasetKey", "datasetVersion", "runtimeImage")}
        manifest["artifactDatasetVersion"] = contract["dataset"]["version"]
        with ZipFile(archive_path, "w", ZIP_DEFLATED) as archive:
            for path in files:
                archive.write(path, path.relative_to(output).as_posix())
            archive.writestr(CONTRACT_NAME, json.dumps(contract, ensure_ascii=False))
            archive.writestr("_preparation/convert.py", body["script"])
            archive.writestr("_preparation/execution.json", json.dumps(manifest))
        check_archive(archive_path)
        if archive_path.stat().st_size > 64 * 1024**2:
            raise ValueError("ZIP exceeds the preparation artifact limit of 64 MiB")
        # Validation runs in another bounded process; uploaded Python is never imported.
        report = root / "validation.json"
        validation = subprocess.run(
            [sys.executable, "-m", "riskgnn.dataset_adapters.validate_package", "--input",
             str(archive_path), "--report", str(report)], cwd="/app/models", env=env,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=100,
        )
        if validation.returncode:
            result["log"] += "\n" + validation.stdout.decode(errors="replace")[-12000:]
            raise ValueError("模型适配器全量校验失败，请根据校验日志修复脚本")
        checked = json.loads(report.read_text())
        if checked.get("compatibility") != "compatible" or checked.get("issues"):
            result["validation"] = checked
            raise ValueError("数据集未通过训练兼容性校验")
        content = archive_path.read_bytes()
        with ZipFile(archive_path) as archive:
            result["files"] = [{"path": item.filename, "size": item.file_size}
                               for item in archive.infolist() if not item.is_dir()]
        result.update(status="ready", error="", validation=checked,
                      datasetVersion=contract["dataset"]["version"],
                      artifactBase64=base64.b64encode(content).decode(),
                      artifactSha256=hashlib.sha256(content).hexdigest())
    except Exception as error:
        result["error"] = str(error)[:2000]
    return result


if __name__ == "__main__":
    if "--catalog" in sys.argv:
        print(json.dumps({"items": definitions()}, ensure_ascii=False))
    else:
        try:
            result = run(json.load(sys.stdin))
        except Exception as error:
            result = {"status": "failed", "error": str(error)[:2000], "log": "",
                      "exitCode": None, "validation": {}, "files": []}
        print(json.dumps(result, ensure_ascii=False))
