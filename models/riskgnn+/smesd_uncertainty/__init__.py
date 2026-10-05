"""SMEsD edge-confidence uncertainty experiment.

Implementation modules are imported explicitly by the thin CLI wrappers one
directory up (`simulate_smesd_uncertainty.py`, `train_smesd_uncertainty.py`,
`pretrain_smesd_metapath2vec.py`, `run_uncertainty_matrix.py`,
`summarize_uncertainty_results.py`). Keep this module import-light: the training
path pulls in torch and torch-geometric, which the pure-data modules and tests
must not require.
"""
