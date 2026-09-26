# coding: utf-8
"""Final Protocol A batch: RiskGNN, 5 seeds, 100 epochs each, her frozen splits.
Reference to beat: 0.8741 +/- 0.0017 (her logistic regression)."""
import subprocess, sys, time

with open('results_protocol_a.txt', 'w', encoding='utf-8') as f:
    f.write('seed\tfinal_test_line\telapsed_s\n')
    f.flush()
    for seed in range(5):
        t0 = time.time()
        cmd = [sys.executable, '-u', 'train_protocol_a.py', '--n_epoch', '100',
               '--seed', str(seed), '--use_class_weight']
        print('[seed=%d] running' % seed, flush=True)
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=900,
                              encoding='utf-8', errors='replace')
        lines = [l for l in out.stdout.splitlines() if 'FINAL TEST' in l]
        final = lines[-1] if lines else ('ERROR: ' + out.stderr[-800:])
        elapsed = time.time() - t0
        f.write('%d\t%s\t%.1f\n' % (seed, final, elapsed))
        f.flush()
        print('  -> %s (%.1fs)' % (final, elapsed), flush=True)
print('DONE', flush=True)
