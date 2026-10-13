# RiskGNN++: Topology-Aware Evidence Fusion and Conflict-Guided Triage for Corporate Risk Graphs

**Anonymous Authors — Working Draft, 13 October 2026**

> Internal revision based on saved training artifacts and prediction replay. This draft reports empirical results; graph-dependent coverage guarantees and causal contagion claims remain unestablished. Reproduction details and outstanding checks: [experiment supplement](riskgnn-plus-plus-experiments.md) and [revision report](riskgnn-plus-plus-review.md).

## Abstract

Corporate risk models must distinguish default prediction from deciding which predictions require human review. Dirichlet evidence provides an uncertainty score, but its usefulness for review allocation must be evaluated separately from classification performance. We introduce RiskGNN++, which extends a dual-branch graph model with relation-specific evidential heads, conflict- and degree-based opinion discounting, and a degree-scaled evidence budget. On a UK corporate dataset containing 233,251 firms, three-seed average precision increases from 31.63% for the implemented ComRisk baseline to 35.32%, while ECE decreases from 22.88% to 20.71%. These metrics use the primary classifier probabilities. Inter-source conflict is associated with classification error: the highest-conflict quartile has 14.2–82.1 times the error rate of the lowest quartile. At a fixed 30% review budget, adding conflict to probability-margin ranking reduces automatic error from 7.38% to 6.85% on the same RiskGNN++ predictions. We also evaluate a topology-aware conformal score separately; it attains 94.88% empirical coverage on UK data at a nominal 95% target, without improving automatic error over probability-only conformal prediction. Results on SMEsD show mixed discrimination and calibration effects. The evidence supports conflict-guided selective prediction in the tested UK setting, while broader transfer and coverage under graph dependence require further validation.

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

### 3.5 Fixed-budget review ranking

A separate protocol reviews the highest-scoring $\lceil BN\rceil$ firms and predicts the remainder at threshold 0.5. We compare $u$, probability ambiguity $0.5-|\hat p_1-0.5|$, and ambiguity plus $0.6C$. Ties follow saved input order. Automatic error is the number of wrong retained predictions divided by the number retained. Review accuracy and business costs are not modeled.

This ranking does not use a conformal threshold and inherits no conformal coverage guarantee. Its conflict coefficient is fixed for this replay; a prospective evaluation requires its selection on validation data before accessing test results.

## 4. Experiments

### 4.1 Protocol

We use training seeds 14, 42, and 2026, 250 epochs, learning rate 0.01, cosine annealing, gradient clipping at 0.25, and checkpoint selection by validation ROC-AUC every five epochs. Three seeds reuse the same data split. Values below are means ± sample standard deviations, not confidence intervals.

The UK dataset has 233,251 firms and four relations (`SAME_ADDRESS`, `EQUITY`, `PREVNAME`, `SAME_NAME`). Train/validation/calibration/test sizes are 139,956/23,332/23,332/46,631. The 248,517 edges are the **training snapshot** count; validation and test snapshots contain 84,060 and 79,771 edges. Test positive prevalence is 3.42%.

SMEsD has 3,976 firm nodes, 2,405 person nodes, and 12 relation types. Its train/validation/calibration/test sizes are 2,816/361/360/491, with 3,556 test-snapshot edges and 64.77% test positive prevalence. The published split contains overlapping firm IDs; the experiment preserves that split. This limits independence and leakage interpretations (see the supplement).

### 4.2 Discrimination and probability quality

**Table 2. UK primary-head performance.** “PR-AUC” in the artifacts is average precision (AP), not trapezoidal area under an interpolated PR curve. ECE uses ten equal-width probability bins. AP, ECE, and ROC-AUC are percentages; Brier is unscaled.

| Model | AP (%) ↑ | ECE (%) ↓ | Brier ↓ | ROC-AUC (%) ↑ |
| --- | ---: | ---: | ---: | ---: |
| ComRisk | 31.63 ± 2.75 | 22.88 ± 4.41 | 0.1376 ± 0.0288 | 86.06 ± 0.94 |
| RiskGNN | 31.93 ± 1.89 | 22.44 ± 5.94 | 0.1421 ± 0.0390 | **86.30 ± 0.93** |
| RiskGNN+ | 33.20 ± 2.88 | 21.87 ± 2.55 | 0.1210 ± 0.0248 | 86.02 ± 0.65 |
| RiskGNN++ | **35.32 ± 1.81** | **20.71 ± 3.02** | **0.1150 ± 0.0105** | 85.82 ± 0.25 |

RiskGNN++ improves mean AP by 3.69 percentage points over ComRisk and 2.12 points over RiskGNN+, while ROC-AUC is lower. Its ECE and Brier are lowest among these four implementations. These primary-head results do not by themselves demonstrate calibrated evidential uncertainty, and the remaining ECE is substantial. No significance claim is made from three seeds.

### 4.3 Fixed-budget selective prediction

**Table 3. UK automatic error on the same RiskGNN++ predictions (%).** All methods retain the same number of firms within each budget. This table comes from saved-prediction replay, not retraining.

| Review budget | Evidence uncertainty | Probability ambiguity | Ambiguity + conflict |
| ---: | ---: | ---: | ---: |
| 10% | 16.10 ± 1.27 | 13.14 ± 1.70 | **12.84 ± 1.78** |
| 20% | 15.71 ± 0.62 | 9.92 ± 2.10 | **9.45 ± 2.24** |
| 30% | 16.27 ± 0.34 | 7.38 ± 2.19 | **6.85 ± 2.34** |
| 40% | 17.32 ± 1.33 | 5.56 ± 2.03 | **5.02 ± 2.28** |
| 50% | 17.27 ± 4.59 | 4.19 ± 1.56 | **3.55 ± 1.89** |

Conflict ranking lowers mean automatic error by 0.30–0.64 percentage points across these UK budgets. The result supports an incremental ranking benefit under this protocol. It does not establish monetary benefit, prospective lending performance, or an industry-standard review budget.

### 4.4 Conformal prediction and transfer

**Table 4. Prediction-set replay using RiskGNN++ (%).** Coverage, automatic rate, and automatic error are separate metrics. Automatic populations differ across scores; their errors are not a matched-budget comparison.

| Dataset | Score | Coverage | Automatic rate | Automatic error |
| --- | --- | ---: | ---: | ---: |
| UK | Probability-only | 94.69 ± 0.58 | 70.12 ± 9.02 | 7.60 ± 0.33 |
| UK | Evidence-augmented | 94.78 ± 0.56 | 70.02 ± 9.31 | 7.48 ± 0.38 |
| UK | TACR | 94.88 ± 0.36 | 67.47 ± 8.06 | 7.61 ± 0.39 |
| SMEsD | Probability-only | 95.11 ± 1.13 | 38.83 ± 11.47 | 12.87 ± 1.88 |
| SMEsD | Evidence-augmented | 95.38 ± 0.72 | 38.63 ± 11.22 | 12.36 ± 2.16 |
| SMEsD | TACR | 95.45 ± 1.03 | 38.90 ± 10.71 | 11.86 ± 1.09 |

UK TACR slightly increases empirical coverage, while automatic error does not improve over probability-only CP. SMEsD shows lower mean automatic error with TACR. Neither result establishes a graph-dependent theorem. The original 95.38% SMEsD figure belongs to evidence-augmented CP, rather than TACR.

On SMEsD, full RiskGNN++ has AP 87.84 ± 0.47%, ROC-AUC 79.66 ± 0.28%, ECE 10.24 ± 2.14%, and Brier 0.1818 ± 0.0068. RiskGNN+ has AP 87.52 ± 1.41%, ROC-AUC 80.35 ± 1.48%, ECE 6.55 ± 0.68%, and Brier 0.1691 ± 0.0045. Thus, the full method does not improve calibration or ROC-AUC on this benchmark. Detailed ablations are retained in the supplement.

## 5. Discussion and Limitations

The strongest supported finding is that composite evidential disagreement helps rank UK classification errors beyond the same model's probability ambiguity. Scalar uncertainty performs worse for that task. This is consistent with a failure of uncertainty ranking, but does not prove that majority-neighbor evidence inflation is its cause. Class-weighted training also affects probability scale and should be separated from topological effects in further experiments.

The evidence does not establish that edge-confidence channels universally collapse, that high conflict identifies causal contagion, or that dataset differences constitute a phase transition. Shared representations weaken an independent-source interpretation of Dempster fusion. Missing-relation heads and split-dependent mean-degree scaling also deserve ablation. UK component-removal experiments, repeated data splits, held-out score selection, calibrated probability baselines, and uncertainty estimates accounting for graph dependence remain necessary.

## 6. Conclusion

RiskGNN++ combines relation-specific opinions with topology-aware discounting and degree-scaled evidence. Saved experiments show higher UK average precision and an incremental fixed-budget benefit from conflict ranking. Conformal-score replay and SMEsD results expose limits to this improvement. The current evidence supports a selective-prediction method for further evaluation, rather than a proved underwriting guarantee.

## References

1. Sensoy, M., Kaplan, L., and Kandemir, M. *Evidential Deep Learning to Quantify Classification Uncertainty*. NeurIPS, 2018. [Paper](https://arxiv.org/abs/1806.01768).
2. Han, Z., Zhang, C., Fu, H., and Zhou, J. T. *Trusted Multi-View Classification*. ICLR, 2021. [Paper](https://arxiv.org/abs/2102.02051).
3. Bengs, V., Hüllermeier, E., and Waegeman, W. *Pitfalls of Epistemic Uncertainty Quantification through Loss Minimisation*. 2022 preprint. [Paper](https://arxiv.org/abs/2203.06102).
4. Jürgens, M., et al. *Is Epistemic Uncertainty Faithfully Represented by Evidential Deep Learning Methods?* ICML, 2024. [Paper](https://arxiv.org/abs/2402.09056).
5. Angelopoulos, A. N., and Bates, S. *A Gentle Introduction to Conformal Prediction and Distribution-Free Uncertainty Quantification*. 2021, revised 2022. [Paper](https://arxiv.org/abs/2107.07511).
6. H. Zargarbashi, S., Antonelli, S., and Bojchevski, A. *Conformal Prediction Sets for Graph Neural Networks*. ICML, 2023. [Proceedings](https://proceedings.mlr.press/v202/h-zargarbashi23a.html).

[PENDING VERIFICATION] Add the exact source publications and versions for the repository's ComRisk and RiskGNN baselines; the original ComRisk bibliographic entry has not been verified.
