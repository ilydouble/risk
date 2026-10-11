import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from riskgnn.dataset_adapters import package_dataset
from riskgnn.dataset_adapters.contract import read_contract

REPO = Path(__file__).resolve().parents[3]
LAUNCHER = REPO / "scripts" / "package-dataset"


def test_default_output_summary_json_and_no_overwrite(datasets, tmp_path, monkeypatch, capsys):
    assert package_dataset.default_output("smesd", "v5") == (
        REPO / "models/runs/datasets/smesd-v5.zip"
    )
    monkeypatch.setattr(package_dataset, "DEFAULT_OUTPUT_DIRECTORY", tmp_path)
    arguments = [
        "--preset",
        "smesd",
        "--data-dir",
        str(datasets / "comrisk_export_v5/smesd"),
        "--dataset-version",
        "v5",
        "--set",
        "target_count=60",
    ]
    package_dataset.main(arguments)
    output = capsys.readouterr().out
    assert "打包完成" in output
    assert "smesd / 1" in output
    assert "完整数据校验将在上传后执行" in output
    assert "进入模型工作台 → 数据集 → 上传并校验" in output
    archive = tmp_path / "smesd-v5.zip"
    assert str(archive) in output
    contract, _ = read_contract(archive)
    assert contract["dataset"]["version"] == "v5"
    assert contract["adapter"]["config"] == {"target_count": 60}
    before = archive.read_bytes()
    with pytest.raises(SystemExit) as error:
        package_dataset.main(arguments)
    assert error.value.code == 2
    assert "--output" in capsys.readouterr().err
    assert archive.read_bytes() == before

    package_dataset.main([*arguments, "--output", str(tmp_path / "explicit.zip"), "--json"])
    summary = json.loads(capsys.readouterr().out)
    assert summary["validation"] == "packaging-only"
    assert summary["contract"] == contract
    assert summary["overrides"] == {"target_count": 60}


@pytest.mark.parametrize("version", ["../escape", "release/v5", "v5\\escape", ""])
def test_default_filename_cannot_escape_output_directory(version):
    with pytest.raises(ValueError, match="--output"):
        package_dataset.default_output("smesd", version)


def test_cli_presets_are_readable_and_json_remains_available(capsys):
    package_dataset.main(["--list-presets"])
    text = capsys.readouterr().out
    for name in ("acra-companies", "smesd", "uk-companies"):
        assert f"预设：{name}" in text
    package_dataset.main(["--show-preset", "smesd", "--json"])
    details = json.loads(capsys.readouterr().out)
    assert details["userSupplied"] == ["data-dir", "dataset-version"]
    assert details["adapter"] == {"id": "smesd", "version": "1"}


def test_launcher_preserves_relative_paths_and_exit_status(datasets, tmp_path):
    working = tmp_path / "caller with spaces"
    working.mkdir()
    shutil.copytree(datasets / "comrisk_export_v5/smesd", working / "source data")
    binaries = tmp_path / "bin"
    binaries.mkdir()
    # Exercise the real launcher/CLI without installing dependencies or accessing the network.
    # A separate manual smoke check uses uv's actual lightweight environment.
    uv = binaries / "uv"
    uv.write_text(
        '#!/bin/sh\nwhile [ "$1" != python ]; do shift; done\nshift\n'
        f'exec {shlex.quote(sys.executable)} "$@"\n'
    )
    uv.chmod(0o755)
    arguments = [
        str(LAUNCHER),
        "--preset",
        "smesd",
        "--data-dir",
        "source data",
        "--dataset-version",
        "release/v5",
        "--output",
        "deliveries/model data.zip",
        "--json",
    ]
    env = {**os.environ, "PATH": f"{binaries}{os.pathsep}{os.environ['PATH']}"}
    result = subprocess.run(arguments, cwd=working, env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    summary = json.loads(result.stdout)
    assert summary["dataDir"] == str(working / "source data")
    assert summary["output"] == str(working / "deliveries/model data.zip")
    contract, _ = read_contract(Path(summary["output"]))
    assert contract["dataset"]["version"] == "release/v5"
    again = subprocess.run(arguments, cwd=working, env=env, capture_output=True, text=True)
    assert again.returncode == 2
    assert "Output already exists" in again.stderr


def test_launcher_explains_missing_uv(tmp_path):
    result = subprocess.run(
        ["/bin/bash", str(LAUNCHER), "--help"],
        env={**os.environ, "PATH": str(tmp_path)},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 127
    assert "未找到 uv" in result.stderr
