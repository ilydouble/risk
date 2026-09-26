# coding: utf-8
"""Robust batch driver for the node_only vs node_edge (neighbor-sampling) test,
3 seeds x 2 variants. Every run is wrapped in try/except so one failure can't
silently hang or kill the whole batch (lesson from the SMEsD 5-seed batch crash,
2026-09-25). Writes each result the moment it's ready (flushed), and prints a
distinct ERROR_OCCURRED line the instant any run fails or times out, so a
watcher notices immediately rather than only at the very end.
"""
import subprocess, sys, time

VARIANTS = ['node_only', 'node_edge']
SEEDS = [0, 1, 2]
N_EPOCH = 10
BATCH_SIZE = 2048
NUM_WORKERS = 8
TIMEOUT_S = 3600  # generous vs. the ~20min/run observed

with open('results_sg_neighbor.txt', 'w', encoding='utf-8') as f:
    f.write('variant\tseed\tfinal_test_line\telapsed_s\n')
    f.flush()
    for variant in VARIANTS:
        for seed in SEEDS:
            t0 = time.time()
            cmd = [sys.executable, '-u', 'train_sg_neighbor.py',
                   '--variant', variant, '--n_epoch', str(N_EPOCH), '--seed', str(seed),
                   '--use_class_weight', '--batch_size', str(BATCH_SIZE),
                   '--num_workers', str(NUM_WORKERS), '--device', 'cpu']
            print('[%s seed=%d] running' % (variant, seed), flush=True)
            try:
                out = subprocess.run(cmd, capture_output=True, text=True,
                                      timeout=TIMEOUT_S, encoding='utf-8', errors='replace')
                lines = out.stdout.splitlines()
                final_line = next((l for l in lines if 'FINAL TEST' in l), None)
                if final_line is None:
                    final_line = 'ERROR: no FINAL TEST line. stderr tail: ' + out.stderr[-800:].replace('\n', ' | ')
                    print('ERROR_OCCURRED: %s seed=%d produced no result' % (variant, seed), flush=True)
            except subprocess.TimeoutExpired:
                final_line = 'ERROR: TIMEOUT after %ds' % TIMEOUT_S
                print('ERROR_OCCURRED: %s seed=%d TIMED OUT after %ds' % (variant, seed, TIMEOUT_S), flush=True)
            except Exception as e:
                final_line = 'ERROR: %s: %s' % (type(e).__name__, e)
                print('ERROR_OCCURRED: %s seed=%d raised %s: %s' % (variant, seed, type(e).__name__, e), flush=True)
            elapsed = time.time() - t0
            f.write('%s\t%d\t%s\t%.1f\n' % (variant, seed, final_line, elapsed))
            f.flush()
            print('  -> %s (%.1fs)' % (final_line, elapsed), flush=True)
print('DONE', flush=True)
