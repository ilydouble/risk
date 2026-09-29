# coding: utf-8
"""One batch: the three original variants re-run with test-fold prediction dumping (so the
ranking + calibration metrics can be computed), plus Wang's new `edges_by_addr_type.parquet`
as a fourth variant.

Why one batch instead of several: the training config is identical for every job, so the only
per-job differences are --variant / --edges_file / the dump path. Running them together avoids
re-loading the 2.1M-node export and re-spinning the worker pool four times.

Every job uses the SAME protocol as the earlier runs except `--num_workers` (4 here, 8 earlier --
output-neutral, see NUM_WORKERS below): 10 epochs, batch 2048, fanout 10, 5 hops, 3 seeds, GPU,
--use_class_weight. The `FINAL TEST:` line must therefore reproduce the previously reported
ROC/KS/AP exactly -- that is the integrity check. Any drift is written into the results file
rather than silently accepted.

Outputs:
    results_metrics_batch.txt      one row per (job, seed): FINAL TEST + FINAL METRICS lines
    preds/<job>_seed<k>.npz        logprob / proba / true / pred for the test fold
    run_<job>_seed<k>.log          full stdout per run
"""
import os
import subprocess
import sys
import time

try:
    import psutil
except ImportError:
    psutil = None

DATA_DIR = 'data_sg_v7/comrisk_export'
NO_LIQ = os.path.join(DATA_DIR, 'edges_no_liq.parquet')
ADDR_TYPE = os.path.join(DATA_DIR, 'edges_by_addr_type.parquet')

OUT = 'results_metrics_batch.txt'
PRED_DIR = 'preds'
SEEDS = [0, 1, 2]
N_EPOCH = 10
BATCH_SIZE = 2048
NUM_WORKERS = 4   # measured 2026-09-27 on this box (node_edge, 1 epoch): 8 -> 8.39 GB peak /
                  # 192 s, 5 -> 7.27 GB / 178 s, 4 -> 6.88 GB / 180 s. Fewer workers is definitely
                  # lighter. On a SINGLE epoch it also looked no slower -- but over a full
                  # 10-epoch run the edge variants are ~16% SLOWER with 4 than with 8
                  # (node_edge 1251 s vs 1071 s), which is why this batch took 3.35 h rather than
                  # the ~2 h originally estimated. That cost is deliberate, not free: free RAM here
                  # is only ~5 GB and 8 workers had already produced a MemoryError. Results are
                  # bit-identical either way (verified: 9/9 comparable runs reproduce exactly).
DEVICE = 'cuda'
TIMEOUT_S = 5400
ATTEMPTS = 3          # a MemoryError here is transient (RAM headroom), so retry the job
RETRY_SLEEP_S = 20

# (job label, --variant, --edges_file)
JOBS = [
    ('node_only',           'node_only', None),
    ('node_edge',           'node_edge', None),
    ('node_edge_no_liq',    'node_edge', NO_LIQ),
    ('node_edge_addrtype',  'node_edge', ADDR_TYPE),
]

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass


def free_gb():
    """Available RAM in GB, or None if psutil is unavailable."""
    return None if psutil is None else psutil.virtual_memory().available / 1e9


def run_one(label, variant, edges_file, seed):
    cmd = [sys.executable, '-u', 'train_sg_neighbor.py',
           '--variant', variant, '--n_epoch', str(N_EPOCH), '--seed', str(seed),
           '--use_class_weight', '--batch_size', str(BATCH_SIZE),
           '--num_workers', str(NUM_WORKERS), '--device', DEVICE,
           '--data_dir', DATA_DIR]
    if edges_file:
        cmd += ['--edges_file', edges_file]
    dump = os.path.join(PRED_DIR, '%s_seed%d.npz' % (label, seed))
    cmd += ['--dump_preds', dump]

    last_err = 'ERROR: not attempted'
    for attempt in range(1, ATTEMPTS + 1):
        fg = free_gb()
        print('  [%s seed=%d] attempt %d/%d%s' % (
            label, seed, attempt, ATTEMPTS,
            ('  (free RAM %.1f GB)' % fg) if fg is not None else ''), flush=True)
        log = 'run_%s_seed%d.log' % (label, seed)
        try:
            with open(log, 'w', encoding='utf-8') as lf:
                subprocess.run(cmd, stdout=lf, stderr=subprocess.STDOUT,
                               timeout=TIMEOUT_S, encoding='utf-8', errors='replace')
            lines = open(log, encoding='utf-8', errors='replace').read().splitlines()
            test_line = next((l for l in lines if 'FINAL TEST' in l), None)
            metrics_line = next((l for l in lines if 'FINAL METRICS' in l), None)
            if test_line is not None:
                return test_line, (metrics_line or 'ERROR: no FINAL METRICS line')
            tail = ' | '.join(lines[-4:])[-400:]
            last_err = 'ERROR: no FINAL TEST line (tail: %s)' % tail
            # A MemoryError inside a pool worker surfaces here as a crash with no result.
            if 'MemoryError' in tail or 'memory' in tail.lower():
                print('  MEMORY_PRESSURE: %s seed=%d attempt %d failed; retrying in %ds'
                      % (label, seed, attempt, RETRY_SLEEP_S), flush=True)
                if attempt < ATTEMPTS:
                    time.sleep(RETRY_SLEEP_S)
                    continue
            return last_err, None
        except subprocess.TimeoutExpired:
            last_err = 'ERROR: TIMEOUT after %ds' % TIMEOUT_S
            return last_err, None
        except Exception as e:
            last_err = 'ERROR: %s: %s' % (type(e).__name__, e)
            return last_err, None
    return last_err, None


def main():
    os.makedirs(PRED_DIR, exist_ok=True)
    missing = [p for p in (NO_LIQ, ADDR_TYPE) if not os.path.exists(p)]
    if missing:
        print('MISSING input file(s): %s -- abort' % ', '.join(missing), flush=True)
        return

    with open(OUT, 'w', encoding='utf-8') as f:
        f.write('job\tseed\tvariant\tedges_file\tfinal_test_line\tfinal_metrics_line\telapsed_s\n')
        f.flush()
        for label, variant, edges_file in JOBS:
            for seed in SEEDS:
                t0 = time.time()
                print('[%s seed=%d] running...' % (label, seed), flush=True)
                test_line, metrics_line = run_one(label, variant, edges_file, seed)
                el = time.time() - t0
                if test_line.startswith('ERROR:'):
                    print('ERROR_OCCURRED: %s seed=%d -> %s' % (label, seed, test_line), flush=True)
                    metrics_line = metrics_line or '-'
                f.write('%s\t%d\t%s\t%s\t%s\t%s\t%.1f\n' % (
                    label, seed, variant, edges_file or '-', test_line, metrics_line, el))
                f.flush()
                print('  -> %s (%.0fs)' % (test_line[-120:], el), flush=True)
    print('DONE', flush=True)


if __name__ == '__main__':
    main()
