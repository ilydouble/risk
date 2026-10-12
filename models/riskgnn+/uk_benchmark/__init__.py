"""UK Companies House / GLEIF benchmark bridge for the RiskGNN+ comparison.

The snapshot lives in ``datasets/uk_dataset_v1`` and is read-only here. Keep this
module import-light: :mod:`uk_benchmark.data` is numpy-only so the loader contract
can be tested without torch-geometric; :mod:`uk_benchmark.training` owns the torch
side and is imported explicitly by the top-level script.
"""
