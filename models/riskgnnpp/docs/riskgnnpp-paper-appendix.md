# Supplementary Material

For [Corporate Distress Assessment with Weak Relational Evidence](riskgnn_plus_plus_paper.md). Numbered citations refer to the main paper’s reference list.

## Appendix A. Secondary prediction-set evaluation

We call the conformal component **Topology-Aware Conformal Risk Auditor (TACR)**, following the implementation. For candidate class $k$, it uses:

$$E(x,k)=1-\hat p_k(x)+\gamma_c C(x)+\beta_c u(x).$$

The replay uses $\gamma_c=0.6$, $\beta_c=0.05$, and nominal miscoverage $\epsilon=0.05$. The probability is the raw primary output; no temperature or isotonic probability calibration was applied. Calibration selects the $\lceil(n_{\mathrm{cal}}+1)(1-\epsilon)\rceil$-th smallest true-label score, with an infinite threshold if the rank exceeds the calibration size. The prediction set contains all classes whose scores do not exceed this threshold.

Singleton sets produce automatic predictions; two-class sets are deferred. Empty sets are reported separately. An empty set alone does not establish an out-of-distribution observation, despite the implementation's `OOD_ALERT` action name.

The standard finite-sample marginal coverage statement requires exchangeability of calibration and test scores under an appropriate fixed-model protocol [5, 6]. It does not require independence as a separate assumption. Adding conflict to the score does not establish exchangeability or repair arbitrary graph dependence. The current optional `network_inflation` subtracts a user-specified quantity from epsilon; `max_degree` is unused and there is no implemented graph-dependence bound. All coverage here is empirical.

The principal risk–coverage evaluation uses calibrated probabilities. We additionally replay the conformal auditor, which operates on uncalibrated probabilities and produces prediction sets rather than a ranked budget, as a secondary check on the same predictions.

**Table A1. Prediction-set replay using RiskGNN++ (%).** Three-seed replay; this secondary check has not been extended to ten seeds. Coverage, automatic rate, and automatic error are separate metrics. Automatic populations differ across scores; their errors are not a matched-budget comparison.

| Dataset | Score | Coverage | Automatic rate | Automatic error |
| --- | --- | ---: | ---: | ---: |
| UK | Probability-only | 94.69 ± 0.58 | 70.12 ± 9.02 | 7.60 ± 0.33 |
| UK | Evidence-augmented | 94.78 ± 0.56 | 70.02 ± 9.31 | 7.48 ± 0.38 |
| UK | TACR | 94.88 ± 0.36 | 67.47 ± 8.06 | 7.61 ± 0.39 |
| SMEsD | Probability-only | 95.11 ± 1.13 | 38.83 ± 11.47 | 12.87 ± 1.88 |
| SMEsD | Evidence-augmented | 95.38 ± 0.72 | 38.63 ± 11.22 | 12.36 ± 2.16 |
| SMEsD | TACR | 95.45 ± 1.03 | 38.90 ± 10.71 | 11.86 ± 1.09 |

UK TACR slightly increases empirical coverage, while automatic error does not improve over probability-only CP. SMEsD shows lower mean automatic error with TACR. Neither result establishes a graph-dependent theorem.

## Appendix B. Exploratory conflict diagnostics

The saved UK diagnostics partition RiskGNN++ predictions by its composite conflict output (defined in Section 4.2 of the main paper). Table A2 reports classification error at a primary probability threshold of 0.5, not observed default prevalence.

**Table A2. UK classification error by conflict quartile.** Ratios use unrounded rates; the large ratios partly reflect small low-conflict denominators.

| Seed | Highest quartile error (%) | Lowest quartile error (%) | Ratio | Pearson correlation with error |
| ---: | ---: | ---: | ---: | ---: |
| 14 | 29.39 | 2.08 | 14.2× | 0.2561 |
| 42 | 35.92 | 0.44 | 82.1× | 0.3625 |
| 2026 | 33.27 | 0.48 | 69.3× | 0.3464 |

Conflict is a statistic of model belief masses, rather than risk magnitude or verified contagion; it includes within-opinion ambiguity as well as differences between opinions. Its Pearson correlation with label-derived neighborhood heterophily is only 0.040–0.071 in the same diagnostics. These associations do not identify whether disagreements arise from noisy relations, feature inadequacy, class weighting, or contagion.

These diagnostics use the original three seeds and raw primary probabilities. They are descriptive associations, not ten-seed conditional-error analyses or evidence of a causal mechanism.
