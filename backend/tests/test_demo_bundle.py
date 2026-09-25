"""Ensure a fresh checkout can run using only the committed demonstration bundle."""

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_shared_bundle_checksums_and_portable_api(tmp_path):
    manifest = json.loads((ROOT / "backend/docs/demo-bundle-manifest.json").read_text())
    assert manifest["company_count"] == 474
    for entry in manifest["files"]:
        relative = Path(entry["path"])
        assert not relative.is_absolute() and ".." not in relative.parts
        source = ROOT / relative
        content = source.read_bytes()
        assert len(content) == entry["bytes"]
        assert hashlib.sha256(content).hexdigest() == entry["sha256"]
        if source.suffix == ".json":
            assert b"/Users/" not in content and b"/Volumes/" not in content
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
    shutil.copytree(
        ROOT / "backend/comrisk",
        tmp_path / "backend/comrisk",
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    (tmp_path / "backend/scripts").mkdir()
    shutil.copyfile(ROOT / "backend/scripts/serve.py", tmp_path / "backend/scripts/serve.py")
    assert not (tmp_path / "backend/data/processed/smesd/train.json").exists()
    assert not (tmp_path / "backend/data/processed/smesd/valid.json").exists()
    env = dict(os.environ)
    for key in ("COMRISK_MODEL_DIR", "COMRISK_DATA_PATH", "PYTHONPATH"):
        env.pop(key, None)
    env.update(OMP_NUM_THREADS="1", MKL_NUM_THREADS="1")
    script = """
import runpy
runpy.run_path('backend/scripts/serve.py', run_name='bundle_check')
from fastapi.testclient import TestClient
from comrisk.api import app
with TestClient(app) as client:
    assert client.get('/health').status_code == 200
    listing = client.get('/v1/companies').json()
    assert listing['total'] == 474
    detail = client.get('/v1/companies/C00010').json()
    prediction = client.post('/v1/predict', json={'company_ids':['C00010']}).json()
    prediction = prediction['predictions'][0]
    explanation = client.get('/v1/explain/C00010').json()
    assert detail['risk_probability'] == prediction['risk_probability']
    assert prediction['risk_probability'] == explanation['risk_probability']
    assert abs(detail['risk_probability'] - 0.7268730401992798) < 1e-6
    assert client.get('/v1/companies/C00010/graph').json()['total_edges'] == 16
    evaluation = client.get('/v1/evaluation').json()
    assert evaluation['metrics']['test']['n'] == 474
    assert abs(evaluation['metrics']['test']['roc_auc'] - 0.793637480738848) < 1e-10
    assert client.get('/v1/companies/unknown').status_code == 404
print('Portable demo bundle passed')
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=90,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Portable demo bundle passed" in result.stdout
