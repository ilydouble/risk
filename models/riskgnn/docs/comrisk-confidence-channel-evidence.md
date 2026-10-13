# ComRisk-family evidence I — the edge-confidence channel

**Prepared 2026-10-05.** A standalone evidence note on the ComRisk family of models (graph-based
corporate default prediction). Companion script: `verify_weakness_evidence.py`, which re-derives every
`[measured]` number below from the parquet data, the raw run logs, the saved checkpoint and the source
code — run it and check. Label-, feature-, closed-route- and scale-level evidence is in
[evidence II](comrisk-data-and-scale-evidence.md).

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

## 3. The uncertainty channel as designed cannot be fed by these fields

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

## 4. Four eliminated routes, each with a control

| route | result | control that makes it credible |
|---|---|---|
| confidence-weighted propagation | **−0.0136** (≈6.1 SE, AP −14 %) | vs the same run with `q ≡` constant |
| confidence-based edge filtering | **0.8377** vs random-deletion **0.8388** | random deletion of the *same number* of edges |
| random-graph intervals | median width 0.0105 | vs a deterministic run (higher KS 0.5468) |
| hyperedge / pretrained embedding | no gain (see [evidence II §3](comrisk-data-and-scale-evidence.md#3-three-routes-that-are-simply-closed)) | attribute-only hyperedge; random-projection probe |

**A "these four routes were tried, and here is why each fails" table is worth more to a paper than
another small positive number**, because each row carries its own control.

---

Label-, feature-, closed-route- and scale-level evidence is in
[evidence II](comrisk-data-and-scale-evidence.md); its final section lists what this evidence set does
**not** claim.
