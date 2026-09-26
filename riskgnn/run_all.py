# coding: utf-8
"""Driver: runs the planned batch of configs sequentially, appends each FINAL TEST
result line to results_summary.txt as it completes (so partial progress is visible
even if the whole batch doesn't finish in time)."""
import subprocess
import sys
import time

configs = []

# A) Full scale (634,646 companies), node_only (cheap: no hyper/edge graph),
#    multiple seeds x with/without Bayesian prior -- the headline full-data result.
for seed in [0, 1, 2]:
    for prior in ['none', 'bayesian']:
        configs.append(dict(max_companies=1000000, n_epoch=300, ablation='node_only',
                             prior_source=prior, seed=seed, use_class_weight=True,
                             tag=f'FULL_node_only_prior={prior}_seed={seed}'))

# B) Safe subsample (3000 companies, confirmed tractable), full 3-way ablation,
#    multiple seeds -- answers "does hypergraph/edgegraph help" without hitting the
#    HyperGNN memory/cubic-time wall found at 15k+.
for seed in [0, 1]:
    for ablation in ['node_only', 'node_hyper', 'full']:
        configs.append(dict(max_companies=3000, n_epoch=40, ablation=ablation,
                             prior_source='none', seed=seed, use_class_weight=True,
                             tag=f'SUB3000_{ablation}_seed={seed}'))

print('Total configs: %d' % len(configs), flush=True)

with open('results_summary.txt', 'w', encoding='utf-8') as summary:
    summary.write('tag\tmax_companies\tn_epoch\tablation\tprior_source\tseed\tfinal_test_line\telapsed_s\n')
    summary.flush()

    for i, cfg in enumerate(configs):
        t0 = time.time()
        cmd = [sys.executable, '-u', 'train_sg.py',
               '--max_companies', str(cfg['max_companies']),
               '--n_epoch', str(cfg['n_epoch']),
               '--ablation', cfg['ablation'],
               '--prior_source', cfg['prior_source'],
               '--seed', str(cfg['seed'])]
        if cfg['use_class_weight']:
            cmd.append('--use_class_weight')
        print('[%d/%d] running %s' % (i + 1, len(configs), cfg['tag']), flush=True)
        try:
            out = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
            final_line = [l for l in out.stdout.splitlines() if 'FINAL TEST' in l]
            final_line = final_line[-1] if final_line else ('ERROR: ' + out.stderr[-500:])
        except subprocess.TimeoutExpired:
            final_line = 'TIMEOUT after 900s'
        elapsed = time.time() - t0
        summary.write('%s\t%d\t%d\t%s\t%s\t%d\t%s\t%.1f\n' % (
            cfg['tag'], cfg['max_companies'], cfg['n_epoch'], cfg['ablation'],
            cfg['prior_source'], cfg['seed'], final_line, elapsed))
        summary.flush()
        print('  -> %s (%.1fs)' % (final_line, elapsed), flush=True)

print('ALL DONE', flush=True)
