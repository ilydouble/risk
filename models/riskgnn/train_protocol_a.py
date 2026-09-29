# coding: utf-8
"""Train RiskGNN under Wang Xiaoxiao's frozen Protocol A: her exact 10 base
features (incl. `officers`, fixed 2026-09-25) + SSIC 5-fold OOF target encoding
(11 dims total), her frozen splits_5seed.parquet, node_only ablation (no
hypergraph/edge-graph -- matches how she measures her logistic-regression
reference). Reference to beat: 0.8741 +/- 0.0017.

Reuses her own load_comrisk.py (in data_sg_v3/comrisk_export/) for feature
construction and target encoding, so we are guaranteed to use identical
features/encoding to what she measured -- only the model differs (RiskGNN vs
her logistic regression).
"""
import argparse
import sys
import time
import numpy as np
import torch
import torch.nn as nn
from sklearn.metrics import accuracy_score as acc, precision_score as pre, recall_score as rec, f1_score as f1, roc_auc_score as roc

sys.path.insert(0, 'data_sg_v3/comrisk_export')
from load_comrisk import ComRiskExport

from gnn import RiskGNN
from utils import Classifier, set_random_seed

parser = argparse.ArgumentParser()
parser.add_argument('--n_epoch', type=int, default=100)
parser.add_argument('--seed', type=int, default=0)
parser.add_argument('--use_class_weight', action='store_true')
parser.add_argument('--input_dim', type=int, default=16)
parser.add_argument('--output_dim', type=int, default=12)
args = parser.parse_args()

t0 = time.time()
def log(msg):
    print('[%.1fs] %s' % (time.time() - t0, msg), flush=True)

set_random_seed(args.seed)
device = torch.device('cpu')

ds = ComRiskExport(path='data_sg_v3/comrisk_export', verbose=True).load()
ds.build_labels()
X = ds.build_features(mode='no_age')  # now 10 features incl. officers, per her fix
te = ds.add_target_encoding('ssic_code')
X11 = np.hstack([X, te[:, None]]).astype(np.float32)
n_feat = X11.shape[1]
log('Protocol A feature matrix: %s (%d dims), names=%s' % (X11.shape, n_feat, ds.feature_names + ['ssic_te']))

sp = ds.load_frozen_splits(seed=args.seed)
train_idx, valid_idx, test_idx = sp['train'].tolist(), sp['val'].tolist(), sp['test'].tolist()
y = ds.y  # 0/1/nan, nan where unlabeled
company_num = len(ds.ca)
log('splits: train=%d valid=%d test=%d company_num=%d' % (len(train_idx), len(valid_idx), len(test_idx), company_num))

train_attr = X11[train_idx].tolist()
valid_attr = X11[valid_idx].tolist()
test_attr = X11[test_idx].tolist()
train_label = y[train_idx].astype(int).tolist()
valid_label = y[valid_idx].astype(int).tolist()
test_label = y[test_idx].astype(int).tolist()

empty_risk = {}
empty_hyp = None  # node_only: hypergraph unused

gnn = RiskGNN(args.input_dim, args.output_dim, company_num, 0, 1,
              cause_type_num=11, device=device,
              com_initial_emb=np.random.RandomState(args.seed).normal(0, 0.1, size=(company_num, 32)),
              person_initial_emb=np.zeros((0, 32)),
              court_type_num=4, category_num=4, time_label_num=5,
              use_hypergraph=False, use_edgegraph=False,
              n_company_attr_dims=n_feat)
classifier = Classifier(args.output_dim, 2).to(device)
model = nn.Sequential(gnn, classifier)
optimizer = torch.optim.Adam(model.parameters(), lr=0.01)
scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, 20, eta_min=1e-6)

if args.use_class_weight:
    tl = np.array(train_label)
    counts = np.bincount(tl, minlength=2)
    weight = torch.FloatTensor(len(tl) / (2 * np.maximum(counts, 1)))
    criterion = nn.CrossEntropyLoss(weight=weight)
    log('class weights: counts=%s weights=%s' % (counts.tolist(), weight.tolist()))
else:
    criterion = nn.CrossEntropyLoss()

log('model built, training (Protocol A, node_only, %d dims)' % n_feat)
for epoch in range(args.n_epoch):
    st = time.time()
    model.train()
    emb = gnn.forward(empty_risk, train_attr, None, empty_hyp, train_idx, None, None)
    res = classifier.forward(emb)
    loss = criterion(res, torch.LongTensor(train_label))
    optimizer.zero_grad(); loss.backward()
    torch.nn.utils.clip_grad_norm_(model.parameters(), 0.25)
    optimizer.step(); scheduler.step()
    tloss = loss.item()
    del emb, res, loss
    if epoch % 10 == 0 or epoch == args.n_epoch - 1:
        model.eval()
        with torch.no_grad():
            emb = gnn.forward(empty_risk, valid_attr, None, empty_hyp, valid_idx, None, None)
            res = classifier.forward(emb)
            pred = res.argmax(dim=1)
            log('Epoch %d (%.2fs) TrainLoss=%.3f ValidAcc=%.4f ValidROC=%.4f' % (
                epoch, time.time() - st, tloss, acc(valid_label, pred),
                roc(valid_label, res[:, 1]) if len(set(valid_label)) > 1 else float('nan')))

model.eval()
with torch.no_grad():
    emb = gnn.forward(empty_risk, test_attr, None, empty_hyp, test_idx, None, None)
    res = classifier.forward(emb)
    pred = res.argmax(dim=1)
    log('FINAL TEST: Acc=%.4f Pre=%.4f Recall=%.4f F1=%.4f ROC=%.4f' % (
        acc(test_label, pred), pre(test_label, pred, zero_division=0), rec(test_label, pred, zero_division=0),
        f1(test_label, pred, zero_division=0), roc(test_label, res[:, 1])))
