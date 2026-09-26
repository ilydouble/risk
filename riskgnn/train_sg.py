# coding: utf-8
"""
Trains RiskGNN on Wang Xiaoxiao's Singapore ACRA+GLEIF export (via load_sg_data.py).

Known, honestly-flagged limitations vs. the original ComRisk/SMEsD setup:
- No pretrained metapath2vec embeddings for this graph -> company_emb initialized
  randomly (fixed seed). This channel carries no real pretrained signal here.
- person_num=0 (ACRA/GLEIF has no person entities) -> the HeteGNN's company<->person
  message-passing branches are structurally present but contribute nothing.
- risk_data is empty (no company-level lawsuit records in SG open data) -> RiskInfo
  contributes all-zero features, exactly as it does for missing entries in ComRisk.
"""
import argparse
import time
import numpy as np
import torch
import torch.nn as nn
from sklearn.metrics import accuracy_score as acc, precision_score as pre, recall_score as rec, f1_score as f1, roc_auc_score as roc

from gnn import RiskGNN
from utils import Classifier, set_random_seed, fit_bayesian_group_prior, build_group_prior_feature, build_group_prior_feature_loo, gen_attribute_hg
from load_sg_data import load_sg_export

parser = argparse.ArgumentParser()
parser.add_argument('--max_companies', type=int, default=5000)
parser.add_argument('--exclude_age', action='store_true', help='Zero out setup_time_months -- see LEAKAGE_REPORT.md, age_years alone gives AUC 0.8894 (survivorship confound).')
parser.add_argument('--cohort_year', type=int, default=None, help='Restrict to companies registered in this year (same-cohort design, controls for the age confound directly instead of just zeroing the feature).')
parser.add_argument('--n_epoch', type=int, default=3)
parser.add_argument('--seed', type=int, default=0)
parser.add_argument('--ablation', type=str, default='full', choices=['node_only', 'node_hyper', 'full'])
parser.add_argument('--prior_source', type=str, default='none', choices=['none', 'bayesian', 'precomputed'])
parser.add_argument('--use_class_weight', action='store_true')
parser.add_argument('--input_dim', type=int, default=16)
parser.add_argument('--output_dim', type=int, default=12)
args = parser.parse_args()

t_start = time.time()
set_random_seed(args.seed)
device = torch.device('cpu')

d = load_sg_export(max_companies=args.max_companies, seed=args.seed, exclude_age=args.exclude_age, cohort_year=args.cohort_year)
print('[%.1fs] data loaded: %s' % (time.time() - t_start, d['meta']))

company_num = d['company_num']
rel_num = d['meta']['rel_num']

# community prior
if args.prior_source == 'bayesian':
    area_prior, a_alpha, a_beta, a_mean, a_stats = fit_bayesian_group_prior(d['hyp_graph']['area'], d['train_label'], d['train_idx'])
    train_prior = build_group_prior_feature_loo(d['hyp_graph']['area'], d['train_idx'], d['train_label'], a_stats, a_alpha, a_beta, a_mean)
    valid_prior = build_group_prior_feature(d['hyp_graph']['area'], d['valid_idx'], area_prior, a_mean)
    test_prior = build_group_prior_feature(d['hyp_graph']['area'], d['test_idx'], area_prior, a_mean)
    print('[%.1fs] Bayesian prior fit: alpha=%.3f beta=%.3f mean=%.4f' % (time.time() - t_start, a_alpha, a_beta, a_mean))
elif args.prior_source == 'precomputed':
    pp = d['precomputed_prior']
    train_prior = pp[d['train_idx']].reshape(-1, 1)
    valid_prior = pp[d['valid_idx']].reshape(-1, 1)
    test_prior = pp[d['test_idx']].reshape(-1, 1)
    print('[%.1fs] using Wang\'s precomputed prior (mean of postal/sector/leiden)' % (time.time() - t_start))
else:
    train_prior = valid_prior = test_prior = None

use_hypergraph = args.ablation in ('full', 'node_hyper')
use_edgegraph = args.ablation in ('full',)

# RiskGNN's HyperGNN expects a list of prebuilt HyperG objects (one per grouping
# key), not the raw {group_name: [company idx, ...]} dict -- matches how the
# original train.py builds train_hyp/valid_hyp/test_hyp.
def build_hyp_list(hyp_graph_dict, n_nodes):
    return [gen_attribute_hg(n_nodes, hyp_graph_dict[k], X=None) for k in ('industry', 'area', 'qualify')]

hyp_list = build_hyp_list(d['hyp_graph'], company_num) if use_hypergraph else None
print('[%.1fs] hypergraph HyperG objects built' % (time.time() - t_start))

# No pretrained metapath2vec embeddings for this graph -- fixed-seed random init.
com_initial_emb = np.random.RandomState(args.seed).normal(0, 0.1, size=(company_num, 32))
person_initial_emb = np.zeros((0, 32))

gnn = RiskGNN(args.input_dim, args.output_dim, company_num, 0, rel_num,
              cause_type_num=11, device=device, com_initial_emb=com_initial_emb, person_initial_emb=person_initial_emb,
              court_type_num=4, category_num=4, time_label_num=5,
              use_hypergraph=use_hypergraph, use_edgegraph=use_edgegraph)
classifier = Classifier(args.output_dim, 2).to(device)
model = nn.Sequential(gnn, classifier)
optimizer = torch.optim.Adam(model.parameters(), lr=0.01)
scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, 20, eta_min=1e-6)

if args.use_class_weight:
    train_label_arr = np.array(d['train_label'])
    counts = np.bincount(train_label_arr, minlength=2)
    weight = torch.FloatTensor(len(train_label_arr) / (2 * np.maximum(counts, 1)))
    criterion = nn.CrossEntropyLoss(weight=weight)
    print('[%.1fs] class weights: counts=%s weights=%s' % (time.time() - t_start, counts.tolist(), weight.tolist()))
else:
    criterion = nn.CrossEntropyLoss()

empty_risk = {}  # risk_data is empty for all companies in this export

print('[%.1fs] model built, starting training (ablation=%s prior=%s)' % (time.time() - t_start, args.ablation, args.prior_source))

for epoch in range(args.n_epoch):
    st = time.time()
    model.train()
    emb = gnn.forward(empty_risk, d['train_attr'], d['hete_graph'], hyp_list, d['train_idx'], None, train_prior)
    res = classifier.forward(emb)
    loss = criterion(res, torch.LongTensor(d['train_label']))
    optimizer.zero_grad()
    loss.backward()
    torch.nn.utils.clip_grad_norm_(model.parameters(), 0.25)
    optimizer.step()
    scheduler.step()
    train_loss = loss.item()
    del emb, res, loss

    model.eval()
    with torch.no_grad():
        emb = gnn.forward(empty_risk, d['valid_attr'], d['hete_graph'], hyp_list, d['valid_idx'], None, valid_prior)
        res = classifier.forward(emb)
        pred = res.argmax(dim=1)
        vl = d['valid_label']
        print('[%.1fs] Epoch %d (%.1fs/epoch) TrainLoss=%.3f ValidAcc=%.4f ValidF1=%.4f ValidROC=%.4f' % (
            time.time() - t_start, epoch, time.time() - st, train_loss,
            acc(vl, pred), f1(vl, pred, zero_division=0), roc(vl, res[:, 1]) if len(set(vl)) > 1 else float('nan')))

model.eval()
with torch.no_grad():
    emb = gnn.forward(empty_risk, d['test_attr'], d['hete_graph'], hyp_list, d['test_idx'], None, test_prior)
    res = classifier.forward(emb)
    pred = res.argmax(dim=1)
    tl = d['test_label']
    print('[%.1fs] FINAL TEST: Acc=%.4f Pre=%.4f Recall=%.4f F1=%.4f ROC=%.4f' % (
        time.time() - t_start, acc(tl, pred), pre(tl, pred, zero_division=0), rec(tl, pred, zero_division=0),
        f1(tl, pred, zero_division=0), roc(tl, res[:, 1]) if len(set(tl)) > 1 else float('nan')))
