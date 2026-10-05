"""Frozen copy of the historical RiskGNN base used only by this experiment.

Source (read-only upstream snapshot, do not sync automatically):

- `models/riskgnn/gnn.py`   sha256 aa182a02c20cc8ea217375c10ddb5bbdaab0f8a5f71468aa702264bef5df3765
- `models/riskgnn/utils.py` sha256 82e6023172ef7a1f2ddadd8e7747cd3b97cfcdbcbe8c0cb617017f19ca1d8f58

These two files are vendored so the experiment has an explicit, self-contained
import boundary instead of mutating `sys.path` to reach the sibling
`models/riskgnn` directory. Only the intra-package import in `gnn.py`
(`from utils import *` -> `from .utils import *`) differs from the source.
Refresh the copy deliberately, then update these hashes.
"""
