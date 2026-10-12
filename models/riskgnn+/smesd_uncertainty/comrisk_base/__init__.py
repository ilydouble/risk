"""Frozen copy of the historical RiskGNN base used only by this experiment.

Source (read-only upstream snapshot, do not sync automatically):

- `models/riskgnn/gnn.py`   sha256 21b8a09c18ed6ce69308acd07ce66855068b8957e3b242a06205b716e10db852
- `models/riskgnn/utils.py` sha256 82e6023172ef7a1f2ddadd8e7747cd3b97cfcdbcbe8c0cb617017f19ca1d8f58

Vendored copies in this directory:

- `gnn.py`   sha256 bcf4605e120c48384eca8603d3cabff63ac087e4ba7b3046c6e217de3b2eef99
- `utils.py` sha256 82e6023172ef7a1f2ddadd8e7747cd3b97cfcdbcbe8c0cb617017f19ca1d8f58

These two files are vendored so the experiment has an explicit, self-contained
import boundary instead of mutating `sys.path` to reach the sibling
`models/riskgnn` directory. Two differences from the current source are
deliberate:

1. The intra-package import in `gnn.py` becomes `from .utils import *`.
2. `HeteGNN.message` was refreshed to upstream's flag-based
   `use_scalar_weights` branch (upstream added it after this snapshot was taken).
   UK edges mix non-uniform `SAME_ADDRESS` weights with uniform relations, which
   the old data-driven branch mishandled. The upstream person-node partitioning in
   `RiskGNN.forward` is intentionally *not* ported: both SMEsD and UK run with
   `person_num=0`, so it is unreachable here.

Refresh the copy deliberately, then update these hashes.
"""
