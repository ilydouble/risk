# coding: utf-8
"""Final, corrected batch: full-scale (634,646), node_only (the only ablation that's
tractable at this scale -- see comment in train_sg.py/load_sg_data.py about the
HyperGNN memory wall), LOO-corrected Bayesian prior, WITH and WITHOUT the age
confound, 3 seeds each -- honest numbers per LEAKAGE_REPORT.md's recommendation."""
import subprocess, sys, time

configs = []
for exclude_age in [False, True]:
    for seed in [0, 1, 2]:
        configs.append(dict(exclude_age=exclude_age, seed=seed,
                             tag=f'FULL_node_only_bayesian_exclude_age={exclude_age}_seed={seed}'))

with open('results_final.txt', 'w', encoding='utf-8') as f:
    f.write('tag\texclude_age\tseed\tfinal_test_line\telapsed_s\n')
    f.flush()
    for i, cfg in enumerate(configs):
        t0 = time.time()
        cmd = [sys.executable, '-u', 'train_sg.py', '--max_companies', '1000000',
               '--n_epoch', '100', '--ablation', 'node_only', '--prior_source', 'bayesian',
               '--use_class_weight', '--seed', str(cfg['seed'])]
        if cfg['exclude_age']:
            cmd.append('--exclude_age')
        print('[%d/%d] %s' % (i + 1, len(configs), cfg['tag']), flush=True)
        try:
            out = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            lines = [l for l in out.stdout.splitlines() if 'FINAL TEST' in l]
            final = lines[-1] if lines else ('ERROR: ' + out.stderr[-500:])
        except subprocess.TimeoutExpired:
            final = 'TIMEOUT'
        elapsed = time.time() - t0
        f.write('%s\t%s\t%d\t%s\t%.1f\n' % (cfg['tag'], cfg['exclude_age'], cfg['seed'], final, elapsed))
        f.flush()
        print('  -> %s (%.1fs)' % (final, elapsed), flush=True)
print('ALL DONE', flush=True)
