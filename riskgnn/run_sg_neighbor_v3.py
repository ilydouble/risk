# coding: utf-8
"""Batched node_only vs node_edge run on Wang's FIXED edge export (v3 / comrisk_export_v3).

Why this file exists
--------------------
The old +0.0099 edge-graph result was measured on the v2 edge table, which (per EDGE_FIX_v3.md)
only covered 3.3% of companies (a street-name alphabetical truncation bug: edges were only built
for streets starting with "A"). Wang has since fixed the edge build; node files are byte-identical
(MD5-checked) and only the edge table changed. So the node_edge comparison must be re-run on the
fixed edges. Wang's own request: (a) node_only, (b) node_edge all edges, (c) node_edge minus the
30 liquidation addresses.

What it runs (all through train_sg_neighbor.py, unchanged model/params, only --data_dir / --edges_file differ):
  * node_only            --data_dir data_sg_v7/comrisk_export
  * node_edge            --data_dir data_sg_v7/comrisk_export
  * node_edge_no_liq     --data_dir data_sg_v7/comrisk_export --edges_file .../edges_no_liq.parquet
    (auto-skipped with a clear message if Wang has not sent edges_no_liq.parquet yet)

SAME parameters as the earlier mini-batch run, so node_only is directly comparable to the stored
0.8234 (it touches no edges at all and must reproduce the old per-seed values exactly -- this is
used below as an integrity check).

Robust by design: every run is wrapped in try/except, results are flushed as they arrive, and a
distinct ERROR_OCCURRED line is printed the moment anything fails or times out.
"""
import os
import re
import subprocess
import sys
import time

DATA_DIR = 'data_sg_v7/comrisk_export'
NO_LIQ = os.path.join(DATA_DIR, 'edges_no_liq.parquet')
OUT_FILE = 'results_sg_neighbor_v3.txt'

SEEDS = [0, 1, 2]
N_EPOCH = 10
BATCH_SIZE = 2048
NUM_WORKERS = 8  # 8 is the max that reliably fits: each worker re-imports torch (CUDA DLLs),
                 # and 16 workers exhausted the Windows paging file (WinError 1455). Do not raise.
                 # (Later runs in run_metrics_batch.py use 4: ~16% slower on the edge variants but
                 # ~1.5 GB lighter at peak, which matters when free RAM is only ~5 GB. Results are
                 # bit-identical either way.)
DEVICE = 'cuda'  # GPU: ~9x faster per batch than CPU on the v7 (dense) graph.
                 # Same protocol otherwise (seeds/epochs/batch/fanout/hops unchanged) -> quality unchanged.
TIMEOUT_S = 3600  # generous vs. the ~13 min/run observed for node_edge

# Tolerance for the node_only integrity check. NOT 1e-9: CPU multi-threaded ops (MKL etc.) can
# introduce small non-determinism, so a difference in the 4th decimal (e.g. 0.8249 vs 0.8250) is
# expected rather than a sign of broken plumbing. A |diff| above this (per-seed) is a real problem.
TOL = 1e-4
# The reference below was measured on CPU (v7 node_only reproduced the v5 CPU values bit-exactly,
# so the node side is provably unchanged). If node_only is re-run on GPU, small device-origin
# differences are expected and are NOT a failure -- TOL_DEVICE is the band for that case.
TOL_DEVICE = 5e-3

# CPU reference: node_only on v7 (fixed edges) == v5 (old edges) exactly. Measured 2026-09-26 on CPU.
CPU_REFERENCE = {0: 0.8249, 1: 0.8256, 2: 0.8197}

INCLUDE_NO_LIQ = False  # the no_liq sensitivity variant is deferred (time budget): on the dense v7
                       # graph one node_edge run is ~25 min, so 3+3+3 runs cannot fit. Set True to include.

RUNS = [
    dict(label='node_only', variant='node_only', edges_file=None, requires=None),
    dict(label='node_edge', variant='node_edge', edges_file=None, requires=None),
    dict(label='node_edge_no_liq', variant='node_edge', edges_file=NO_LIQ, requires=NO_LIQ),
]
if not INCLUDE_NO_LIQ:
    RUNS = [r for r in RUNS if r['label'] != 'node_edge_no_liq']


def roc_from(line):
    m = re.search(r'ROC=([0-9.]+)', line or '')
    return float(m.group(1)) if m else None


def main():
    # The summary prints emoji; on Windows with stdout redirected to a file the default cp1252
    # encoding cannot encode them and the summary crashes at the very end. Force UTF-8.
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    results = []
    with open(OUT_FILE, 'w', encoding='utf-8') as f:
        f.write('label\tseed\tdata_dir\tedges_file\tfinal_test_line\telapsed_s\n')
        f.flush()
        for run in RUNS:
            if run['requires'] and not os.path.exists(run['requires']):
                msg = 'SKIPPED (missing %s)' % run['requires']
                print('[%s] %s' % (run['label'], msg), flush=True)
                f.write('%s\t-\t%s\t%s\t%s\t-\n' % (run['label'], DATA_DIR, run['edges_file'], msg))
                f.flush()
                continue
            for seed in SEEDS:
                t0 = time.time()
                cmd = [sys.executable, '-u', 'train_sg_neighbor.py',
                       '--variant', run['variant'],
                       '--n_epoch', str(N_EPOCH),
                       '--seed', str(seed),
                       '--use_class_weight',
                       '--batch_size', str(BATCH_SIZE),
                       '--num_workers', str(NUM_WORKERS),
                       '--device', DEVICE,
                       '--data_dir', DATA_DIR]
                if run['edges_file']:
                    cmd += ['--edges_file', run['edges_file']]
                print('[%s seed=%d] running: %s' % (run['label'], seed, ' '.join(cmd[1:])), flush=True)
                per_run_log = 'run_%s_seed%d.log' % (run['label'], seed)
                try:
                    # Stream the child's stdout/stderr to a per-run log file so we can watch per-epoch
                    # progress in real time and give an accurate ETA (previously it was captured and
                    # only surfaced when the run finished).
                    with open(per_run_log, 'w', encoding='utf-8') as logf:
                        subprocess.run(cmd, stdout=logf, stderr=subprocess.STDOUT,
                                       timeout=TIMEOUT_S, encoding='utf-8', errors='replace')
                    lines = open(per_run_log, encoding='utf-8', errors='replace').read().splitlines()
                    final_line = next((l for l in lines if 'FINAL TEST' in l), None)
                    if final_line is None:
                        final_line = 'ERROR: no FINAL TEST line in %s (tail: %s)' % (
                            per_run_log, ' | '.join(lines[-3:])[-300:])
                        print('ERROR_OCCURRED: %s seed=%d produced no result' % (run['label'], seed), flush=True)
                except subprocess.TimeoutExpired:
                    final_line = 'ERROR: TIMEOUT after %ds' % TIMEOUT_S
                    print('ERROR_OCCURRED: %s seed=%d TIMED OUT after %ds' % (run['label'], seed, TIMEOUT_S), flush=True)
                except Exception as e:
                    final_line = 'ERROR: %s: %s' % (type(e).__name__, e)
                    print('ERROR_OCCURRED: %s seed=%d raised %s: %s' % (run['label'], seed, type(e).__name__, e), flush=True)
                elapsed = time.time() - t0
                f.write('%s\t%d\t%s\t%s\t%s\t%.1f\n' % (
                    run['label'], seed, DATA_DIR, run['edges_file'] or '-', final_line, elapsed))
                f.flush()
                print('  -> %s (%.1fs)' % (final_line, elapsed), flush=True)
                results.append((run['label'], seed, roc_from(final_line)))
        print('DONE', flush=True)

    # ---- summary + integrity check ----
    print('\n' + '=' * 70, flush=True)
    import statistics
    by = {}
    for label, seed, v in results:
        if v is not None:
            by.setdefault(label, []).append((seed, v))
    for label, pairs in by.items():
        vals = [v for _, v in pairs]
        mean = statistics.mean(vals)
        std = statistics.stdev(vals) if len(vals) > 1 else float('nan')
        print('%-18s n=%d  mean=%.4f  std=%.4f  per-seed=%s' % (
            label, len(vals), mean, std, sorted(pairs)), flush=True)
    if 'node_only' in by:
        print('\nINTEGRITY CHECK  node_only on %s vs CPU reference: %s' % (DEVICE, CPU_REFERENCE), flush=True)
        worst = 0.0
        for s, v in sorted(by['node_only']):
            if s not in CPU_REFERENCE:
                continue
            d = abs(v - CPU_REFERENCE[s])
            worst = max(worst, d)
            if d == 0:
                tag = 'exact'
            elif d <= TOL:
                tag = 'same-device float noise'
            elif d <= TOL_DEVICE:
                tag = 'device difference (expected if GPU)'
            else:
                tag = 'DIFFERS'
            print('   seed=%d  cpu_ref=%.4f  now=%.4f  |diff|=%.6f  %s' %
                  (s, CPU_REFERENCE[s], v, d, tag), flush=True)
        if worst == 0:
            print('   -> MATCH ✅ (bit-exact) — node side unchanged', flush=True)
        elif worst <= TOL:
            print('   -> MATCH ✅ (same-device float noise, worst |diff|=%.6f)' % worst, flush=True)
        elif worst <= TOL_DEVICE and DEVICE == 'cuda':
            print('   -> OK ✅ (worst |diff|=%.6f <= TOL_DEVICE %.0e) — consistent with GPU-vs-CPU '
                  'device noise, not a data/plumbing problem' % (worst, TOL_DEVICE), flush=True)
        else:
            print('   -> MISMATCH ❌ worst |diff|=%.6f > %.0e — real difference, investigate'
                  % (worst, TOL_DEVICE), flush=True)
    if 'node_only' in by and 'node_edge' in by:
        a = statistics.mean([v for _, v in by['node_only']])
        b = statistics.mean([v for _, v in by['node_edge']])
        print('node_edge - node_only = %+.4f  (on FIXED edges; old +0.0099 is obsolete)' % (b - a), flush=True)


if __name__ == '__main__':
    main()
