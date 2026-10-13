# ComRisk-family evidence II — labels, features, closed routes, scale

**Prepared 2026-10-05.** Companion script `verify_weakness_evidence.py` re-derives every `[measured]`
number below. Evidence tags and the edge-confidence channel are in
[evidence I](comrisk-confidence-channel-evidence.md).

---

## 1. The label is a registry proxy, not a credit outcome

- **Only 30.1 % of companies carry a usable label** — 634,646 of 2,111,884; `NaN` marks
  **administrative termination** and must be excluded. `[measured]`
- **Base rate 2.10 %** (13,328 positives). `[measured]`
- Consequence for reporting: with p = 0.021, **a constant predictor already scores
  Brier = p(1−p) = 0.0206**, i.e. it passes a "Brier ≤ 0.10" target while knowing nothing. Report
  **BSS = 1 − Brier/[p(1−p)]** instead. Measured calibrated BSS: `node_only` 0.0303 · `node_edge` 0.0468 ·
  `no_liq` 0.0652 · `addr_type` 0.0429 `[measured]`.
- The label measures **formal insolvency only** — 70 % of rows are excluded, so "not distressed" is not
  "healthy", only "not formally terminated". `[reported]`

---

## 2. The feature set contains a label artefact

**(2a) `officers` is a size/exit-route proxy read contemporaneously with the label.**
`officers = 0` → **99.1 %** distress (112 companies); `officers = 1` → **0.0008 %** (122,275 companies,
1 distress). Single-feature GBM AUC = **0.8117**. `[reported]` *(located in the export's own
`FEATURES.md` §4.3 — "single-feature reference, labelled subset" — and in `feature_config.json` as
`"single feature officers (GBM)": 0.8117`.)*
Dropping it collapses the tabular reference from **0.8395 → 0.6889** `[reported]` — which is why
**`A_clean5` = 0.6889**, not 0.8395, is the honest same-data baseline.

**(2b) Two of the six `no_priors` features are stale in the export.**
`related_company_count` and `related_company_weighted` are **96.72 % exactly zero** (unique values 150
and 841 respectively, over all 2,111,884 rows) `[measured]`, i.e. ≈3.3 % coverage. They are **2 of the 6**
features behind every published Singapore number in this family, so **those absolute values inherit this
caveat**; arm-to-arm comparisons do not, because both arms use the same columns.

> **A trap to avoid in any write-up: dropping own-`officers` (`clean5`) leaves the edge gain standing —
> but 91 % of the remaining gain is the *neighbour*-`officers` term (ICC = 21 %).** So on this graph the
> relational signal is **entangled with the same artefact**. The honest sentence is
> *"the graph helps, and on this data a large part of that help is the neighbourhood form of a
> label-adjacent feature"* — **not** "the graph captures contagion risk". `[reported]` (`clean5`
> 0.6883 → +5 neighbour means **0.8698** → + neighbour-`officers` only **0.8530**.)

---

## 3. Three routes that are simply closed

**(3a) Hypergraphs add nothing.**
- SMEsD, full-batch, 3 seeds: `node_only` **0.8040** vs `node_hyper` **0.8042** ⇒ **+0.0002** `[measured]`
  (recomputed from the raw ablation log).
- External SMEsD numbers: `full` **0.7891** vs `no_hyper` **0.7916** — the hypergraph version is
  *lower*. `[reported]`
- ACRA attribute hyperedge: **+0.0002**. `[reported]`
- Mechanism: the grouping fields (industry, region, type, qualification) are **already node features**,
  so the hyperedge re-injects the same information — and can create a large dense propagation channel.
  The design document itself states this.

**(3b) Pretrained/learned node embeddings are not trainable in this architecture.**
`gnn.py:295` — `self.company_emb = torch.FloatTensor(com_initial_emb).to(device)`: a **plain tensor
attribute**, not an `nn.Parameter` and not a registered buffer. `[measured]`
**Verified against the real saved checkpoint** — `weights.pt` contains **169 parameters**, and
**`company_emb` is not among them**. `[measured]` So the node embedding table is a **frozen random
projection**, not a learned representation.
Independently: retraining the embeddings on the current graph gives a probe of **0.518** against **0.515**
for a random projection — i.e. no signal. `[reported]`

**(3c) The random-graph "uncertainty interval" is not a prediction interval.**
Because `q` is a **node** constant, `z ~ Bernoulli(q)` re-sampling degenerates into **node-level
dropout**. The intervals are real (median width **0.0105**) but they are a **sensitivity analysis**;
the deterministic version even had the **higher** KS (**0.5468**). The correct summary is
*"sampling adds variance and no information"* — not "the intervals are noise". `[reported]` *(the
external report already words this correctly; it is repeated here only so the wording survives into
publication.)*

---

## 4. Scale — the actual constraint

The sizing problem is **not "can it run 1 M nodes" but "can it run 1 M nodes across 12+ relation
types"**. The current implementation has **two O(rel_num) loops** (one over all edges, one over all
nodes); measured **4 → 7 relations = +43 %**, so the 12-relation ceiling is **≈3×** a 4-relation run.
`[measured]` — and both fixes are known (precompute the masks; group edges by type in a single pass), so
this is an **optimisable constant, not a wall**. `[reported]`

---

## 5. What is held ready

- **Bit-neutrality, proved rather than asserted:** a state-dict hash, checked across runs. `[reported]`
- **Machine-offset measurement:** `node_only --seed 1` = **0.8279** (laptop) · **0.8287** (two independent
  cloud instances, identical) ⇒ a stable **+0.0008** offset. Seed spread is **0.0035**, so the honest
  three-seed noise floor is **0.002–0.007**, not 0.0008. `[measured]`
- **Attribution rule applied throughout:** "minute differences across machines are noise; only
  same-machine comparisons are admissible" — this is what forced the retraction of an earlier `+0.0011`
  claim.
- **CPU-verifiable reproduction:** three published checkpoints reproduce **exactly** 0.8279 / 0.8550 /
  0.8775 on CPU (≈9 min total). `[measured]`
- **A cautionary table of non-reproducing numbers.** The published ComRisk-family figure, a retrain of it,
  a locally adapted variant, and an earlier independent implementation do not agree:
  **0.8483** (paper Table 3) vs **0.8220–0.8248** (a retrain) vs **0.8093** (best) / **0.8112** (last
  epoch) (the locally adapted variant) vs **0.7936** (an earlier independent implementation).
  All four are `[reported]`/`[unverified]` for this note; **none was re-derived here** and no cause is
  claimed. If a paper rests on "it does not reproduce", this is the table it needs — and it is strongest
  if each number carries its own configuration.
  ⚠️ **Precision point that matters: the 0.8093 figure is NOT plain ComRisk.**
  `comrisk/train.py:148-165` fits a **Bayesian community prior** and passes it into the model, so 0.8093
  is **ComRisk + a community prior**, not a reproduction of the released code. Quoting it as "ComRisk
  scores 0.8093" would be wrong. `[measured]`

---

## 6. Explicitly NOT claimed here

- That the graph captures contagion risk. Both sides of the comparison exploit a **label artefact
  (size / exit route)**; §2 is why.
- That low-confidence edges are noise. [Evidence I §2](comrisk-confidence-channel-evidence.md#2-what-was-measured-when-the-channel-was-forced-into-the-model)
  shows the opposite under a threshold.
- That the design ("edge existence as first-class uncertainty") is wrong.
  [Evidence I §1c](comrisk-confidence-channel-evidence.md#1-the-headline-weakness-the-confidence-channel-cannot-carry-edge-uncertainty)
  is that it is **untested**.
- Any number whose only provenance is prose. Those are tagged `[unverified]` and should not be promoted.
