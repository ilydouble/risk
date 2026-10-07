"""Research imports remain usable without any workbench dependencies."""

import subprocess
import sys
from pathlib import Path


def test_research_does_not_import_service_dependencies():
    root = Path(__file__).resolve().parents[2] / "riskgnn"
    code = """
import importlib.abc
import sys
class ResearchOnly(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'service', 'fastapi', 'sqlalchemy', 'dishka', 'asyncpg'}:
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
