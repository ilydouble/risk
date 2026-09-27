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
- **Ranking and calibration metrics** (`capture_at_frac`, `lift_at_frac`,
  `brier_score`, `brier_skill_score`, `calibration_curve` in
  `train_sg_neighbor.py`) plus `--dump_preds`, which saves the test- and
  validation-fold log-probabilities so the metrics can be recomputed offline by
  `compute_metrics.py` without retraining. Note `Classifier.forward` returns
  *log*-softmax output, so anything needing real probabilities (Brier,
  calibration curve) must `exp()` it first — ROC/KS/AP are rank-based and so are
  unaffected, which makes this easy to get silently wrong.
- **A relation-count-agnostic `HeteGNN`**: the per-relation `Linear` input width
  now follows a `use_scalar_weights` flag instead of a hardcoded relation index
  (`if i in [6,7,8,9]`). That old check only worked while a graph had ≤6 relation
  types; at 7+ one relation silently got the wrong width and training failed with
  `mat1 and mat2 shapes cannot be multiplied`. Relevant whenever the relation
  count grows (the upstream loader caps it at 12).
- **A smaller memory footprint at 2.1M nodes**: the CSR index tables are int32 and
  the sampler accumulates into `array.array` buffers instead of Python lists,
  which cuts peak RAM by roughly 1.5 GB with **bit-identical** output (verified by
  re-running and diffing ROC/KS/AP).

## Setup

    pip install -r requirements.txt

Developed against Python 3.13, PyTorch 2.7.1 (CPU or CUDA), torch-geometric 2.8.0.

## Data

- **SMEsD** (`data/`, gitignored): fetch from the original
  [ComRisk repo](https://github.com/shaopengw/ComRisk) (`data/*.pkl`).
- **Singapore ACRA/GLEIF export** (`data_sg_v7/comrisk_export/`, gitignored,
  ~150MB per version): a partner-provided parquet export, not redistributed here.
  See `SMEsD.md` for the SMEsD schema; the Singapore export's schema/loader is
  `data_sg_v7/comrisk_export/load_comrisk.py`.

## Running it

    python train.py                          # original SMEsD baseline (community prior, LOO-corrected)
    python train_protocol_a.py                # RiskGNN vs. logistic-regression reference, frozen SG splits
    python train_sg_ablation.py --ablation node_hyper --n_epoch 30 --seed 0   # full-batch, node/hypergraph ablations
    python train_sg_neighbor.py --variant node_edge --n_epoch 10 --seed 0     # mini-batch edge-graph, full 2.1M-node scale
    python train_sg_neighbor.py --variant node_edge --edges_file <edges.parquet> \
        --dump_preds preds/node_edge_seed0.npz                                # save test+val predictions
    python compute_metrics.py                # ranking + calibration + BSS from preds/*.npz
    python run_metrics_batch.py              # the 4-variant x 3-seed batch behind the numbers below

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
- **Edge-graph (SAME_ADDRESS/EQUITY_*) is a real, reproducible gain.** The
  multi-seed comparison is finished, and it was re-run on the corrected export
  (the v2 build's address-truncation bug is fixed upstream). Three seeds, 6-dim
  `no_priors`, 10 epochs, batch 2048, fanout 10, 5 hops, GPU:

  | variant | ROC | KS | AP | Capture@5% | Lift@10% | Brier raw | BSS recal. |
  |---|---|---|---|---|---|---|---|
  | `node_only` | 0.8224 ± 0.0051 | 0.5325 | 0.0689 | 0.253 | 3.70 | 0.177 | 0.030 |
  | `node_edge` | 0.8578 ± 0.0025 | 0.5695 | 0.1604 | 0.287 | 4.65 | 0.135 | 0.047 |
  | `node_edge` − liquidation addrs | **0.8745 ± 0.0035** | 0.5885 | **0.2680** | **0.367** | **5.29** | 0.133 | **0.065** |
  | `node_edge` + `edges_by_addr_type` | 0.8522 | — | — | 0.281 | 4.51 | 0.158 | 0.043 |

  **Δ ROC +0.0354** (+0.0521 with the 30 liquidation addresses removed), ranges
  fully non-overlapping. Re-running the whole batch reproduced the earlier
  ROC/KS/AP **exactly** on all 9 comparable runs — zero drift. Splitting
  SAME_ADDRESS by address type does **not** help: it is worse on every metric and
  more seed-variable. Capture@5% is the one target not met (0.367 against a 0.50
  goal, where 0.05 is the random baseline).
- **Do not cite "Brier ≤ 0.10" as a pass.** At a 2.1% positive rate a constant
  predictor already scores p(1−p) = 0.0206, so that threshold carries no
  information — it was written for a balanced dataset. Quote the Brier Skill
  Score instead: the raw model is **6.5–8.6× worse** than a constant (which is
  what `--use_class_weight`, w1/w0 ≈ 46.6×, costs in probability terms), and the
  Platt-recalibrated model is only **0.030–0.065** — i.e. 3–7% better than doing
  nothing. `compute_metrics.py` prints BSS next to Brier for this reason.
- **The `officers` feature and the label itself carry a size/selection
  artifact**: ~70% of the Singapore dataset is excluded from labeling
  entirely (administrative closures), so the label captures only *formal*
  insolvency, and `officers` acts as a company-size proxy for which exit route
  gets recorded rather than a real risk signal. Report the no-`officers`
  variant as an artifact-free lower bound alongside any headline number. A
  leave-one-out neighbour-mean ablation on the same splits (run independently by
  a collaborator) found that the edge gain **does survive removing own
  `officers`**, but that **~91% of that gain comes from the neighbour-`officers`
  term** (`officers` spatial autocorrelation ICC ≈ 21%). So on this dataset the
  graph's contribution is heavily entangled with the label-construction artifact —
  do **not** claim it captures relational risk here.
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
