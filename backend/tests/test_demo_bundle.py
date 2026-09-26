"""The API loads the selected package and an independently located snapshot."""

import asyncio
import shutil
from pathlib import Path

import pytest

from risk_api.modules.benchmark.service import BenchmarkService


@pytest.mark.model_integration
def test_portable_inference(real_model, tmp_path: Path) -> None:
    source_model, source_data = real_model
    model = tmp_path / "unrelated-layout/model"
    data = tmp_path / "snapshot.json"
    shutil.copytree(source_model, model)
    shutil.copyfile(source_data, data)
    service = BenchmarkService(data_path=data, model_dir=model)

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
