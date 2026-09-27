# coding: utf-8
"""Runs ONLY the node_edge_no_liq sensitivity variant (3 seeds) on the v7 fixed edges, writing to
results_sg_neighbor_v3_noliq.txt -- so it does NOT re-run node_only/node_edge or touch their results.

Same protocol as the main run (10 epochs, batch 2048, fanout 10, 5 hops, 3 seeds, GPU, 8 workers);
the only difference is --edges_file edges_no_liq.parquet (36,722 SAME_ADDRESS edges removed for the
30 liquidation addresses).
"""
import os
import re
import sys
import subprocess
import time

DATA_DIR = 'data_sg_v7/comrisk_export'
NO_LIQ = os.path.join(DATA_DIR, 'edges_no_liq.parquet')
OUT = 'results_sg_neighbor_v3_noliq.txt'
SEEDS = [0, 1, 2]
N_EPOCH = 10
BATCH_SIZE = 2048
NUM_WORKERS = 8
DEVICE = 'cuda'
TIMEOUT_S = 3600

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass


def main():
    if not os.path.exists(NO_LIQ):
        print('MISSING %s -- abort' % NO_LIQ, flush=True)
        return
    with open(OUT, 'w', encoding='utf-8') as f:
        f.write('label\tseed\tdata_dir\tedges_file\tfinal_test_line\telapsed_s\n')
        f.flush()
        for seed in SEEDS:
            t0 = time.time()
            cmd = [sys.executable, '-u', 'train_sg_neighbor.py',
                   '--variant', 'node_edge', '--n_epoch', str(N_EPOCH), '--seed', str(seed),
                   '--use_class_weight', '--batch_size', str(BATCH_SIZE),
                   '--num_workers', str(NUM_WORKERS), '--device', DEVICE,
                   '--data_dir', DATA_DIR, '--edges_file', NO_LIQ]
            log = 'run_node_edge_no_liq_seed%d.log' % seed
            print('[no_liq seed=%d] running' % seed, flush=True)
            try:
                with open(log, 'w', encoding='utf-8') as lf:
                    subprocess.run(cmd, stdout=lf, stderr=subprocess.STDOUT,
                                   timeout=TIMEOUT_S, encoding='utf-8', errors='replace')
                lines = open(log, encoding='utf-8', errors='replace').read().splitlines()
                final = next((l for l in lines if 'FINAL TEST' in l), None)
                if final is None:
                    final = 'ERROR: no FINAL TEST line (tail: %s)' % (' | '.join(lines[-3:])[-300:])
                    print('ERROR_OCCURRED: no_liq seed=%d produced no result' % seed, flush=True)
            except subprocess.TimeoutExpired:
                final = 'ERROR: TIMEOUT after %ds' % TIMEOUT_S
                print('ERROR_OCCURRED: no_liq seed=%d TIMED OUT' % seed, flush=True)
            except Exception as e:
                final = 'ERROR: %s: %s' % (type(e).__name__, e)
                print('ERROR_OCCURRED: no_liq seed=%d raised %s' % (seed, e), flush=True)
            el = time.time() - t0
            f.write('node_edge_no_liq\t%d\t%s\t%s\t%s\t%.1f\n' % (seed, DATA_DIR, NO_LIQ, final, el))
            f.flush()
            print('  -> %s (%.1fs)' % (final, el), flush=True)
    print('DONE', flush=True)


if __name__ == '__main__':
    main()
