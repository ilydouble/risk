# coding: utf-8
"""Offline metrics for the dumped test/valid predictions: ranking + calibration, raw and
post-hoc calibrated.

Why calibration is needed here: the training runs use --use_class_weight, which reweights the
loss by w1/w0 ~= 47x on this data. That is deliberate (2.1% positives) and it leaves the
rank-based metrics untouched (ROC/KS/AP depend only on ordering), but it systematically inflates
the predicted probabilities -- e.g. the raw model puts ~0.55 on companies whose observed distress
rate is ~0.02. Brier and the calibration curve are therefore bad *by construction*, not because
the ranking is bad.

The fix is post-hoc and needs no retraining: fit a 2-parameter monotone map
    p_cal = sigmoid(a * s + b)          (s = dumped log-probability)
on the VALIDATION fold, then apply it to the test fold. Both the raw and the calibrated numbers
are reported so nothing is hidden.

Usage:  python compute_metrics.py
Writes: results_metrics_summary.txt
"""
import glob
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from train_sg_neighbor import (  # noqa: E402
    brier_score, brier_skill_score, calibration_curve, capture_at_frac, lift_at_frac,
    proba_from_logprob,
)

PRED_DIR = 'preds'
OUT = 'results_metrics_summary.txt'
LABELS = ['node_only', 'node_edge', 'node_edge_no_liq', 'node_edge_addrtype']
SEEDS = [0, 1, 2]


def platt_fit(s_valid, y_valid):
    """Fit p = sigmoid(a*s + b) by 1-D logistic regression on the validation fold."""
    from sklearn.linear_model import LogisticRegression
    lr = LogisticRegression(C=1e6, solver='lbfgs', max_iter=1000)
    lr.fit(np.asarray(s_valid).reshape(-1, 1), np.asarray(y_valid).astype(int))
    a = float(lr.coef_[0][0])
    b = float(lr.intercept_[0])
    return a, b


def platt_apply(s, a, b):
    return 1.0 / (1.0 + np.exp(-(a * np.asarray(s, dtype=np.float64) + b)))


def metrics_block(true, logprob, proba):
    return {
        'capture@5%': capture_at_frac(true, logprob, 0.05),
        'lift@10%': lift_at_frac(true, logprob, 0.10),
        'brier': brier_score(true, proba),
        'bss': brier_skill_score(true, proba),
    }


def fmt(vals):
    vals = [v for v in vals if v == v]  # drop NaN
    if not vals:
        return '     n/a     '
    return '%7.4f±%.4f' % (float(np.mean(vals)), float(np.std(vals, ddof=1)) if len(vals) > 1 else 0.0)


def main():
    rows = []
    for label in LABELS:
        per_seed = {'raw': [], 'cal': []}
        for seed in SEEDS:
            path = os.path.join(PRED_DIR, '%s_seed%d.npz' % (label, seed))
            if not os.path.exists(path):
                continue
            d = np.load(path)
            tl, tt = d['test_logprob'], d['test_true']
            vl, vt = d['valid_logprob'], d['valid_true']

            per_seed['raw'].append(metrics_block(tt, tl, d['test_proba']))
            a, b = platt_fit(vl, vt)
            cal_test = platt_apply(tl, a, b)
            m = metrics_block(tt, tl, cal_test)
            m['a'], m['b'] = a, b
            per_seed['cal'].append(m)

        if not per_seed['raw']:
            rows.append((label, None, None, 0))
            continue
        rows.append((label, per_seed['raw'], per_seed['cal'], len(per_seed['raw'])))

    lines = []
    lines.append('Ranking + calibration metrics (test fold; mean +/- std over seeds)')
    lines.append('')
    lines.append('%-22s %-4s %-16s %-15s %-16s %-14s' % (
        'job', 'seed', 'Capture@5%', 'Lift@10%', 'Brier', 'BSS'))
    lines.append('-' * 100)
    for label, raw, cal, n in rows:
        if raw is None:
            lines.append('%-22s  MISSING' % label)
            continue
        lines.append('%-22s %-4s %-16s %-15s %-16s %-14s' % (
            label, 'raw', fmt([r['capture@5%'] for r in raw]),
            fmt([r['lift@10%'] for r in raw]), fmt([r['brier'] for r in raw]),
            fmt([r['bss'] for r in raw])))
        lines.append('%-22s %-4s %-16s %-15s %-16s %-14s' % (
            label, 'cal', fmt([r['capture@5%'] for r in cal]),
            fmt([r['lift@10%'] for r in cal]), fmt([r['brier'] for r in cal]),
            fmt([r['bss'] for r in cal])))
        lines.append('%-22s      Platt a=%.3f b=%.3f  (fit on validation, applied to test)' % (
            '', float(np.mean([r['a'] for r in cal])), float(np.mean([r['b'] for r in cal]))))
        lines.append('')
    # The constant-predictor reference that makes Brier interpretable at this base rate.
    rates = []
    for s in SEEDS:
        pth = os.path.join(PRED_DIR, '%s_seed%d.npz' % (LABELS[0], s))
        if os.path.exists(pth):
            rates.append(float(np.load(pth)['test_true'].mean()))
    if rates:
        p = float(np.mean(rates))
        lines.append('Reference: always predicting the base rate p = %.4f gives Brier = p(1-p) = %.6f '
                     '(BSS = 0).' % (p, p * (1 - p)))
        lines.append('At this base rate a constant predictor ALREADY passes "Brier <= 0.10", so that'
                     ' threshold carries no information -- BSS is the number to quote.')
    lines.append('BSS: 1 = perfect, 0 = no better than a constant, negative = worse than a constant.')
    lines.append('Targets: Capture@5% >= 0.50 (random = 0.05) | Lift@10% >= 3 (random = 1) |'
                 ' Brier <= 0.10 (constant = p(1-p), see above).')
    lines.append('"raw" = model output as-is; "cal" = Platt-recalibrated on validation.')
    lines.append('Rank-based Capture/Lift are identical for raw and calibrated by construction.')

    # per-seed detail for the best-effort variant, plus its calibration curve
    best = 'node_edge_no_liq'
    p = os.path.join(PRED_DIR, '%s_seed0.npz' % best)
    if os.path.exists(p):
        d = np.load(p)
        a, b = platt_fit(d['valid_logprob'], d['valid_true'])
        for tag, proba in (('raw', d['test_proba']), ('cal', platt_apply(d['test_logprob'], a, b))):
            lines.append('')
            lines.append('%s seed0 calibration curve (%s):' % (best, tag))
            for r in calibration_curve(d['test_true'], proba):
                if r['count']:
                    lines.append('  bin%02d [%.1f,%.1f) n=%-6d pred=%.4f obs=%.4f' % (
                        r['bin'], r['lo'], r['hi'], r['count'],
                        r['mean_prediction'], r['observed_rate']))

    text = '\n'.join(lines)
    print(text)
    with open(OUT, 'w', encoding='utf-8') as f:
        f.write(text + '\n')
    print('\nwritten -> %s' % OUT)


if __name__ == '__main__':
    main()
