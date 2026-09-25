"""The committed test snapshot and selected weights work without train/valid data."""

import asyncio
import hashlib
import json
import shutil
from pathlib import Path

from risk_api.modules.benchmark.service import BenchmarkService

ROOT = Path(__file__).resolve().parents[2]


def test_shared_bundle_checksums_and_portable_inference(tmp_path: Path) -> None:
    manifest = json.loads((ROOT / "backend/docs/demo-bundle-manifest.json").read_text())
    assert manifest["company_count"] == 474
    for entry in manifest["files"]:
        relative = Path(entry["path"])
        assert relative.parts[0] == "backend" and ".." not in relative.parts
        content = (ROOT / relative).read_bytes()
        assert len(content) == entry["bytes"]
        assert hashlib.sha256(content).hexdigest() == entry["sha256"]
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, destination)
    backend = tmp_path / "backend"
    assert not (backend / "data/processed/smesd/train.json").exists()
    assert not (backend / "data/processed/smesd/valid.json").exists()
    (backend / "docs").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(
        ROOT / "backend/docs/demo-bundle-manifest.json",
        backend / "docs/demo-bundle-manifest.json",
    )
    service = BenchmarkService(
        root=backend,
        data_path=backend / "data/processed/smesd/test.json",
        model_dir=backend / "artifacts/smesd-v1/no_hyper-seed42",
    )

    async def verify() -> None:
        try:
            await service.start()
            assert service.search("", 1, 20)[1] == 474
            score = service.predict(["C00010"])[0]["riskProbability"]
            assert abs(score - 0.7268730401992798) < 1e-6
            assert service.graph("C00010", 30)["totalEdges"] == 16
            assert (
                abs(service.evaluation()["metrics"]["test"]["roc_auc"] - 0.793637480738848) < 1e-10
            )
        finally:
            service.close()

    asyncio.run(verify())
