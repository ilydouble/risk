import json
import os
import shutil
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
import torch
from fixtures.real_datasets import acra_subset

from riskgnn.tools.package_dataset import package


def pytest_sessionstart(session):
    # Match the bounded CPU CLI when tests load a predictor in the parent process.
    torch.set_num_threads(2)


def pytest_addoption(parser):
    parser.addoption(
        "--require-datasets",
        action="store_true",
        help="Fail instead of skipping when the real dataset inputs are absent",
    )


@pytest.fixture(scope="session")
def datasets(request):
    root = Path(
        os.environ.get("RISK_DATASETS_ROOT", Path(__file__).resolve().parents[3] / "datasets")
    )
    required = [
        root / p
        for p in (
            "comrisk_export_v5/acra/company_attr.parquet",
            "comrisk_export_v5/smesd/train.json",
            "uk_dataset_v1/train.json",
        )
    ]
    if not all(path.is_file() for path in required):
        message = "Real datasets are required; set RISK_DATASETS_ROOT or populate datasets/"
        if request.config.getoption("--require-datasets"):
            pytest.fail(message)
        pytest.skip(message)
    return root


@pytest.fixture(scope="session")
def acra_source(datasets, tmp_path_factory):
    target = tmp_path_factory.mktemp("real-acra") / "source"
    acra_subset(datasets / "comrisk_export_v5/acra", target)
    return target


@pytest.fixture
def export_zip(acra_source, tmp_path):
    root = tmp_path / "source"
    shutil.copytree(acra_source, root)
    archive = tmp_path / "data.zip"
    package(root, archive, "acra-real-test-subset", "v5", "sg-comrisk")
    with ZipFile(archive) as zipped:
        contract = json.loads(zipped.read("risk_dataset_contract.json"))
    (root / "risk_dataset_contract.json").write_text(json.dumps(contract))
    # Exercise the supported optional single top-level directory too.
    with ZipFile(archive, "w", compression=ZIP_DEFLATED) as zipped:
        for path in root.iterdir():
            zipped.write(path, "comrisk_export/" + path.name)
    return archive
