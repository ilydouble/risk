from pathlib import Path

import pytest
from com_risk_runtime.artifacts import ARTIFACT_FILES, validate_bundle

from risk_api.shared.config import settings


def pytest_addoption(parser):
    parser.addoption(
        "--require-model", action="store_true", help="fail if model artifacts are absent"
    )


def pytest_configure(config):
    config.addinivalue_line("markers", "model_integration: requires the downloaded model bundle")


def pytest_sessionstart(session):
    if session.config.getoption("--require-model"):
        try:
            validate_bundle(
                Path(settings.benchmark_model_dir),
                Path(settings.benchmark_data_path),
                expected_version=settings.benchmark_model_version,
            )
        except (OSError, ValueError, KeyError) as exc:
            raise pytest.UsageError(f"--require-model: invalid or missing model: {exc}") from exc


@pytest.fixture(scope="session")
def real_model():
    model = Path(settings.benchmark_model_dir)
    if not any((model / name).exists() for name in (*ARTIFACT_FILES, "manifest.json")):
        pytest.skip("download a Release bundle to weights/; acceptance must use --require-model")
    data = Path(settings.benchmark_data_path)
    validate_bundle(model, data, expected_version=settings.benchmark_model_version)
    return model, data
