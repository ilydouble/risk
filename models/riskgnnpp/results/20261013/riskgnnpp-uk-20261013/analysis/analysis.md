# Analysis: uk (3 seeds)

Seeds: [14, 42, 2026]
Recalibration: `isotonic` on the calibration split.

## Raw vs recalibrated metrics

### comrisk

| Metric | Raw | Recalibrated |
| --- | --- | --- |
| rocAuc | 0.8606 ± 0.0094 | 0.8594 ± 0.0097 |
| prAuc | 0.3163 ± 0.0275 | 0.2743 ± 0.0419 |
| ece | 0.2288 ± 0.0441 | 0.0089 ± 0.0042 |
| brier | 0.1376 ± 0.0288 | 0.0279 ± 0.0007 |
| accuracy | 0.7958 ± 0.0462 | 0.9670 ± 0.0011 |

### riskgnn

| Metric | Raw | Recalibrated |
| --- | --- | --- |
| rocAuc | 0.8630 ± 0.0093 | 0.8617 ± 0.0100 |
| prAuc | 0.3193 ± 0.0189 | 0.2873 ± 0.0320 |
| ece | 0.2244 ± 0.0594 | 0.0084 ± 0.0030 |
| brier | 0.1421 ± 0.0390 | 0.0279 ± 0.0006 |
| accuracy | 0.7932 ± 0.0545 | 0.9677 ± 0.0011 |

### plus

| Metric | Raw | Recalibrated |
| --- | --- | --- |
| rocAuc | 0.8602 ± 0.0065 | 0.8586 ± 0.0075 |
| prAuc | 0.3320 ± 0.0288 | 0.3065 ± 0.0269 |
| ece | 0.2187 ± 0.0255 | 0.0071 ± 0.0024 |
| brier | 0.1210 ± 0.0248 | 0.0274 ± 0.0004 |
| accuracy | 0.8308 ± 0.0388 | 0.9680 ± 0.0005 |

### plusplus

| Metric | Raw | Recalibrated |
| --- | --- | --- |
| rocAuc | 0.8582 ± 0.0025 | 0.8573 ± 0.0025 |
| prAuc | 0.3532 ± 0.0181 | 0.3292 ± 0.0150 |
| ece | 0.2071 ± 0.0302 | 0.0056 ± 0.0028 |
| brier | 0.1150 ± 0.0105 | 0.0270 ± 0.0004 |
| accuracy | 0.8359 ± 0.0142 | 0.9681 ± 0.0007 |

## Triage (risk--coverage, recalibrated)

### plus (gamma per seed: [0.1, 0.1, 0.1])

| Signal | AURC ↓ | Risk@0.5 ↓ | Risk@0.6 ↓ | Risk@0.7 ↓ | Risk@0.8 ↓ | Risk@0.9 ↓ |
| --- | --- | --- | --- | --- | --- | --- |
| softmax | 0.0092 | 0.0064 | 0.0070 | 0.0083 | 0.0106 | 0.0151 |
| naive_edl | 0.0543 | 0.0449 | 0.0410 | 0.0380 | 0.0352 | 0.0333 |
| tacr | 0.0079 | 0.0062 | 0.0072 | 0.0082 | 0.0106 | 0.0153 |

### plusplus (gamma per seed: [0.4, 0.4, 0.4])

| Signal | AURC ↓ | Risk@0.5 ↓ | Risk@0.6 ↓ | Risk@0.7 ↓ | Risk@0.8 ↓ | Risk@0.9 ↓ |
| --- | --- | --- | --- | --- | --- | --- |
| softmax | 0.0105 | 0.0076 | 0.0082 | 0.0093 | 0.0111 | 0.0151 |
| naive_edl | 0.0422 | 0.0382 | 0.0362 | 0.0342 | 0.0331 | 0.0327 |
| tacr | 0.0082 | 0.0064 | 0.0072 | 0.0085 | 0.0107 | 0.0154 |

## Paired significance across seeds

| Comparison | mean diff | 95% CI | paired t p | Wilcoxon p | wins |
| --- | --- | --- | --- | --- | --- |
| PR-AUC: RiskGNN++ vs RiskGNN+ | +0.0227 | [-0.0096, +0.0424] | 0.2976 | 0.5000 | 2/3 |
| ROC-AUC: RiskGNN++ vs RiskGNN+ | -0.0013 | [-0.0070, +0.0036] | 0.7072 | 0.7500 | 1/3 |
| ECE: RiskGNN++ vs RiskGNN+ | -0.0015 | [-0.0067, +0.0014] | 0.6258 | 1.0000 | 2/3 |
| Brier: RiskGNN++ vs RiskGNN+ | -0.0004 | [-0.0009, +0.0001] | 0.2898 | 0.5000 | 1/3 |
| PR-AUC: RiskGNN++ vs ComRisk | +0.0549 | [+0.0278, +0.0981] | 0.1283 | 0.2500 | 3/3 |
| AURC: TACR vs Softmax | -0.0023 | [-0.0031, -0.0019] | 0.0265 | 0.2500 | 0/3 |
| AURC: TACR vs naive EDL | -0.0340 | [-0.0469, -0.0155] | 0.0699 | 0.2500 | 0/3 |
| Risk@0.7: TACR vs Softmax | -0.0008 | [-0.0014, +0.0004] | 0.3113 | 0.5000 | 1/3 |
| Risk@0.7: TACR vs naive EDL | -0.0256 | [-0.0278, -0.0214] | 0.0067 | 0.2500 | 0/3 |
