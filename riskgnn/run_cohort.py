# coding: utf-8
"""Same-cohort design (2014 registration year), age excluded, 3 seeds --
the "most honest" number per Wang Xiaoxiao's LEAKAGE_REPORT.md recommendation."""
import subprocess, sys, time

with open('results_cohort.txt', 'w', encoding='utf-8') as f:
    f.write('seed\tfinal_test_line\telapsed_s\n')
    f.flush()
    for seed in [0, 1, 2]:
        t0 = time.time()
        cmd = [sys.executable, '-u', 'train_sg.py', '--max_companies', '1000000',
               '--n_epoch', '100', '--ablation', 'node_only', '--prior_source', 'bayesian',
               '--use_class_weight', '--exclude_age', '--cohort_year', '2014', '--seed', str(seed)]
        print('[seed=%d] running' % seed, flush=True)
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        lines = [l for l in out.stdout.splitlines() if 'FINAL TEST' in l]
        final = lines[-1] if lines else ('ERROR: ' + out.stderr[-500:])
        elapsed = time.time() - t0
        f.write('%d\t%s\t%.1f\n' % (seed, final, elapsed))
        f.flush()
        print('  -> %s (%.1fs)' % (final, elapsed), flush=True)
print('DONE', flush=True)
