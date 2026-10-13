# RiskGNN++: Topology-Aware Evidence Fusion and Conflict-Guided Triage for Corporate Risk Graphs

**Anonymous Authors — Working Draft, 13 October 2026**

> Internal revision based on saved training artifacts and prediction replay. This draft reports empirical results; graph-dependent coverage guarantees and causal contagion claims remain unestablished. Reproduction details and outstanding checks: [experiment supplement](riskgnn-plus-plus-experiments.md) and [revision report](riskgnn-plus-plus-review.md).

## Abstract

Multi-relational corporate graphs can reinforce overlapping evidence, while a classifier's confidence alone may not identify the cases that need human review. We ask whether disagreement among relational views can improve both risk prediction and the allocation of a limited review budget. RiskGNN++ extends a dual-branch graph model with relation-specific Dirichlet opinions, discounts conflicting opinions according to disagreement and node degree, and scales fused evidence by degree. For review allocation, it combines calibrated probability ambiguity with inter-view conflict, keeping this ranking task separate from classification and conformal prediction. We evaluate the method over ten training seeds on UK and SMEsD corporate graphs. On UK, RiskGNN++ does not show an average-precision gain over RiskGNN+ (32.89% versus 32.81%; paired $p=0.965$), but conflict-guided ranking reduces the area under the risk–coverage curve from 0.0097 to 0.0083 ($p=0.002$). The gain is not significant at 70% automatic coverage and does not replicate on SMEsD. These results identify conflict as a promising review signal in the tested UK setting, while leaving its generality and the predictive value of the architectural changes unresolved.

## 1. Introduction

Corporate graphs connect firms through ownership, shared addresses, names, and other relationships. Such structure can complement intrinsic firm attributes, but disagreement between attributes and relational representations may make a prediction difficult to trust. Our objective is to assess whether this disagreement improves review allocation beyond the probability margin of the same classifier.

Evidential deep learning (EDL) maps nonnegative evidence to a Dirichlet distribution [1]. Its vacuous mass is often interpreted as epistemic uncertainty. Multi-view evidential fusion combines opinions using Dempster–Shafer rules [2]. However, loss-based second-order prediction does not automatically establish that an uncertainty score faithfully represents epistemic uncertainty [3, 4]. We therefore evaluate both classification and selective prediction, rather than inferring operational reliability from the evidence parameterization.

Our contributions are:

1. **Relation-specific evidence fusion.** RiskGNN++ retains separate relational opinions and discounts them using disagreement and in-degree before fusion.
2. **An empirical uncertainty audit.** On saved UK predictions, conflict concentrates classification errors, whereas scalar evidential uncertainty is a weaker review-ranking signal.
3. **Separated triage protocols.** We distinguish fixed-budget conflict ranking from topology-aware conformal prediction, report their different outcomes, and state the assumptions needed for coverage claims.

The comparison concerns the implementations and configurations in this repository. It does not establish state-of-the-art performance against the wider literature or identify a causal default-contagion mechanism.

## 2. Problem and Evidence Audit

Let the corporate graph be $\mathcal{G}=(\mathcal{V},\mathcal{E},\mathcal{R})$, with binary corporate-status label $y_i\in\{0,1\}$. The positive label follows each dataset's encoding; calling it a future loan default requires a documented prediction horizon and outcome definition. The primary classifier produces $\hat p_i$, and a separate review score ranks predictions for deferral.

In binary subjective logic, $\alpha_k=e_k+1$, $S=\alpha_0+\alpha_1$, $b_k=e_k/S$, and $u=2/S$. Thus, increasing total evidence algebraically reduces $u$. Whether graph aggregation causes unjustified evidence growth is a mechanism hypothesis, requiring degree-conditioned evidence and error analyses beyond this identity.

The saved UK diagnostics partition RiskGNN++ predictions by its composite conflict output (defined in Section 3.2). Table 1 reports classification error at a primary probability threshold of 0.5, not observed default prevalence.

**Table 1. UK classification error by conflict quartile.** Ratios use unrounded rates; the large ratios partly reflect small low-conflict denominators.

| Seed | Highest quartile error (%) | Lowest quartile error (%) | Ratio | Pearson correlation with error |
| ---: | ---: | ---: | ---: | ---: |
| 14 | 29.39 | 2.08 | 14.2× | 0.2561 |
| 42 | 35.92 | 0.44 | 82.1× | 0.3625 |
| 2026 | 33.27 | 0.48 | 69.3× | 0.3464 |

Conflict measures model disagreement, rather than risk magnitude or verified contagion. Its Pearson correlation with label-derived neighborhood heterophily is only 0.040–0.071 in the same diagnostics. These associations do not identify whether disagreements arise from noisy relations, feature inadequacy, class weighting, or contagion.

## 3. Method

### 3.1 Backbone and evidential branches

RiskGNN++ extends RiskGNN+, retaining the intrinsic feature branch, five heterogeneous graph layers, enabled hypergraph processing, and a learnable mixture feeding the primary classifier. Community priors use training labels; training features use leave-one-out priors. The intrinsic branch is implemented by the inherited feature extractor, rather than a standalone MLP over raw attributes alone.

A node evidence head and an aggregate graph evidence head are retained for auxiliary supervision. The new relation heads pool final graph representations, including person representations where present. For each relation, the implementation averages incoming neighbor representations **together with the target's own representation**, dividing by relation in-degree plus one. An absent relation therefore still produces a self-based opinion, rather than an exactly vacuous source. An exponential of a linear projection clamped to $[-10,10]$ yields the relation evidence.

The heads are relation-specific, but their inputs share a graph backbone and include self-information. They should not be described as statistically independent evidence sources; dependence and repeated evidence are limitations of the fusion interpretation.

### 3.2 Discounting, fusion, and reported conflict

For opinions $\omega_a=(\mathbf b_a,u_a)$ and $\omega_b=(\mathbf b_b,u_b)$, binary conflict is $K(\omega_a,\omega_b)=b_{a,0}b_{b,1}+b_{a,1}b_{b,0}$. Relation $r$ is discounted using:

$$W_{i,r}=(1-K(\omega_i^{\mathrm{node}},\omega_{i,r}))^{\gamma_d}(1+d_i)^{-\eta}.$$

Here $d_i$ counts incoming edges of the considered relations, $\gamma_d=1$, and $\eta=0.25$. Discounting multiplies belief masses by $W_{i,r}$ and transfers the removed mass to uncertainty. The node opinion and discounted relation opinions are fused sequentially using Dempster's rule:

$$\mathbf b^{\mathrm{fused}}=\frac{\mathbf b_a\odot\mathbf b_b+\mathbf b_a u_b+\mathbf b_b u_a}{1-K(\omega_a,\omega_b)},\qquad u^{\mathrm{fused}}=\frac{u_a u_b}{1-K(\omega_a,\omega_b)}.$$

The reported conflict output is distinct from the sequential fusion normalizers. It is computed **before discounting** as the average of (i) mean node-to-relation pairwise conflict and (ii) mean relation-to-relation pairwise conflict. For one relation, the latter is zero. This composite output is used for RiskGNN++ triage and Table 1; the original two-branch node-versus-graph conflict is a different quantity.

### 3.3 Degree-scaled evidence and optimization

After fusion, the evidence budget is scaled as:

$$\boldsymbol\alpha_i^{\mathrm{reg}}=\mathbf1+\frac{\boldsymbol\alpha_i^{\mathrm{fused}}-\mathbf1}{1+\lambda_d d_i/(\bar d+1)},\qquad \lambda_d=0.5.$$

In the implementation, $\bar d$ is the current forward-call mean degree clamped below at one and detached from gradients. The scaling is used during both training and evaluation; reported fused probabilities and uncertainty are derived from regularized evidence. The primary probabilities remain the softmax output of the discriminative head.

The implemented objective adds primary class-weighted cross entropy, fused expected Dirichlet cross entropy (weight 0.5), node and aggregate-graph expected cross entropies (0.15 each), and fused Dirichlet KL regularization (0.001). The KL term uses $\tilde\alpha_k=y_k+(1-y_k)\alpha_k$. The evidential expected cross entropies are also class weighted. The aggregate graph head remains auxiliary and is not a separately fused source in the new multi-source combination.

### 3.4 Topology-aware conformal score

We call the conformal component **Topology-Aware Conformal Risk Auditor (TACR)**, following the implementation. For candidate class $k$, it uses:

$$E(x,k)=1-\hat p_k(x)+\gamma_c C(x)+\beta_c u(x).$$

The replay uses $\gamma_c=0.6$, $\beta_c=0.05$, and nominal miscoverage $\epsilon=0.05$. The probability is the raw primary output; no temperature or isotonic probability calibration was applied. Calibration selects the $\lceil(n_{\mathrm{cal}}+1)(1-\epsilon)\rceil$-th smallest true-label score, with an infinite threshold if the rank exceeds the calibration size. The prediction set contains all classes whose scores do not exceed this threshold.

Singleton sets produce automatic predictions; two-class sets are deferred. Empty sets are reported separately. An empty set alone does not establish an out-of-distribution observation, despite the implementation's `OOD_ALERT` action name.

The standard finite-sample marginal coverage statement requires exchangeability of calibration and test scores under an appropriate fixed-model protocol [5, 6]. It does not require independence as a separate assumption. Adding conflict to the score does not establish exchangeability or repair arbitrary graph dependence. The current optional `network_inflation` subtracts a user-specified quantity from epsilon; `max_degree` is unused and there is no implemented graph-dependence bound. All coverage here is empirical.

### 3.5 Recalibrated risk–coverage triage

Under the current class-weighted training protocol, raw probabilities are poorly calibrated. Every arm is recalibrated on the calibration split: isotonic regression on UK (23,332 points) and Platt scaling on SMEsD (360 points). Isotonic regression is nondecreasing but creates ties, which can change AP and review-score rankings. The calibration labels are reused to select the conflict weight; test labels are not used in either step.

Triage is then evaluated as a risk–coverage curve rather than a single thresholded error rate. Let $s_i$ be a review score, oriented so that larger values are deferred first. Deferring the highest-scoring firms leaves a fraction $c$ of firms processed automatically, and the selective risk $R(c)$ is the 0/1 error of those retained, using the recalibrated probability at threshold 0.5. We report the area under this curve, $\mathrm{AURC}=\int_0^1 R(c)\,\mathrm{d}c$ (lower is better), together with the risk at fixed coverage levels.

Three review scores are compared on identical predictions:

- **probability ambiguity** $0.5-|\hat p_1-0.5|$, the natural margin baseline;
- **scalar evidence uncertainty** $u$, the score a naive evidential pipeline would use;
- **conflict-guided ranking**, ambiguity plus $\gamma C$ with the composite conflict $C$ of Section 3.2. This is distinct from the TACR conformal score in Section 3.4.

The conflict weight $\gamma$ is selected on the calibration split by minimising the calibration risk at 70% coverage, never on test; selected values range from 0.0 to 0.4 across seeds. The AURC and fixed-coverage metrics are computed on test predictions only and are paired across seeds. Review accuracy, monetary cost, and a prospective lending protocol are not modeled.

## 4. Experiments

### 4.1 Protocol

We use ten training seeds (7, 14, 21, 42, 77, 101, 314, 555, 888, 2026), 250 epochs, learning rate 0.01, cosine annealing, gradient clipping at 0.25, and checkpoint selection by validation ROC-AUC every five epochs. All seeds reuse the same data split. Values below are means ± sample standard deviations, not confidence intervals; paired comparisons across seeds report a paired $t$-test, a Wilcoxon signed-rank test, and a bootstrap 95% confidence interval of the mean difference.

The UK dataset has 233,251 firms and four relations (`SAME_ADDRESS`, `EQUITY`, `PREVNAME`, `SAME_NAME`). Train/validation/calibration/test sizes are 139,956/23,332/23,332/46,631. The 248,517 edges are the **training snapshot** count; validation and test snapshots contain 84,060 and 79,771 edges. Test positive prevalence is 3.42%.

SMEsD has 3,976 firm nodes, 2,405 person nodes, and 12 relation types. Its train/validation/calibration/test sizes are 2,816/361/360/491, with 3,556 test-snapshot edges and 64.77% test positive prevalence. The published split contains overlapping firm IDs; the experiment preserves that split. This limits independence and leakage interpretations (see the supplement).

### 4.2 Discrimination and probability quality

**Table 2. UK primary-head performance over ten seeds.** “PR-AUC” in the artifacts is average precision (AP), not trapezoidal area under an interpolated PR curve. ECE uses ten equal-width probability bins. AP, ECE, and ROC-AUC are percentages; Brier is unscaled.

| Model | AP (%) ↑ | ECE (%) ↓ | Brier ↓ | ROC-AUC (%) ↑ |
| --- | ---: | ---: | ---: | ---: |
| ComRisk | 29.01 ± 3.54 | 23.75 ± 4.40 | 0.1319 ± 0.0242 | 85.56 ± 0.82 |
| RiskGNN | 29.92 ± 4.10 | 25.31 ± 8.34 | 0.1478 ± 0.0446 | **85.64 ± 1.17** |
| RiskGNN+ | 32.81 ± 3.30 | 26.33 ± 5.36 | 0.1422 ± 0.0259 | 85.59 ± 1.15 |
| RiskGNN++ | **32.89 ± 4.65** | **23.11 ± 2.82** | **0.1348 ± 0.0159** | 85.56 ± 1.02 |

Over ten seeds RiskGNN++ improves raw mean AP over ComRisk by 3.88 percentage points (paired $t$ $p = 0.027$, Wilcoxon $p = 0.049$, 7/10 seeds) but is indistinguishable from RiskGNN+ (0.08 points, paired $t$ $p = 0.965$, 6/10 seeds). The corresponding **recalibrated** AP comparisons are +4.65 points ($p = 0.010$, 8/10) and +0.99 points ($p = 0.572$, 5/10). These recalibrated tests must not be attached to Table 2's raw AP. ROC-AUC, ECE and Brier differences among the evidential variants are within seed noise. The earlier three-seed advantage over RiskGNN+ is not sustained.

Under the current class-weighted protocol, every arm overpredicts positives on UK: raw Brier (0.1319–0.1478) exceeds a constant base-rate predictor (0.0330), and raw accuracy (0.78–0.81) is below always predicting negative (0.9658). Isotonic recalibration fit on the calibration split reduces Brier to 0.0276–0.0285 and ECE to 0.0060–0.0091; accuracy rises to 0.966–0.968. This does not isolate class weighting as the cause. Because isotonic ties alter AP, raw and recalibrated AP are reported separately. Decision-level metrics below use recalibrated probabilities.

### 4.3 Recalibrated risk–coverage triage

**Table 3. UK recalibrated risk–coverage triage over ten seeds.** Selective 0/1 error of the automatically processed firms after isotonic recalibration on the calibration split; lower is better. AURC integrates the risk–coverage curve over automatic coverage $c\in[0,1]$.

| Review score | AURC ↓ | Risk@0.5 ↓ | Risk@0.7 ↓ | Risk@0.9 ↓ |
| --- | ---: | ---: | ---: | ---: |
| Probability ambiguity | 0.0097 | 0.0069 | 0.0089 | 0.0155 |
| Scalar evidence uncertainty $u$ | 0.0465 | 0.0420 | 0.0362 | 0.0339 |
| Conflict-guided ranking (ambiguity + $\gamma C$) | **0.0083** | **0.0063** | 0.0087 | 0.0156 |

Paired comparisons across the ten seeds, on the same RiskGNN++ predictions:

| Comparison | Mean difference | 95% CI | Paired $t$ | Wilcoxon | Seeds favoured |
| --- | ---: | ---: | ---: | ---: | ---: |
| AURC: conflict ranking − ambiguity | −0.0014 | [−0.0020, −0.0008] | 0.0023 | 0.0078 | 8/10; tied in 2 |
| AURC: conflict ranking − uncertainty $u$ | −0.0382 | [−0.0459, −0.0302] | <0.0001 | 0.0020 | 10/10 |
| Risk@0.7: conflict ranking − ambiguity | −0.0002 | [−0.0006, +0.0001] | 0.2765 | 0.4609 | 5/10; tied in 2 |

Scalar evidential uncertainty is a substantially worse review score than the probability margin at the measured coverage levels. Adding conflict produces a small AURC reduction, significant under the reported paired tests, concentrated at low automatic coverage. Two seeds select $\gamma=0$ and tie the baseline; thus “10/10 improved” would be inaccurate. The 70% coverage improvement is not significant. UK isotonic calibration leaves 99.7–99.9% of ambiguity scores in tied groups; the baseline breaks ties by saved input order. In a sensitivity check averaging 30 random input permutations per seed, mean baseline AURC is 0.0096 versus 0.0083 for conflict ranking, which is better in eight seeds and tied with the deterministic baseline in two. This does not remove all tie-breaking dependence or selection bias from tuning $\gamma$ on the same calibration labels used to fit isotonic regression. Monetary cost and prospective lending performance remain unmodeled.

### 4.4 Conformal prediction and transfer

The risk–coverage protocol of Section 4.3 is the primary triage evaluation. We additionally replay the conformal auditor, which operates on uncalibrated probabilities and produces prediction sets rather than a ranked budget, as a secondary check on the same predictions.

**Table 4. Prediction-set replay using RiskGNN++ (%).** Three-seed replay; this secondary check has not been extended to ten seeds. Coverage, automatic rate, and automatic error are separate metrics. Automatic populations differ across scores; their errors are not a matched-budget comparison.

| Dataset | Score | Coverage | Automatic rate | Automatic error |
| --- | --- | ---: | ---: | ---: |
| UK | Probability-only | 94.69 ± 0.58 | 70.12 ± 9.02 | 7.60 ± 0.33 |
| UK | Evidence-augmented | 94.78 ± 0.56 | 70.02 ± 9.31 | 7.48 ± 0.38 |
| UK | TACR | 94.88 ± 0.36 | 67.47 ± 8.06 | 7.61 ± 0.39 |
| SMEsD | Probability-only | 95.11 ± 1.13 | 38.83 ± 11.47 | 12.87 ± 1.88 |
| SMEsD | Evidence-augmented | 95.38 ± 0.72 | 38.63 ± 11.22 | 12.36 ± 2.16 |
| SMEsD | TACR | 95.45 ± 1.03 | 38.90 ± 10.71 | 11.86 ± 1.09 |

UK TACR slightly increases empirical coverage, while automatic error does not improve over probability-only CP. SMEsD shows lower mean automatic error with TACR. Neither result establishes a graph-dependent theorem. The original 95.38% SMEsD figure belongs to evidence-augmented CP, rather than TACR.

On SMEsD over ten seeds, RiskGNN++ has AP 87.79 ± 1.25%, ROC-AUC 80.24 ± 1.30%, ECE 9.77 ± 1.77%, and Brier 0.1793 ± 0.0069; RiskGNN+ has AP 87.74 ± 1.60%, ROC-AUC 80.26 ± 2.43%, ECE 7.58 ± 1.70%, and Brier 0.1720 ± 0.0083. Paired differences are not significant on these metrics (AP $p = 0.95$, ROC-AUC $p = 0.98$). SMEsD ECE changes from 9.77% to 8.26% after Platt scaling; these data do not identify the cause of residual miscalibration. Conflict-guided ranking has higher mean AURC than the probability margin (0.1479 vs 0.1443, paired $p = 0.063$); scalar evidence uncertainty is worse still (0.2021). Two datasets cannot establish which graph or prevalence property controls transfer.

## 5. Discussion and Limitations

After ten seeds, RiskGNN++ is statistically indistinguishable from RiskGNN+ on UK AP, ROC-AUC, ECE and Brier; its raw AP advantage over ComRisk is significant under the reported tests. The main incremental result is an observed UK AURC reduction from adding conflict to the same model's probability ambiguity, subject to extensive isotonic ties and a single shared test graph. Scalar evidence uncertainty is a worse review signal than ambiguity here. Neither finding identifies majority-neighbor evidence inflation as the cause. The contribution of class weighting to probability miscalibration needs an unweighted ablation.

The evidence does not establish that edge-confidence channels universally collapse, that high conflict identifies causal contagion, or that dataset differences constitute a phase transition. Shared representations weaken an independent-source interpretation of Dempster fusion. Missing-relation heads and split-dependent mean-degree scaling also deserve ablation. UK component-removal experiments, repeated data splits, held-out score selection, calibrated probability baselines, and uncertainty estimates accounting for graph dependence remain necessary.

## 6. Conclusion

RiskGNN++ combines relation-specific opinions with topology-aware discounting and degree-scaled evidence. Saved UK experiments show higher raw AP than ComRisk and a small AURC gain from conflict-guided ranking, without an established AP gain over RiskGNN+ or a fixed-budget triage gain. SMEsD and conformal-score replay limit generalization. Further split-level and tie-aware evaluation is needed before an operational claim.

## References

1. Sensoy, M., Kaplan, L., and Kandemir, M. *Evidential Deep Learning to Quantify Classification Uncertainty*. NeurIPS, 2018. [Paper](https://arxiv.org/abs/1806.01768).
2. Han, Z., Zhang, C., Fu, H., and Zhou, J. T. *Trusted Multi-View Classification*. ICLR, 2021. [Paper](https://arxiv.org/abs/2102.02051).
3. Bengs, V., Hüllermeier, E., and Waegeman, W. *Pitfalls of Epistemic Uncertainty Quantification through Loss Minimisation*. 2022 preprint. [Paper](https://arxiv.org/abs/2203.06102).
4. Jürgens, M., et al. *Is Epistemic Uncertainty Faithfully Represented by Evidential Deep Learning Methods?* ICML, 2024. [Paper](https://arxiv.org/abs/2402.09056).
5. Angelopoulos, A. N., and Bates, S. *A Gentle Introduction to Conformal Prediction and Distribution-Free Uncertainty Quantification*. 2021, revised 2022. [Paper](https://arxiv.org/abs/2107.07511).
6. H. Zargarbashi, S., Antonelli, S., and Bojchevski, A. *Conformal Prediction Sets for Graph Neural Networks*. ICML, 2023. [Proceedings](https://proceedings.mlr.press/v202/h-zargarbashi23a.html).

[PENDING VERIFICATION] Add the exact source publications and versions for the repository's ComRisk and RiskGNN baselines; the original ComRisk bibliographic entry has not been verified.
