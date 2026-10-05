# ComRisk-family — documented weaknesses, with evidence

**Prepared 2026-10-05.** A standalone evidence note on the ComRisk family of models (graph-based
corporate default prediction). Companion script: `verify_weakness_evidence.py`, which re-derives every
`[measured]` number below from the parquet data, the raw run logs, the saved checkpoint and the source
code — run it and check.

---

## 0. Evidence tags used in this note

| tag | meaning |
|---|---|
| **`[measured]`** | re-derived **here**, directly from the data / the raw run logs / the source and the saved checkpoint. Reproducible. |
| **`[reported]`** | the number appears in an **external document** (a report or a data export). The exact line was located; the experiment was **not** re-run here. |
| **`[unverified]`** | reached this analysis only as prose. **Receipt time and wording cannot be independently checked.** |

**Every number carries a tag.** `[measured]` means this note stands behind the number. `[reported]` means
"it is asserted in that document" — not that this note reproduced it. **Interpretive sentences**
(mechanisms, "this is untested", "not harmful") are reasoning built on the tagged numbers, not
measurements, and are written as such.

---

## 1. The headline weakness: the confidence channel cannot carry edge uncertainty

**(1a) On the Singapore export, the edge-confidence column IS a node feature.**
`existence_confidence` is **bit-identical to `address_trust`** — on every one of the **3,858,395**
`SAME_ADDRESS` edges, at **both endpoints**, **0 exceptions**. `[measured]`
The same identity is also stated in the external check report (§Ⅲ.3) and in the edge-table manifest.
`[reported]`

> **Consequence, stated plainly:** a per-edge confidence that is constant *within a node* cannot express
> "how much is this relation believed" — by construction. Any model term that consumes it is re-using
> information the node branch already has.

**(1b) On the SMEsD variant it is worse — it is constant.**
`existence_confidence` is **1.0 on all 18,274** train edges. `[reported]` *(verified against the shipped
`train.json`: a single unique value across all 18,274 edges.)*

**(1c) The channel is therefore untested, not disproven.** This is the point that matters for a paper:
the *design* (edge existence as a first-class uncertainty) has **never been evaluated with an input that
actually varies per edge**. Every negative below is a negative about *this* channel, not about the idea.
**A confidence rebuilt from evidence semantics is the open experiment** — and to this analysis's
knowledge it has not been run.

---

## 2. What was measured when the channel *was* forced into the model

All on the same frozen splits. Configuration: 6-dim `no_priors`, 10 epochs, batch 2048, fanout 10,
5 hops, full 2.1 M-node scale.

**(2a) Placement matters, and the post-softmax form is the harmful one.** 3 seeds each, every other
setting identical — `uniform` and `pre` come from one box; `post` comes from a second box, and the two
boxes are **proven equivalent** because both ran the identical `pre` config and produced **bit-identical**
values (0.8570 / 0.8585 / 0.8612): `[measured]`

| form | ROC | Δ vs uniform |
|---|---|---|
| uniform graph (every weight = 1.0) | **0.8591 ± 0.0070** | — |
| `softmax(logits + log q)` — **before** | **0.8589 ± 0.0021** | **−0.0002 → a tie** |
| `softmax(logits) · q` — **after** | **0.8440 ± 0.0035** | **−0.0149** |

The reference implementation (`com_risk_runtime/model.py`:
`segment_softmax(logits + weight.log(), target, n)`) already does the **before** form, while the
accompanying written guidance argues for **after**. The measurement says the kernel is right and the
guidance is not — **the disagreement is internal to that work's own documentation, not in any
implementation of it.** The external `6dim_Conf` arm gives **0.8442 ± 0.0029** against this note's
**0.8440 ± 0.0035** — 0.0002 apart, different seed sets (0/1/2 vs 1/2/3) and different machines, so this
is a **reproduction rather than a shared artefact** `[measured]` / `[reported]`.

> **Why the "after" form fails, mechanically:** `q` averages **0.3471** (computed directly from the
> confidence tiers `[measured]`), and multiplying by it at **every hop and every layer** compresses the
> whole graph channel to ≈0.35×, so after 5 hops the residual node-feature path dominates. The
> pre-softmax form has no such decay because the softmax renormalises it away.

**(2b) Filtering by confidence hurts, monotonically.** `[measured]` *(⚠️ this chain mixes machines and
contains one single-seed rung — read the labels)*

| edges kept | ROC |
|---|---|
| all edges (`node_edge`, 3 seeds) | **0.8578** |
| `q ≥ 0.2` (72.6 % kept, server, 3 seeds) | **0.8422 ± 0.0025** |
| `q ≥ 0.5` (45.4 % dropped, laptop, **seed 1 only**) | **0.8391** |
| `q ≥ 0.8` (8.2 % kept, server, 3 seeds) | **0.8317 ± 0.0046** |
| `is_inferred = False` only (1,089 edges, server, 3 seeds) | **0.8314 ± 0.0041** |

**(2c) Filtering by confidence is indistinguishable from filtering at random.** `conf50` **0.8377 ± 0.0031**
against a random-deletion control that drops the same **45.4 %**, `conf50_RANDCTRL` **0.8388 ± 0.0034**.
`[reported]`

**(2d) Weighted propagation is not better than the plain graph.** `6dim_Conf` − `6dim_noConf` =
**−0.0136 (≈6.1 SE, AP −14 %)**. `[reported]`

**(2e) A trivial neighbour-average control gets most of the way.** Inductive, fanout = 10 (the same
budget as the GNN), 3 split seeds: own 6 features only **0.8395**; own + 6 neighbour means **0.8467**
(+0.0072). The GNN's `node_edge` **0.8578** therefore beats the trivial baseline by only **+0.0111** —
the honest framing is *"the graph adds a real but modest amount over neighbour averaging on this label"*,
not "the graph is the source of the signal". `[measured]`

> *(2b) and (2c) are the same finding from two directions: **"low confidence" ≠ "harmful".** The
> `edges_no_low` variant (`q ≥ 0.2`, 72.55 %, the same construction as the `q ≥ 0.2` row above) removes
> 1.25 M low-confidence edges and loses 0.0156 ROC, so the low tiers carry signal in aggregate even
> though they are where the harmful edges sit.*

---

## 3. The label is a registry proxy, not a credit outcome

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

## 4. The feature set contains a label artefact

**(4a) `officers` is a size/exit-route proxy read contemporaneously with the label.**
`officers = 0` → **99.1 %** distress (112 companies); `officers = 1` → **0.0008 %** (122,275 companies,
1 distress). Single-feature GBM AUC = **0.8117**. `[reported]` *(located in the export's own
`FEATURES.md` §4.3 — "single-feature reference, labelled subset" — and in `feature_config.json` as
`"single feature officers (GBM)": 0.8117`.)*
Dropping it collapses the tabular reference from **0.8395 → 0.6889** `[reported]` — which is why
**`A_clean5` = 0.6889**, not 0.8395, is the honest same-data baseline.

**(4b) Two of the six `no_priors` features are stale in the export.**
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

## 5. Three routes that are simply closed

**(5a) Hypergraphs add nothing.**
- SMEsD, full-batch, 3 seeds: `node_only` **0.8040** vs `node_hyper` **0.8042** ⇒ **+0.0002** `[measured]`
  (recomputed from the raw ablation log).
- External SMEsD numbers: `full` **0.7891** vs `no_hyper` **0.7916** — the hypergraph version is
  *lower*. `[reported]`
- ACRA attribute hyperedge: **+0.0002**. `[reported]`
- Mechanism: the grouping fields (industry, region, type, qualification) are **already node features**,
  so the hyperedge re-injects the same information — and can create a large dense propagation channel.
  The design document itself states this.

**(5b) Pretrained/learned node embeddings are not trainable in this architecture.**
`gnn.py:295` — `self.company_emb = torch.FloatTensor(com_initial_emb).to(device)`: a **plain tensor
attribute**, not an `nn.Parameter` and not a registered buffer. `[measured]`
**Verified against the real saved checkpoint** — `weights.pt` contains **169 parameters**, and
**`company_emb` is not among them**. `[measured]` So the node embedding table is a **frozen random
projection**, not a learned representation.
Independently: retraining the embeddings on the current graph gives a probe of **0.518** against **0.515**
for a random projection — i.e. no signal. `[reported]`

**(5c) The random-graph "uncertainty interval" is not a prediction interval.**
Because `q` is a **node** constant, `z ~ Bernoulli(q)` re-sampling degenerates into **node-level
dropout**. The intervals are real (median width **0.0105**) but they are a **sensitivity analysis**;
the deterministic version even had the **higher** KS (**0.5468**). The correct summary is
*"sampling adds variance and no information"* — not "the intervals are noise". `[reported]` *(the
external report already words this correctly; it is repeated here only so the wording survives into
publication.)*

---

## 6. The uncertainty channel as designed cannot be fed by these fields

Two independent analyses reached this from opposite directions:

- The external check report: the confidence field is **redundant**; if it is to represent uncertainty,
  **the current fields are not enough and must be supplemented**. `[unverified]`
- The design work's own TODO list: go back to the graph-building stage and **rebuild edge-level
  confidence from evidence semantics** (same address + same industry + similar size → strong; same
  address only → weak), folding `source_system` / `is_inferred` / `evidence_count` into evidence grades.

**This is the single most valuable open direction visible from here, and it is a DATA job, not a model
tweak** — new graph script, new export, all baselines re-run. **To this analysis's knowledge it is also
unassigned.**

---

## 7. Four eliminated routes, each with a control

| route | result | control that makes it credible |
|---|---|---|
| confidence-weighted propagation | **−0.0136** (≈6.1 SE, AP −14 %) | vs the same run with `q ≡` constant |
| confidence-based edge filtering | **0.8377** vs random-deletion **0.8388** | random deletion of the *same number* of edges |
| random-graph intervals | median width 0.0105 | vs a deterministic run (higher KS 0.5468) |
| hyperedge / pretrained embedding | no gain (see §5) | attribute-only hyperedge; random-projection probe |

**A "these four routes were tried, and here is why each fails" table is worth more to a paper than
another small positive number**, because each row carries its own control.

---

## 8. Scale — the actual constraint

The sizing problem is **not "can it run 1 M nodes" but "can it run 1 M nodes across 12+ relation
types"**. The current implementation has **two O(rel_num) loops** (one over all edges, one over all
nodes); measured **4 → 7 relations = +43 %**, so the 12-relation ceiling is **≈3×** a 4-relation run.
`[measured]` — and both fixes are known (precompute the masks; group edges by type in a single pass), so
this is an **optimisable constant, not a wall**. `[reported]`

---

## 9. What is held ready

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

## 10. Explicitly NOT claimed here

- That the graph captures contagion risk. Both sides of the comparison exploit a **label artefact
  (size / exit route)**; §4 is why.
- That low-confidence edges are noise. §2 shows the opposite under a threshold.
- That the design ("edge existence as first-class uncertainty") is wrong. §1c: it is **untested**.
- Any number whose only provenance is prose. Those are tagged `[unverified]` and should not be promoted.
