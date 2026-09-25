"""Reproducible ablations; choose by validation only."""
import argparse
from pathlib import Path
from .data import dump_json
from .pipeline import load_data, train


def run(data, output, epochs=80, seeds=(42,)):
    root=Path(output);root.mkdir(parents=True,exist_ok=True)
    variants={"full":dict(), "self_only":dict(mode="self_only",use_prior=False),
              "no_hyper":dict(mode="no_hyper"), "no_graph":dict(mode="no_graph"),
              "no_prior":dict(use_prior=False), "pretrained":dict(pretrain_epochs=20)}
    rows=[]
    for seed in seeds:
        for name,options in variants.items():
            print(f'RUN {name} seed={seed}',flush=True)
            path=root/f'{name}-seed{seed}'
            report=train(data,path,epochs=epochs,seed=seed,**options)
            rows.append({"variant":name,"seed":seed,"artifact":str(path.resolve()),
                         "best_epoch":report['metadata']['best_epoch'],
                         "validation_loss":min(x['valid_loss'] for x in report['history']),
                         "test":report['model']['test'],"valid":report['model']['valid'],
                         "seconds":report['elapsed_seconds']})
    selected=min(variants,key=lambda name:sum(r['validation_loss'] for r in rows if r['variant']==name)/len(seeds))
    result={"rows":rows,"selected_variant":selected,"selection_rule":"lowest mean validation BCE over seeds",
            "selected_artifact":next(r['artifact'] for r in rows if r['variant']==selected),
            "scope":"Public SMEsD method validation, not competition target achievement"}
    dump_json(root/'summary.json',result)
    lines=['# 第一版模型公开数据实验','', '仅用于 SMEsD 方法验证，不代表东南亚竞赛成绩。','',
           '| 版本 | 种子 | 测试 AUC | PR-AUC | KS | Brier | Lift@10% | Top5%捕获 |',
           '|---|---|---|---|---|---|---|---|']
    for r in rows:
        m=r['test'];lines.append(f"| {r['variant']} | {r['seed']} | {m['roc_auc']:.4f} | {m['pr_auc']:.4f} | {m['ks']:.4f} | {m['brier']:.4f} | {m['lift_at_10pct']:.4f} | {m['capture_at_5pct']:.4f} |")
    lines += ['',f'按验证集损失选择：{selected}。未按测试成绩选择模型。','',
              '每个目录 metrics.json 包含训练曲线、校准曲线、原始/校准指标及逻辑回归、梯度提升树基线。',
              'self_only 移除图、超图、社区先验，但保留诉讼编码；表格基线仅使用企业属性，信息量不同。']
    (root/'summary.md').write_text('\n'.join(lines),encoding='utf-8')
    print(result['selected_artifact'])


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--data',default='data/processed/smesd');p.add_argument('--output',default='artifacts/smesd-v1')
    p.add_argument('--epochs',type=int,default=80);p.add_argument('--seeds',nargs='+',type=int,default=[42])
    a=p.parse_args();run(load_data(a.data),a.output,a.epochs,a.seeds)
