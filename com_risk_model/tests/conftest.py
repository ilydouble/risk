import os
from pathlib import Path

import pytest
from com_risk_runtime.artifacts import ARTIFACT_FILES, validate_bundle

from training.demo import generate
from training.pipeline import train

ROOT = Path(__file__).resolve().parents[1]
VERSION = os.getenv("BENCHMARK_MODEL_VERSION", "smesd-v1")
MODEL = Path(os.getenv("BENCHMARK_MODEL_DIR", str(ROOT / "weights" / VERSION)))
SNAPSHOT = Path(os.getenv("BENCHMARK_DATA_PATH", str(ROOT / "data/processed/smesd/test.json")))


def pytest_addoption(parser):
    parser.addoption(
        "--require-model", action="store_true", help="fail if model artifacts are absent"
    )


def pytest_configure(config):
    config.addinivalue_line("markers", "model_integration: requires the downloaded model bundle")


def pytest_sessionstart(session):
    if session.config.getoption("--require-model"):
        try:
            validate_bundle(MODEL, SNAPSHOT, expected_version=VERSION)
        except (OSError, ValueError, KeyError) as exc:
            raise pytest.UsageError(f"--require-model: invalid or missing model: {exc}") from exc


@pytest.fixture(scope="session")
def real_model():
    if not any((MODEL / name).exists() for name in (*ARTIFACT_FILES, "manifest.json")):
        pytest.skip("download a Release bundle to weights/; acceptance must use --require-model")
    return MODEL, validate_bundle(MODEL, SNAPSHOT, expected_version=VERSION)


@pytest.fixture(scope="session")
def trained(tmp_path_factory):
    path = tmp_path_factory.mktemp("model")
    d = generate(100)
    report = train(d, path, epochs=3, patience=2, hidden=8, pretrain_epochs=2)
    return path, d, report
