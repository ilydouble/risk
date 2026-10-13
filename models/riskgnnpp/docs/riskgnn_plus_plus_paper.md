# Corporate Distress Assessment with Weak Relational Evidence: A UK Graph Dataset and Conflict-Guided Review

**Anonymous Authors — Working Draft, 13 October 2026**

## Abstract

Corporate registries provide rich relational information for distress assessment, yet a recorded connection does not establish that neighboring firms share the same financial condition. This creates a reliability problem: a graph model must use relational information for prediction while identifying judgments that warrant human review. We study this problem through a UK corporate-status dataset and RiskGNN++, a model that combines attribute and graph representations with relation-specific evidential heads. The dataset integrates Companies House and GLEIF records for 233,251 firms, with four relation types and 412,348 directed edges. The model discounts and scales fused evidence using conflict and degree, and uses a composite conflict signal alongside calibrated probability ambiguity to rank predictions for review. Across ten training seeds, RiskGNN++ achieves 32.89% average precision on UK, compared with 29.01% for the implemented ComRisk baseline. On identical classifier outputs, conflict-guided ranking reduces the area under the risk–coverage curve from 0.0097 to 0.0083. This benefit is specific to the evaluated UK protocol: it is not significant at 70% automatic coverage and does not transfer to SMEsD. These findings motivate evaluating relational evidence through both predictive discrimination and its usefulness for selective review.

## 1. Introduction

A shared registered address is an observable connection between companies. Its relevance to corporate distress is less direct: the record alone does not establish an economic dependency or a common financial condition. Corporate graph models face this distinction whenever they aggregate ownership links, address matches, or name-based associations. The question is therefore not only whether relationships improve prediction, but how to assess predictions formed from relational evidence with different meanings and strengths.

This distinction matters when predictions inform a review process. A classifier ranks firms by estimated distress probability; a review score ranks its predictions by the need for further examination. These objectives differ. A high-risk firm can be classified correctly, while a low-risk prediction can conceal an error. Probability ambiguity supplies a simple review baseline, but it summarizes the final prediction without explicitly retaining the compatibility of the model's underlying opinions. We investigate whether a conflict signal derived from those opinions can improve review allocation when added to probability ambiguity.

Our study connects data construction, predictive modeling, and selective evaluation. We assemble a UK corporate-status graph from Companies House and GLEIF records, retaining four relation types and source-derived edge weights. We develop RiskGNN++ to expose node and relation-specific evidential opinions within an attribute–graph classifier. Conflict and node degree regulate auxiliary evidence fusion, while a composite conflict score augments the calibrated probability margin for review ranking. Prediction quality and review quality are evaluated separately, so that a useful review signal need not be justified by a classification improvement.

The resulting contribution has three parts:

1. **A documented UK corporate-status dataset.** The dataset contains 233,251 firms and 412,348 directed edges across three isolated graph snapshots, with address-group splitting, explicit registry-status labels, and source-derived evidence weights. It provides a setting for studying corporate assessment under class imbalance and heterogeneous relational semantics.
2. **A model connecting relational evidence to review decisions.** RiskGNN++ integrates relation-specific Dirichlet heads, conflict- and degree-based evidence discounting, and degree-scaled fusion with an existing corporate graph backbone. It exposes a separate conflict signal for review ranking, making the relation between prediction and selective review directly testable.
3. **An empirical separation of discrimination and review utility.** Ten-seed comparisons show a UK average-precision improvement over the implemented ComRisk baseline and an integrated risk–coverage improvement when conflict augments the same classifier's probability ambiguity. Within-family comparisons, fixed-coverage results, and evaluation on SMEsD delimit these findings.

The main claim is an empirical one about the complete system and the evaluated review protocol. We do not infer an independent contribution from every module or equate model conflict with observed financial contagion.

## 2. Related Work

**Corporate graph prediction.** ComRisk combines information about a firm's own condition with relational information for enterprise bankruptcy prediction [7]. It is the principal external comparison in our experiments. Our study emphasizes the additional decision of which predictions to review and develops a UK registry-based evaluation setting. RiskGNN and RiskGNN+ belong to our own research line and are included as within-family comparators; they are not independent external baselines.

**Evidential fusion and graph uncertainty.** Evidential deep learning parameterizes class evidence through a Dirichlet distribution [1], and Trusted Multi-View Classification uses evidential opinions for multi-view fusion [2]. Conflict-aware multi-view learning and trust-based discounting have also been studied [8, 9]. Graph uncertainty research includes linear opinion pooling over neighboring nodes [10]. Accordingly, Dirichlet opinions, Dempster fusion, and trust discounting are established ingredients. Our methodological contribution is their particular integration with relation-conditioned corporate representations and an explicit review score, evaluated in the proposed dataset. We assess uncertainty scores empirically because an evidential parameterization alone does not establish faithful epistemic uncertainty [3, 4].

**Selective prediction.** Selective classification evaluates errors among predictions retained for automatic processing; SelectiveNet is one example of learning prediction and rejection jointly [11]. We instead evaluate post-hoc review scores on fixed classifier predictions. Conformal prediction addresses a different output, a set of candidate labels under a coverage criterion [5, 6]. A secondary prediction-set replay is reported in the appendix, separately from our principal risk–coverage evaluation.

## 3. Dataset and Task

### 3.1 UK corporate-status graph

The UK dataset was assembled from Companies House registry records and GLEIF legal-entity relationships, with limited API supplementation for director-derived attributes. It has 233,251 firms and four relations (`SAME_ADDRESS`, `EQUITY`, `PREVNAME`, `SAME_NAME`). Its three isolated snapshots contain 412,348 directed edges in total; the 248,517/84,060/79,771 counts refer to train/validation/test snapshots, respectively. Train/validation/calibration/test sizes are 139,956/23,332/23,332/46,631; calibration is carved out of the original validation snapshot. Splitting follows address groups, and test positive prevalence is 3.42%. The positive label is a contemporaneous registry distress status, not future loan default. Same-address edge weights encode source-derived evidence strength rather than verified edge probabilities.

### 3.2 SMEsD comparison dataset

SMEsD has 3,976 firm nodes, 2,405 person nodes, and 12 relation types. Its train/validation/calibration/test sizes are 2,816/361/360/491, with 3,556 test-snapshot edges and 64.77% test positive prevalence. The published split contains overlapping firm IDs; the experiment preserves that split. This limits independence and leakage interpretations (see the supplement).

### 3.3 Prediction and selective review

Let the corporate graph be $\mathcal{G}=(\mathcal{V},\mathcal{E},\mathcal{R})$, with binary corporate-status label $y_i\in\{0,1\}$. The positive label follows each dataset's encoding; calling it a future loan default requires a documented prediction horizon and outcome definition. The primary classifier produces $\hat p_i$, and a separate review score ranks predictions for deferral.

We use “weak relational evidence” to describe the uncertain predictive relevance of a recorded connection, rather than an established error in the underlying registry record. Source-derived weights express evidence strength, not calibrated edge probabilities. Likewise, the UK sampling and labeling process defines corporate-status assessment in the assembled population; it does not establish prospective lending performance or represent every UK firm. The construction uses legal-entity anchors and same-address neighborhoods, with director-derived attributes and hyperedges supplementing pairwise relations. Acquisition and audit details are documented in the [experiment supplement](riskgnn-plus-plus-experiments.md).

## 4. RiskGNN++

### 4.1 Backbone and evidential branches

RiskGNN++ builds on our earlier RiskGNN+ model, retaining the intrinsic feature branch, five heterogeneous graph layers, enabled hypergraph processing, and a learnable mixture feeding the primary classifier. Community priors use training labels; training features use leave-one-out priors. The intrinsic branch is implemented by the inherited feature extractor, rather than a standalone MLP over raw attributes alone.

A node evidence head and an aggregate graph evidence head are retained for auxiliary supervision. The new relation heads pool final graph representations, including person representations where present. For each relation, the implementation averages incoming neighbor representations **together with the target's own representation**, dividing by relation in-degree plus one. An absent relation therefore still produces a self-based opinion, rather than an exactly vacuous source. An exponential of a linear projection clamped to $[-10,10]$ yields the relation evidence.

In binary subjective logic, $\alpha_k=e_k+1$, $S=\alpha_0+\alpha_1$, $b_k=e_k/S$, and $u=2/S$. Increasing total evidence therefore reduces $u$ algebraically; this identity alone does not establish whether the accumulated evidence is warranted. The heads are relation-specific, but their inputs share a graph backbone and include self-information. They should not be described as statistically independent evidence sources; dependence and repeated evidence are limitations of the fusion interpretation.

### 4.2 Discounting, fusion, and reported conflict

We reduce the contribution of a relation opinion when it conflicts with the node opinion and attenuate relational evidence as incoming degree increases. This is a modeling choice intended to temper accumulation from shared graph representations.

For opinions $\omega_a=(\mathbf b_a,u_a)$ and $\omega_b=(\mathbf b_b,u_b)$, binary conflict is $K(\omega_a,\omega_b)=b_{a,0}b_{b,1}+b_{a,1}b_{b,0}$. Relation $r$ is discounted using:

$$W_{i,r}=(1-K(\omega_i^{\mathrm{node}},\omega_{i,r}))^{\gamma_d}(1+d_i)^{-\eta}.$$

Here $d_i$ counts incoming edges of the considered relations, $\gamma_d=1$, and $\eta=0.25$. Discounting multiplies belief masses by $W_{i,r}$ and transfers the removed mass to uncertainty. The node opinion and discounted relation opinions are fused sequentially using Dempster's rule:

$$\mathbf b^{\mathrm{fused}}=\frac{\mathbf b_a\odot\mathbf b_b+\mathbf b_a u_b+\mathbf b_b u_a}{1-K(\omega_a,\omega_b)},\qquad u^{\mathrm{fused}}=\frac{u_a u_b}{1-K(\omega_a,\omega_b)}.$$

The reported conflict output is distinct from the sequential fusion normalizers. It is computed **before discounting** as the average of (i) mean node-to-relation pairwise conflict and (ii) mean relation-to-relation pairwise conflict. For one relation, the latter is zero. This composite output is used for RiskGNN++ triage and the appendix diagnostics; the original two-branch node-versus-graph conflict is a different quantity.

The conflict statistic measures cross-class belief mass. It is not a pure distance between predictions: identical opinions assigning positive belief to both classes can have nonzero conflict. We use it as a candidate review feature rather than a direct measure of observed relational inconsistency.

### 4.3 Degree-scaled evidence and optimization

A second degree-dependent scaling limits the amount of evidence retained after fusion. After fusion, the evidence budget is scaled as:

$$\boldsymbol\alpha_i^{\mathrm{reg}}=\mathbf1+\frac{\boldsymbol\alpha_i^{\mathrm{fused}}-\mathbf1}{1+\lambda_d d_i/(\bar d+1)},\qquad \lambda_d=0.5.$$

In the implementation, $\bar d$ is the current forward-call mean degree clamped below at one and detached from gradients. The scaling is used during both training and evaluation; reported fused probabilities and uncertainty are derived from regularized evidence. The primary probabilities remain the softmax output of the discriminative head.

The implemented objective adds primary class-weighted cross entropy, fused expected Dirichlet cross entropy (weight 0.5), node and aggregate-graph expected cross entropies (0.15 each), and fused Dirichlet KL regularization (0.001). The KL term uses $\tilde\alpha_k=y_k+(1-y_k)\alpha_k$. The evidential expected cross entropies are also class weighted. The aggregate graph head remains auxiliary and is not a separately fused source in the new multi-source combination.

The primary classifier does not directly consume the fused opinion at inference. Discounting and evidence scaling affect its parameters through shared training and auxiliary losses. Review ranking uses primary probabilities and the pre-discount composite conflict; the fused uncertainty is evaluated as a separate baseline. These distinct paths prevent a review-score improvement from identifying the effect of the fusion modules individually.

### 4.4 Calibrated conflict-guided review

Under the current class-weighted training protocol, raw probabilities are poorly calibrated. Every arm is recalibrated on the calibration split: isotonic regression on UK (23,332 points) and Platt scaling on SMEsD (360 points). Isotonic regression is nondecreasing but creates ties, which can change AP and review-score rankings. The calibration labels are reused to select the conflict weight; test labels are not used in either step.

Triage is then evaluated as a risk–coverage curve rather than a single thresholded error rate. Let $s_i$ be a review score, oriented so that larger values are deferred first. Deferring the highest-scoring firms leaves a fraction $c$ of firms processed automatically, and the selective risk $R(c)$ is the 0/1 error of those retained, using the recalibrated probability at threshold 0.5. We report the area under this curve, $\mathrm{AURC}=\int_0^1 R(c)\,\mathrm{d}c$ (lower is better), together with the risk at fixed coverage levels.

Three review scores are compared on identical predictions:

- **probability ambiguity** $0.5-|\hat p_1-0.5|$, the natural margin baseline;
- **scalar evidence uncertainty** $u$, the scalar uncertainty supplied by the fused evidential output;
- **conflict-guided ranking**, ambiguity plus $\gamma C$ with the composite conflict $C$ of Section 4.2. This is distinct from the TACR conformal score in Appendix A.

The conflict weight $\gamma$ is selected on the calibration split by minimising the calibration risk at 70% coverage, never on test; selected values range from 0.0 to 0.4 across seeds. The AURC and fixed-coverage metrics are computed on test predictions only and are paired across seeds. Review accuracy, monetary cost, and a prospective lending protocol are not modeled.

## 5. Experiments

### 5.1 Protocol

RiskGNN and RiskGNN+ are earlier methods in the same model family and serve as within-family comparators; ComRisk is a separate implemented comparison architecture. We use ten training seeds (7, 14, 21, 42, 77, 101, 314, 555, 888, 2026), 250 epochs, learning rate 0.01, cosine annealing, gradient clipping at 0.25, and checkpoint selection by validation ROC-AUC every five epochs. All seeds reuse the same data split. Values below are means ± sample standard deviations, not confidence intervals; paired comparisons across seeds report a paired $t$-test, a Wilcoxon signed-rank test, and a bootstrap 95% confidence interval of the mean difference.

### 5.2 Discrimination and probability quality

**Table 1. UK primary-head performance over ten seeds.** “PR-AUC” in the artifacts is average precision (AP), not trapezoidal area under an interpolated PR curve. ECE uses ten equal-width probability bins. AP, ECE, and ROC-AUC are percentages; Brier is unscaled.

| Model | AP (%) ↑ | ECE (%) ↓ | Brier ↓ | ROC-AUC (%) ↑ |
| --- | ---: | ---: | ---: | ---: |
| ComRisk | 29.01 ± 3.54 | 23.75 ± 4.40 | **0.1319 ± 0.0242** | 85.56 ± 0.82 |
| RiskGNN | 29.92 ± 4.10 | 25.31 ± 8.34 | 0.1478 ± 0.0446 | **85.64 ± 1.17** |
| RiskGNN+ | 32.81 ± 3.30 | 26.33 ± 5.36 | 0.1422 ± 0.0259 | 85.59 ± 1.15 |
| RiskGNN++ | **32.89 ± 4.65** | **23.11 ± 2.82** | 0.1348 ± 0.0159 | 85.56 ± 1.02 |

Over ten seeds RiskGNN++ improves raw mean AP over ComRisk by 3.88 percentage points (paired $t$ $p = 0.027$, Wilcoxon $p = 0.049$, 7/10 seeds) but is indistinguishable from RiskGNN+ (0.08 points, paired $t$ $p = 0.965$, 6/10 seeds). The corresponding **recalibrated** AP comparisons are +4.65 points ($p = 0.010$, 8/10) and +0.99 points ($p = 0.572$, 5/10). Table 1 reports raw AP; the recalibrated comparisons refer to the transformed scores. ROC-AUC, ECE and Brier differences among the evidential variants are within seed noise. The comparison supports a full-system improvement over ComRisk, but not an additional AP improvement over RiskGNN+.

Under the current class-weighted protocol, every arm overpredicts positives on UK: raw Brier (0.1319–0.1478) exceeds a constant base-rate predictor (0.0330), and raw accuracy (0.78–0.81) is below always predicting negative (0.9658). Isotonic recalibration fit on the calibration split reduces Brier to 0.0276–0.0285 and ECE to 0.0060–0.0091; accuracy rises to 0.966–0.968. This does not isolate class weighting as the cause. Because isotonic ties alter AP, raw and recalibrated AP are reported separately. Decision-level metrics below use recalibrated probabilities.

### 5.3 Recalibrated risk–coverage triage

**Table 2. UK recalibrated risk–coverage triage over ten seeds.** Selective 0/1 error of the automatically processed firms after isotonic recalibration on the calibration split; lower is better. AURC integrates the risk–coverage curve over automatic coverage $c\in[0,1]$.

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

Scalar evidential uncertainty is a substantially worse review score than the probability margin at the measured coverage levels. Adding conflict produces a small AURC reduction, significant under the reported paired tests, concentrated at low automatic coverage. Two seeds select $\gamma=0$ and tie the baseline. The 70% coverage improvement is not significant. UK isotonic calibration leaves 99.7–99.9% of ambiguity scores in tied groups; the baseline breaks ties by saved input order. In a sensitivity check averaging 30 random input permutations per seed, mean baseline AURC is 0.0096 versus 0.0083 for conflict ranking, which is better in eight seeds and tied with the deterministic baseline in two. This does not remove all tie-breaking dependence or selection bias from tuning $\gamma$ on the same calibration labels used to fit isotonic regression. Monetary cost and prospective lending performance remain unmodeled.

### 5.4 Evaluation on SMEsD

On SMEsD over ten seeds, RiskGNN++ has AP 87.79 ± 1.25%, ROC-AUC 80.24 ± 1.30%, ECE 9.77 ± 1.77%, and Brier 0.1793 ± 0.0069; RiskGNN+ has AP 87.74 ± 1.60%, ROC-AUC 80.26 ± 2.43%, ECE 7.58 ± 1.70%, and Brier 0.1720 ± 0.0083. Paired differences are not significant on these metrics (AP $p = 0.95$, ROC-AUC $p = 0.98$). SMEsD ECE changes from 9.77% to 8.26% after Platt scaling; these data do not identify the cause of residual miscalibration. Conflict-guided ranking has higher mean AURC than the probability margin (0.1479 vs 0.1443, paired $p = 0.063$); scalar evidence uncertainty is worse still (0.2021). Two datasets cannot establish which graph or prevalence property controls transfer.

## 6. Discussion and Limitations

The results separate two roles of relational modeling. First, the complete system improves UK average precision over the implemented ComRisk comparison. Second, conflict adds information useful to the evaluated UK review ranking, even though RiskGNN++ has no established AP improvement over RiskGNN+. This distinction supports studying review utility alongside discrimination. It does not show that the score identifies errors independently of probability, degree, or other correlates, nor that each evidential module contributes to the observed gain.

**Scope of the review result.** The UK AURC reduction is modest and depends on a protocol using isotonic calibration, extensive tied scores, and calibration-label reuse for score selection. It does not establish a calibration-independent effect. The fixed 70% automatic-coverage comparison is not significant, and the result does not transfer to SMEsD. Selective 0/1 error also weights false positives and false negatives equally despite UK class imbalance. Human reviewer accuracy, review cost, and deployment outcomes are outside this evaluation.

**Interpretation of evidence.** Relation heads share graph representations and include self-information even when a relation is absent. Their opinions are therefore neither independent sources nor observations of separate financial mechanisms. Dempster conflict mixes cross-class ambiguity with differences between opinions. Degree scaling constrains the model's evidence parameterization but has not been shown to correct evidence inflation. Component-removal results are needed to attribute gains to discounting, fusion, or scaling individually; the current comparison evaluates the complete design.

**Data and statistical scope.** UK labels describe contemporaneous registry status in a source-selected population. SMEsD retains overlapping firm IDs from its published split. All ten seeds reuse the same data partition, so reported variability and paired tests describe training randomness on these fixed datasets rather than uncertainty over new populations or graph samples. The external comparison is a repository implementation of ComRisk, not an exhaustive comparison with corporate prediction or uncertainty methods. Prediction-set coverage in the appendix is empirical because the protocol does not establish exchangeability under graph dependence.

## 7. Conclusion

This study treats corporate graph assessment as both a prediction task and a selective-review task. We construct a UK corporate-status dataset and introduce RiskGNN++ to expose relational evidence within a corporate graph classifier. The complete system improves UK average precision over the implemented ComRisk comparison, and adding conflict to probability ambiguity improves integrated review performance under the evaluated UK protocol. The absence of an additional within-family AP gain, a significant fixed-budget gain, or transfer to SMEsD defines the scope of these findings. The dataset and evaluation provide a basis for studying when relational information helps determine which corporate predictions deserve review.

## References

1. Sensoy, M., Kaplan, L., and Kandemir, M. *Evidential Deep Learning to Quantify Classification Uncertainty*. NeurIPS, 2018. [Paper](https://arxiv.org/abs/1806.01768).
2. Han, Z., Zhang, C., Fu, H., and Zhou, J. T. *Trusted Multi-View Classification*. ICLR, 2021. [Paper](https://arxiv.org/abs/2102.02051).
3. Bengs, V., Hüllermeier, E., and Waegeman, W. *Pitfalls of Epistemic Uncertainty Quantification through Loss Minimisation*. 2022 preprint. [Paper](https://arxiv.org/abs/2203.06102).
4. Jürgens, M., et al. *Is Epistemic Uncertainty Faithfully Represented by Evidential Deep Learning Methods?* ICML, 2024. [Paper](https://arxiv.org/abs/2402.09056).
5. Angelopoulos, A. N., and Bates, S. *A Gentle Introduction to Conformal Prediction and Distribution-Free Uncertainty Quantification*. 2021, revised 2022. [Paper](https://arxiv.org/abs/2107.07511).
6. H. Zargarbashi, S., Antonelli, S., and Bojchevski, A. *Conformal Prediction Sets for Graph Neural Networks*. ICML, 2023. [Proceedings](https://proceedings.mlr.press/v202/h-zargarbashi23a.html).
7. Wei, S., et al. *Combining Intra-Risk and Contagion Risk for Enterprise Bankruptcy Prediction Using Graph Neural Networks*. Information Sciences, 2024, 120081. [DOI](https://doi.org/10.1016/j.ins.2023.120081); [author repository](https://github.com/shaopengw/ComRisk).
8. Xu, C., et al. *Reliable Conflictive Multi-View Learning*. AAAI, 2024. [Paper](https://arxiv.org/abs/2402.16897).
9. Lu, J., et al. *Navigating Conflicting Views: Harnessing Trust for Learning*. ICML, 2025. [Paper and version history](https://arxiv.org/abs/2406.00958).
10. Damke, C., and Hüllermeier, E. *Linear Opinion Pooling for Uncertainty Quantification on Graphs*. UAI, 2024. [Proceedings](https://proceedings.mlr.press/v244/damke24a.html).
11. Geifman, Y., and El-Yaniv, R. *SelectiveNet: A Deep Neural Network with an Integrated Reject Option*. ICML, 2019. [Proceedings](https://proceedings.mlr.press/v97/geifman19a.html).

## Supplementary Material

[Appendix: evidence diagnostics and prediction-set replay](riskgnnpp-paper-appendix.md). [Experimental protocol and artifact audit](riskgnn-plus-plus-experiments.md).
