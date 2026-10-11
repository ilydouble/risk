"""Research imports remain usable without any workbench dependencies."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np


def test_research_does_not_import_service_dependencies():
    root = Path(__file__).resolve().parents[2] / "riskgnn"
    code = """
import importlib.abc
import sys
class ResearchOnly(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        blocked = {'service', 'model_service', 'fastapi', 'sqlalchemy', 'dishka', 'asyncpg'}
        if fullname.split('.')[0] in blocked:
            raise ImportError('Research cannot depend on service: ' + fullname)
sys.meta_path.insert(0, ResearchOnly())
import gnn
import train_sg_neighbor
assert gnn.RiskGNN is not None
train_sg_neighbor.main()
"""
    result = subprocess.run(
        [sys.executable, "-c", code, "--help"], cwd=root, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
    assert "--device" in result.stdout and "--data_dir" in result.stdout


def test_original_research_cli_predictions(export_zip, tmp_path):
    root = Path(__file__).resolve().parents[2] / "riskgnn"
    fixtures = Path(__file__).parent / "fixtures"
    trusted = tmp_path / "research-input"
    shutil.copytree(tmp_path / "source", trusted)
    # This repository-owned loader is explicitly used for the original research CLI.
    # Uploaded attachments are never used as Python code.
    shutil.copy2(fixtures / "research_loader.py", trusted / "load_comrisk.py")
    output = tmp_path / "predictions.npz"
    arguments = [
        sys.executable,
        str(root / "train_sg_neighbor.py"),
        "--variant",
        "node_edge",
        "--n_epoch",
        "1",
        "--seed",
        "0",
        "--input_dim",
        "32",
        "--output_dim",
        "32",
        "--batch_size",
        "64",
        "--eval_batch_size",
        "64",
        "--fanout",
        "2",
        "--eval_every",
        "1",
        "--device",
        "cpu",
        "--num_workers",
        "1",
        "--data_dir",
        str(trusted),
        "--dump_preds",
        str(output),
    ]
    result = subprocess.run(
        arguments,
        cwd=root,
        capture_output=True,
        text=True,
        env={**os.environ, "OMP_NUM_THREADS": "2", "MKL_NUM_THREADS": "2"},
    )
    assert result.returncode == 0, result.stderr
    expected = json.loads((fixtures / "research-neighbor-predictions.json").read_text())["arrays"]
    with np.load(output) as actual:
        assert set(actual) == set(expected)
        for key, values in expected.items():
            assert np.allclose(actual[key], values, rtol=0, atol=1e-7), key
