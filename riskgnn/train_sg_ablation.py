# coding: utf-8
"""Wang Xiaoxiao's requested 3-way graph ablation, on her v2.0 "no_priors" (6-dim)
Protocol A feature set, full scale (2,111,884 nodes / 634,646 labeled), her frozen
splits. Tests whether RiskGNN's graph components (hypergraph, edge graph) add real
value over the node-only baseline -- this is the actual dAUC>=0.03 claim the team
committed to, which node_only alone cannot test.

Ablations:
  node_only        : use_hypergraph=False, use_edgegraph=False  (baseline)
  node_hyper        : use_hypergraph=True,  use_edgegraph=False  (test hypergraph gain)
  node_hyper_edge    : use_hypergraph=True,  use_edgegraph=True   (test edge-graph gain, expected small)

Hypergraph MUST use hyper_impl='vectorized' -- the original scipy HyperGNN OOMs
(tried to allocate ~11.5GB at just 50k companies); at 2.1M nodes it cannot run at
all. This is the whole point of today's hyper_laplacian port.

Edge weights are forced to 1.0 (documented, known limitation: HeteGNN.message()'s
fixed-shape Linear per relation type breaks on real non-uniform weights on new
edge types -- unresolved, Li Ruirui's attention-based fix for this is not yet
integrated).
"""
import argparse
import sys
import time
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.metrics import accuracy_score as acc, precision_score as pre, recall_score as rec, f1_score as f1, roc_auc_score as roc, average_precision_score as ap_score
from scipy.stats import ks_2samp


def ks_stat(y_true, y_score):
    """KS statistic: max separation between the positive- and negative-class
    score distributions (Wang's FEATURES.md sec.8 requires AUC+KS+AP together)."""
    y_true = np.asarray(y_true)
    y_score = np.asarray(y_score)
    return ks_2samp(y_score[y_true == 1], y_score[y_true == 0]).statistic

sys.path.insert(0, 'data_sg_v5/comrisk_export')
from load_comrisk import ComRiskExport

from gnn import RiskGNN
from utils import Classifier, set_random_seed, build_incidence

parser = argparse.ArgumentParser()
parser.add_argument('--ablation', type=str, required=True, choices=['node_only', 'node_hyper', 'node_hyper_edge'])
parser.add_argument('--n_epoch', type=int, default=30)
parser.add_argument('--seed', type=int, default=0)
parser.add_argument('--use_class_weight', action='store_true')
parser.add_argument('--input_dim', type=int, default=16)
parser.add_argument('--output_dim', type=int, default=12)
parser.add_argument('--eval_every', type=int, default=5)
parser.add_argument('--device', type=str, default='auto', choices=['auto', 'cpu', 'cuda'])
args = parser.parse_args()

t0 = time.time()
def log(msg):
    print('[%.1fs] %s' % (time.time() - t0, msg), flush=True)

set_random_seed(args.seed)
if args.device == 'auto':
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
else:
    device = torch.device(args.device)
log('device=%s' % device)

ds = ComRiskExport(path='data_sg_v5/comrisk_export', verbose=True).load()
ds.build_labels()
X = ds.build_features(mode='no_priors')  # Wang's v2.0 recommended 6-dim set, NO SSIC (matches her baseline_tree.py reference exactly)
n_feat = X.shape[1]
company_num = len(ds.ca)
log('feature matrix: %s (%d dims), names=%s' % (X.shape, n_feat, ds.feature_names))
log('company_num=%d' % company_num)

sp = ds.load_frozen_splits(seed=args.seed)
train_idx, valid_idx, test_idx = sp['train'].tolist(), sp['val'].tolist(), sp['test'].tolist()
y = ds.y
log('splits: train=%d valid=%d test=%d' % (len(train_idx), len(valid_idx), len(test_idx)))

train_attr = X[train_idx].tolist()
valid_attr = X[valid_idx].tolist()
test_attr = X[test_idx].tolist()
train_label = y[train_idx].astype(int).tolist()
valid_label = y[valid_idx].astype(int).tolist()
test_label = y[test_idx].astype(int).tolist()

use_hypergraph = args.ablation in ('node_hyper', 'node_hyper_edge')
use_edgegraph = args.ablation in ('node_hyper_edge',)
log('ablation=%s -> use_hypergraph=%s use_edgegraph=%s' % (args.ablation, use_hypergraph, use_edgegraph))

empty_risk = {}

hyp_list = None
if use_hypergraph:
    # Reuse ds.build_hyperedge_index() -- her own vectorized implementation
    # (id2idx.map() + pd.factorize() on the whole column at once), instead of a
    # slow per-group Python .apply() loop over 91,757 area-groups (which is what
    # a first version of this script did, and it did not finish in 6+ minutes).
    hyperedge_index, n_hyperedges = ds.build_hyperedge_index(
        names=('industry', 'area', 'qualify'), min_size=2)
    node_all = hyperedge_index[0]
    group_all = hyperedge_index[1]
    hyp_list = []
    for name in ('industry', 'area', 'qualify'):
        if name not in ds.hyper_slices:
            continue
        off_lo, off_hi, n_he = ds.hyper_slices[name]
        sel = (group_all >= off_lo) & (group_all < off_hi)
        node = torch.LongTensor(node_all[sel])
        group = torch.LongTensor(group_all[sel] - off_lo)
        hyp_list.append((node, group, n_he))
        log('  hypergraph %s: %d groups, %d incidences' % (name, n_he, int(sel.sum())))

hete_graph = None
person_num = 0
rel_num = 1
if use_edgegraph:
    ds.build_id_map()
    e = ds.edges
    s = e['src_id'].map(ds.id2idx)
    d = e['dst_id'].map(ds.id2idx)
    ok = s.notna() & d.notna()
    log('  edges: dropping %d dangling of %d' % (int((~ok).sum()), len(e)))
    s = s[ok].astype(np.int64).values
    d = d[ok].astype(np.int64).values
    rel_codes, rel_uniq = pd.factorize(e.loc[ok, 'rel_type'])
    rel_num = len(rel_uniq)
    log('  relation types: %s' % list(rel_uniq))
    edge_index = np.vstack([np.concatenate([s, d]), np.concatenate([d, s])]).T.tolist()
    edge_type = np.concatenate([rel_codes, rel_codes]).tolist()
    # Edge weights forced to 1.0: HeteGNN.message()'s fixed-shape Linear per
    # relation type breaks on real non-uniform weights (documented limitation,
    # see project memory / Wang comm log item 7). Not fixed in this run.
    edge_weight = [1.0] * len(edge_type)
    hete_graph = (edge_index, edge_type, edge_weight)
    log('  hete_graph: %d directed edges, %d relation types' % (len(edge_type), rel_num))

gnn = RiskGNN(args.input_dim, args.output_dim, company_num, person_num, rel_num,
              cause_type_num=11, device=device,
              com_initial_emb=np.random.RandomState(args.seed).normal(0, 0.1, size=(company_num, 32)),
              person_initial_emb=np.zeros((0, 32)),
              court_type_num=4, category_num=4, time_label_num=5,
              use_hypergraph=use_hypergraph, use_edgegraph=use_edgegraph,
              n_company_attr_dims=n_feat, hyper_impl='vectorized')
classifier = Classifier(args.output_dim, 2).to(device)
model = nn.Sequential(gnn, classifier).to(device)
optimizer = torch.optim.Adam(model.parameters(), lr=0.01)
scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, 20, eta_min=1e-6)

if args.use_class_weight:
    tl = np.array(train_label)
    counts = np.bincount(tl, minlength=2)
    weight = torch.FloatTensor(len(tl) / (2 * np.maximum(counts, 1))).to(device)
    criterion = nn.CrossEntropyLoss(weight=weight)
    log('class weights: counts=%s weights=%s' % (counts.tolist(), weight.tolist()))
else:
    criterion = nn.CrossEntropyLoss()

train_label_t = torch.LongTensor(train_label).to(device)

log('model built, training (%s, %d dims, %d epochs)' % (args.ablation, n_feat, args.n_epoch))
for epoch in range(args.n_epoch):
    st = time.time()
    model.train()
    emb = gnn.forward(empty_risk, train_attr, hete_graph, hyp_list, train_idx, None, None)
    res = classifier.forward(emb)
    loss = criterion(res, train_label_t)
    optimizer.zero_grad(); loss.backward()
    torch.nn.utils.clip_grad_norm_(model.parameters(), 0.25)
    optimizer.step(); scheduler.step()
    tloss = loss.item()
    del emb, res, loss
    if epoch % args.eval_every == 0 or epoch == args.n_epoch - 1:
        model.eval()
        with torch.no_grad():
            emb = gnn.forward(empty_risk, valid_attr, hete_graph, hyp_list, valid_idx, None, None)
            res = classifier.forward(emb)
            pred = res.argmax(dim=1).cpu().numpy()
            valid_scores = res[:, 1].detach().cpu().numpy()
            log('Epoch %d (%.2fs) TrainLoss=%.3f ValidAcc=%.4f ValidROC=%.4f' % (
                epoch, time.time() - st, tloss, acc(valid_label, pred),
                roc(valid_label, valid_scores) if len(set(valid_label)) > 1 else float('nan')))
    else:
        log('Epoch %d (%.2fs) TrainLoss=%.3f' % (epoch, time.time() - st, tloss))

model.eval()
with torch.no_grad():
    emb = gnn.forward(empty_risk, test_attr, hete_graph, hyp_list, test_idx, None, None)
    res = classifier.forward(emb)
    pred = res.argmax(dim=1).cpu().numpy()
    test_scores = res[:, 1].detach().cpu().numpy()
    log('FINAL TEST: Acc=%.4f Pre=%.4f Recall=%.4f F1=%.4f ROC=%.4f KS=%.4f AP=%.4f' % (
        acc(test_label, pred), pre(test_label, pred, zero_division=0), rec(test_label, pred, zero_division=0),
        f1(test_label, pred, zero_division=0), roc(test_label, test_scores),
        ks_stat(test_label, test_scores), ap_score(test_label, test_scores)))
