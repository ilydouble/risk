# RiskGNN

Enterprise credit-risk / bankruptcy-prediction model, extended from the ComRisk
paper's original code (see citation below) for Topic 18. Built and validated on
two datasets: the original SMEsD (China SMEs) and a Singapore ACRA/GLEIF export
(2.1M companies), the latter used as a large-scale stand-in for the competition's
real Southeast Asian data until it is released.

## Original work

This repository is extended from the paper "Combining intra-risk and contagion
risk for enterprise bankruptcy prediction using graph neural networks"
([paper](https://www.sciencedirect.com/science/article/abs/pii/S0020025523016675)).

    @article{wei2024combining,
      title={Combining Intra-Risk and Contagion Risk for Enterprise Bankruptcy Prediction Using Graph Neural Networks},
      author={Wei, Shaopeng and Lv, Jia and Guo, Yu and Yang, Qing and Chen, Xingyan and Zhao, Yu and Li, Qing and Zhuang, Fuzhen and Kou, Gang},
      journal={Information Sciences},
      pages={120081},
      year={2024},
      issn = {0020-0255},
      doi = {https://doi.org/10.1016/j.ins.2023.120081},
      publisher={Elsevier}
    }

## What's been added on top of the original code

- **Bayesian-smoothed community (region/industry) risk prior**, fit on training
  data only, with a leave-one-out correction (`fit_bayesian_group_prior` /
  `build_group_prior_feature_loo` in `utils.py`) — the naive version leaks the
  label for single-company groups, which this fixes.
- **Vectorized hypergraph Laplacian** (`hyper_laplacian`, `HyperGNNVectorized` in
  `gnn.py`) — the original scipy-sparse implementation OOMs above ~50k companies;
  this scales to millions of nodes (`RiskGNN(..., hyper_impl='vectorized')`).
- **GPU support** — the original code was CPU-only throughout; `RiskGNN` and its
  submodules now respect the `device` they're constructed with.
- **A custom mini-batch / neighbor-sampling training path**
  (`RiskGNN.forward_batch`, `train_sg_neighbor.py`) for the edge-graph (HeteGNN)
  component at full scale, where full-batch training runs out of memory
  (activation memory across 5 stacked layers, not raw data size).
- **Ablations to isolate which component carries predictive signal**
  (`train_sg_ablation.py`: node-only vs. +hypergraph; `train_sg_neighbor.py`:
  node-only vs. +edge-graph, via mini-batching), plus AUC/KS/AP reporting
  throughout. The full node+hypergraph+edge-graph combination has not been run
  end-to-end — it's both slow (~141s/epoch full-batch on CPU) and OOMs on a
  16GB GPU; the two ablations above were run separately instead.

## Setup

    pip install -r requirements.txt

Developed against Python 3.13, PyTorch 2.7.1 (CPU or CUDA), torch-geometric 2.8.0.

## Data

- **SMEsD** (`data/`, gitignored): fetch from the original
  [ComRisk repo](https://github.com/shaopengw/ComRisk) (`data/*.pkl`).
- **Singapore ACRA/GLEIF export** (`data_sg_v5/comrisk_export/`, gitignored,
  ~150MB): a partner-provided parquet export, not redistributed here. See
  `SMEsD.md` for the SMEsD schema; the Singapore export's schema/loader is
  `data_sg_v5/comrisk_export/load_comrisk.py`.

## Running it

    python train.py                          # original SMEsD baseline (community prior, LOO-corrected)
    python train_protocol_a.py                # RiskGNN vs. logistic-regression reference, frozen SG splits
    python train_sg_ablation.py --ablation node_hyper --n_epoch 30 --seed 0   # full-batch, node/hypergraph ablations
    python train_sg_neighbor.py --variant node_edge --n_epoch 10 --seed 0     # mini-batch edge-graph, full 2.1M-node scale

`data/meta_emb.pkl` already ships pretrained metapath2vec embeddings for
`train.py`'s SMEsD run. To regenerate them yourself, run `python
metapath2vec.py` — first substitute PyG's own `SparseTensor.sample`/`sample_adj`
with the patched versions in `sample.py` (this repo's copy fixes a zero-degree
edge case the upstream version doesn't handle); the Singapore-data scripts don't
need this, they initialize embeddings randomly since no pretrained ones exist
for that graph.

`run_*.py` scripts are batch drivers that sweep seeds/ablations and write a
results table; each wraps its per-run subprocess in try/except so one failed
run doesn't kill the batch.

## Known limitations (read before citing a number from this repo)

- **Hypergraph adds no measured value on the Singapore data**: node-only vs.
  node+hypergraph ablation gave ROC-AUC 0.8040±0.0033 vs. 0.8042±0.0055 —
  statistically indistinguishable. The industry/area/qualify groupings are
  derived from features already in the node attributes, so this isn't
  surprising in hindsight.
- **Edge-graph (SAME_ADDRESS/EQUITY_*) shows an early positive signal**
  (node_edge single-seed ROC in the 0.815–0.84 range vs. node_only's 0.80–0.83,
  across several exploratory runs at different batch sizes) but a proper
  multi-seed comparison is still in progress as of this writing, and this is
  being validated on data with a **known construction bug** in the upstream
  address-truncation logic (large address groups are truncated non-randomly,
  contaminating ~91% of edges) — treat any edge-graph number here as
  preliminary until (a) the multi-seed run finishes and (b) it's re-run on a
  corrected export. See `results_sg_neighbor.txt` (gitignored, local only) for
  the raw per-seed numbers.
- **The `officers` feature and the label itself carry a size/selection
  artifact**: ~70% of the Singapore dataset is excluded from labeling
  entirely (administrative closures), so the label captures only *formal*
  insolvency, and `officers` acts as a company-size proxy for which exit route
  gets recorded rather than a real risk signal. Report the no-`officers`
  variant as an artifact-free lower bound alongside any headline number.
- Edge weights (address-trust score, GLEIF ownership %) are currently forced to
  a uniform 1.0 in `HeteGNN` — its fixed-shape per-relation `Linear` layer
  breaks on real non-uniform weights on new edge types. Not yet fixed.
- All Singapore-data numbers are a **methodology stand-in**, not a Southeast
  Asian competition result — re-validate once the real multi-country data
  arrives.
- **Licensing**: this builds on the original ComRisk paper's code (see citation
  above); redistribution terms for the upstream code/data have not been
  independently verified. Keeping the citation/provenance here does not imply
  re-authorization.
