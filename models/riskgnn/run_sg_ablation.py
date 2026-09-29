# coding: utf-8
"""Batch driver for Wang's 3-way graph ablation (node_only / node_hyper /
node_hyper_edge), full-scale Singapore data, her frozen splits, matching her own
suggested scale (`baseline_ablation.py --epochs 30 --seeds 3`).

Robust by design (the earlier SMEsD 5-seed batch died from this): every run is
wrapped in try/except, a failure is logged and the batch CONTINUES to the next
run instead of crashing silently. Writes each result the moment it's available
(flushed), and writes a distinct ERROR_OCCURRED marker line the instant any run
fails, so a watcher process can notice within seconds rather than only at the
very end.
"""
import subprocess, sys, time

ABLATIONS = ['node_only', 'node_hyper']  # node_hyper_edge excluded: ~141s/epoch
# (14x slower than node_hyper's ~10s/epoch, would add ~3.5h for 30 epochs x 3
# seeds), and matches Wang's own diagnosis that the edge graph carries almost no
# signal (0.09% distress-distress edges, 96.2% of labeled nodes isolated).
# Run it separately, at a reduced epoch count, only if node_hyper's result
# specifically calls for it.
SEEDS = [0, 1, 2]
N_EPOCH = 30
TIMEOUT_S = 1800  # both remaining ablations run in well under this per-seed

with open('results_sg_ablation.txt', 'w', encoding='utf-8') as f:
    f.write('ablation\tseed\tfinal_test_line\telapsed_s\n')
    f.flush()
    for ablation in ABLATIONS:
        for seed in SEEDS:
            t0 = time.time()
            cmd = [sys.executable, '-u', 'train_sg_ablation.py',
                   '--ablation', ablation, '--n_epoch', str(N_EPOCH),
                   '--seed', str(seed), '--use_class_weight', '--device', 'cuda']
            print('[%s seed=%d] running' % (ablation, seed), flush=True)
            try:
                out = subprocess.run(cmd, capture_output=True, text=True,
                                      timeout=TIMEOUT_S, encoding='utf-8', errors='replace')
                lines = out.stdout.splitlines()
                final_line = next((l for l in lines if l.startswith('FINAL TEST') or 'FINAL TEST' in l), None)
                if final_line is None:
                    final_line = 'ERROR: no FINAL TEST line. stderr tail: ' + out.stderr[-500:].replace('\n', ' | ')
                    print('ERROR_OCCURRED: %s seed=%d produced no result' % (ablation, seed), flush=True)
            except subprocess.TimeoutExpired:
                final_line = 'ERROR: TIMEOUT after %ds' % TIMEOUT_S
                print('ERROR_OCCURRED: %s seed=%d TIMED OUT after %ds' % (ablation, seed, TIMEOUT_S), flush=True)
            except Exception as e:
                final_line = 'ERROR: %s: %s' % (type(e).__name__, e)
                print('ERROR_OCCURRED: %s seed=%d raised %s: %s' % (ablation, seed, type(e).__name__, e), flush=True)
            elapsed = time.time() - t0
            f.write('%s\t%d\t%s\t%.1f\n' % (ablation, seed, final_line, elapsed))
            f.flush()
            print('  -> %s (%.1fs)' % (final_line, elapsed), flush=True)
print('DONE', flush=True)
