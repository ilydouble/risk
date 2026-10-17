"""Real Docker acceptance tests for the untrusted-script boundary (opt-in)."""

import base64
import importlib.util
import io
import json
import os
from pathlib import Path
from zipfile import ZipFile

import pytest

pytestmark = pytest.mark.skipif(
    os.getenv("RISK_TEST_PREPARATION_DOCKER") != "1",
    reason="requires isolated runtime Docker image",
)


def launcher():
    os.environ.setdefault("PREPARATION_RUNNER_TOKEN", "runtime-test-token")
    spec = importlib.util.spec_from_file_location(
        "preparation_runner", Path(__file__).parents[1] / "script_runner/server.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.launch


SCRIPT = '''import csv, json, os
from pathlib import Path
from riskgnn.dataset_adapters.smesd.schemas import FEATURES, RELATIONS, HYPEREDGES
inputs, outputs = Path(os.environ['INPUT_DIR']), Path(os.environ['OUTPUT_DIR'])
rows = list(csv.DictReader((inputs / 'source.csv').open()))
for split in ('train', 'valid', 'test'):
    nodes = [{'id': row['id'], 'kind': 'company', 'community': '',
              'features': [float(row['capital']), float(row['paid']), float(row['age'])],
              'label': int(row['label']), 'split': split} for row in rows if row['split'] == split]
    snapshot = {'schema_version': 1, 'name': split, 'synthetic': False,
                'evaluation': 'isolated_snapshots', 'target_description': 'test fixture status',
                'feature_names': FEATURES, 'relation_names': RELATIONS,
                'hyperedge_types': HYPEREDGES, 'nodes': nodes, 'edges': [],
                'hyperedges': [], 'events': []}
    (outputs / f'{split}.json').write_text(json.dumps(snapshot))
print('converted', len(rows), 'fixture companies')
'''
SOURCE = ("id,capital,paid,age,label,split\n"
          "001,1,1,12,0,train\n002,2,2,24,1,train\n"
          "003,1,1,12,0,valid\n004,2,2,24,1,valid\n"
          "005,1,1,12,0,test\n006,2,2,24,1,test\n")


def body(script):
    import hashlib
    return {"script": script, "files": [{"filename": "source.csv",
            "contentBase64": base64.b64encode(SOURCE.encode()).decode()}],
            "preset": "smesd", "name": "script test fixture", "datasetKey": "test-fixture",
            "datasetVersion": "v1", "revision": 1, "sourceSha256": "test-fixture-source",
            "scriptSha256": hashlib.sha256(script.encode()).hexdigest()}


def test_real_conversion_full_validation_and_reproducible_artifact():
    result = launcher()(body(SCRIPT))
    assert result["status"] == "ready", result
    assert result["validation"]["counts"]["company_attr"] == 6
    assert result["validation"]["compatibility"] == "compatible"
    assert "converted 6" in result["log"]
    with ZipFile(io.BytesIO(base64.b64decode(result["artifactBase64"]))) as archive:
        assert "_preparation/convert.py" in archive.namelist()
        contract = json.loads(archive.read("risk_dataset_contract.json"))
        assert contract["dataset"]["id"] == "test-fixture"
        assert contract["dataset"]["version"] == "v1-r1"
        assert json.loads(archive.read("train.json"))["nodes"][0]["id"] == "001"


def test_script_cannot_write_inputs_root_or_reach_network():
    script = '''import os, socket
from pathlib import Path
assert os.getuid() == 65534
for path in (Path(os.environ['INPUT_DIR']) / 'source.csv', Path('/app/models/escape')):
    try:
        path.write_text('overwrite')
    except OSError:
        print('write denied')
    else:
        raise AssertionError('write unexpectedly allowed')
try:
    socket.create_connection(('1.1.1.1', 443), timeout=1)
except OSError:
    print('network denied')
else:
    raise AssertionError('network unexpectedly allowed')
assert not any('TOKEN' in key or 'PASSWORD' in key for key in os.environ)
print('isolation verified')
'''
    result = launcher()(body(script))
    assert result["status"] == "failed"  # No dataset files were produced.
    assert result["log"].count("write denied") == 2
    assert "network denied" in result["log"] and "isolation verified" in result["log"]
    assert "artifactBase64" not in result


def test_script_failure_and_invalid_dataset_never_publish_an_artifact():
    launch = launcher()
    failed = launch(body("raise RuntimeError('controlled failure')"))
    assert failed["status"] == "failed" and "controlled failure" in failed["log"]
    invalid = launch(body("import os\nfrom pathlib import Path\n"
                          "for name in ('train', 'valid', 'test'):\n"
                          "    path = Path(os.environ['OUTPUT_DIR']) / (name + '.json')\n"
                          "    path.write_text('{}')"))
    assert invalid["status"] == "failed" and "校验失败" in invalid["error"]
    assert "artifactBase64" not in invalid


def test_timeout_terminates_script_without_publishing_an_artifact():
    result = launcher()(body("import time\ntime.sleep(70)"))
    assert result["status"] == "failed" and "65秒" in result["error"]
    assert "artifactBase64" not in result
