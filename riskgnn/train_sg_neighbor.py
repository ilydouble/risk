# coding: utf-8
"""node_only vs node_edge (HeteGNN edge-graph, via neighbor sampling) on Wang's
v2.0 no_priors (6-dim) protocol, full 2.1M-node scale, her frozen splits.

Custom fixed-fanout k-hop neighbor sampler in plain NumPy (torch_geometric's own
NeighborLoader needs 'pyg-lib' or 'torch-sparse', neither has a prebuilt wheel for
this torch/Python/OS combo). Sampling is pure-Python/CPU and doesn't benefit from
GPU (confirmed empirically: 2026-09-26, GPU and CPU gave near-identical per-epoch
time, ~300s, for this workload) -- so it's parallelized across CPU cores instead,
via a ProcessPoolExecutor that prefetches several batches ahead of the training
step. This changes nothing about the model, seeds, or epoch count -- same
statistics, just built faster using otherwise-idle cores.

Skips the hypergraph branch entirely: the node_only vs node_hyper ablation
(2026-09-26) already found it adds no measurable value (0.8040 vs 0.8042), and it
doesn't naturally fit mini-batching, so this isolates exactly the exogenous
edge-graph question Wang asked for. node_only reuses the same batching/eval path
with an empty edge set, so the comparison is apples-to-apples.
"""
import argparse
import sys
import time
from array import array
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from concurrent.futures import ProcessPoolExecutor
from sklearn.metrics import accuracy_score as acc, precision_score as pre, recall_score as rec, f1_score as f1, roc_auc_score as roc, average_precision_score as ap_score
from scipy.stats import ks_2samp

# ---------------------------------------------------------------------------
# Worker-process globals: set once per process by _worker_init, reused across
# every sampling task in that process (avoids re-pickling the ~6M-entry CSR
# arrays on every single batch).
# ---------------------------------------------------------------------------
_W = {}


def _worker_init(indptr, dst, et, ew, fanouts):
    _W['indptr'] = indptr
    _W['dst'] = dst
    _W['et'] = et
    _W['ew'] = ew
    _W['fanouts'] = fanouts


def _sample_task(seed_nodes, rng_seed):
    """Runs inside a worker process. Mimics real neighbor-loader convention:
    n_id[0:batch_size] are the seed/target nodes; local edge_index has messages
    flowing neighbor->center (matches HeteGNN's propagate(), which aggregates at
    edge_index[1])."""
    indptr, dst, et, ew, fanouts = _W['indptr'], _W['dst'], _W['et'], _W['ew'], _W['fanouts']
    rng = np.random.default_rng(rng_seed)
    node_map = {}
    # array('i') instead of list: 4 bytes per element instead of ~36 (8-byte pointer +
    # a 28-byte PyLong object per distinct int). At ~2M edges per batch x 8 workers the
    # Python lists were the single largest peak-RAM consumer (~290 MB per worker, ~2.3 GB
    # across the pool). The appended VALUES are identical and in the same order, so the
    # arrays produced downstream are bit-identical -- memory-only change.
    order_nodes = array('i')
    for nid in seed_nodes:
        nid = int(nid)
        if nid not in node_map:
            node_map[nid] = len(order_nodes)
            order_nodes.append(nid)
    batch_size = len(order_nodes)
    frontier = list(range(batch_size))
    edges_src, edges_dst, edges_et = array('i'), array('i'), array('i')
    edges_ew = array('f')
    for fanout in fanouts:
        new_frontier = []
        for center_local in frontier:
            node = order_nodes[center_local]
            start, end = indptr[node], indptr[node + 1]
            deg = end - start
            if deg == 0:
                continue
            sel = np.arange(start, end) if deg <= fanout else start + rng.choice(deg, size=fanout, replace=False)
            for k in sel:
                neigh = int(dst[k])
                if neigh not in node_map:
                    node_map[neigh] = len(order_nodes)
                    order_nodes.append(neigh)
                    new_frontier.append(node_map[neigh])
                edges_src.append(node_map[neigh])
                edges_dst.append(center_local)
                edges_et.append(int(et[k]))
                edges_ew.append(float(ew[k]))
        frontier = new_frontier
        if not frontier:
            break
    # Return NumPy arrays, not Python lists -- pickles much faster across the
    # process-pool boundary (this is the dominant cost per the 2026-09-26 finding
    # that workers sit ~96% idle -- IPC serialization, not sampling compute, is
    # the bottleneck). Purely a packaging change; the sampled edges/nodes are
    # identical either way.
    # Return NumPy arrays with the SMALLEST safe dtype: indices are < 2^31, so int32 is exact,
    # and it halves the bytes pickled across the process-pool boundary (the dominant per-batch
    # overhead on this dense graph). Values are identical -> results unchanged (verified by
    # re-running seed 0 / 1 epoch and checking the ROC matches exactly).
    n_id = np.array(order_nodes, dtype=np.int32)
    if edges_src:
        edge_index_local = np.array([edges_src, edges_dst], dtype=np.int32)
        edge_type_local = np.array(edges_et, dtype=np.int32)
        edge_weight_local = np.array(edges_ew, dtype=np.float32)
    else:
        edge_index_local = np.zeros((2, 0), dtype=np.int32)
        edge_type_local = np.zeros((0,), dtype=np.int32)
        edge_weight_local = np.zeros((0,), dtype=np.float32)
    return n_id, edge_index_local, edge_type_local, edge_weight_local, batch_size


def build_csr(edge_index, edge_type, edge_weight, num_nodes):
    src = edge_index[0].numpy()
    order = np.argsort(src, kind='stable')
    dst = edge_index[1].numpy()[order]
    et = edge_type.numpy()[order]
    ew = edge_weight.numpy()[order]
    src_sorted = src[order]
    indptr = np.searchsorted(src_sorted, np.arange(num_nodes + 1))
    # int32 is exact at these sizes (2.1M nodes, 7.7M directed edges) and halves the
    # index tables. On Windows the pool uses spawn, so each of the NUM_WORKERS workers
    # holds its OWN copy of this table -- narrow dtypes are a direct per-worker saving.
    return (indptr.astype(np.int32), dst.astype(np.int32), et.astype(np.int32), ew)


class ParallelBatchSource:
    """Submits sampling tasks to a process pool `lookahead` batches ahead of
    consumption, so worker processes prepare future batches while the main
    process trains on the current one."""
    def __init__(self, pool, seeds_list, base_seed, lookahead=8):
        self.pool = pool
        self.seeds_list = seeds_list
        self.base_seed = base_seed
        self.lookahead = lookahead
        self.next_submit = 0
        self.pending = []
        for _ in range(min(lookahead, len(seeds_list))):
            self._submit_one()

    def _submit_one(self):
        i = self.next_submit
        seeds = self.seeds_list[i]
        fut = self.pool.submit(_sample_task, seeds, self.base_seed * 1_000_003 + i)
        self.pending.append(fut)
        self.next_submit += 1

    def __iter__(self):
        return self

    def __len__(self):
        return len(self.seeds_list)

    def __next__(self):
        if not self.pending:
            raise StopIteration
        fut = self.pending.pop(0)
        if self.next_submit < len(self.seeds_list):
            self._submit_one()
        return fut.result()


def ks_stat(y_true, y_score):
    y_true = np.asarray(y_true)
    y_score = np.asarray(y_score)
    return ks_2samp(y_score[y_true == 1], y_score[y_true == 0]).statistic


# --- ranking + calibration metrics (added 2026-09-27, for Wang's "two free metrics") ---
# NOTE ON UNITS: Classifier.forward returns log_softmax output, so res[:, 1] (the `score`
# returned by run_eval) is a LOG-probability, not a probability. ROC/KS/AP are rank-based
# and therefore unaffected -- which is why this was easy to miss -- but Brier and the
# calibration curve are NOT: they must be computed on exp(score).
def proba_from_logprob(score):
    return np.exp(np.asarray(score, dtype=np.float64))


def _top_frac_mask(y_score, frac):
    """Boolean mask over the top `frac` of ranked scores (stable tie-breaking by index)."""
    y_score = np.asarray(y_score)
    k = max(1, int(round(frac * len(y_score))))
    order = np.argsort(-y_score, kind='stable')
    mask = np.zeros(len(y_score), dtype=bool)
    mask[order[:k]] = True
    return mask


def capture_at_frac(y_true, y_score, frac):
    """Share of all positives that fall inside the top `frac` of predictions."""
    y_true = np.asarray(y_true)
    total = y_true.sum()
    if total == 0:
        return float('nan')
    return float(y_true[_top_frac_mask(y_score, frac)].sum() / total)


def lift_at_frac(y_true, y_score, frac):
    """Positive rate inside the top `frac`, divided by the overall positive rate."""
    y_true = np.asarray(y_true)
    base = y_true.mean()
    if base == 0:
        return float('nan')
    return float(y_true[_top_frac_mask(y_score, frac)].mean() / base)


def brier_score(y_true, proba):
    """Mean squared error between predicted probability and the 0/1 outcome."""
    return float(np.mean((np.asarray(proba, dtype=np.float64)
                          - np.asarray(y_true, dtype=np.float64)) ** 2))


def brier_skill_score(y_true, proba, base_rate=None):
    """BSS = 1 - Brier / [p(1-p)], where p is the base rate of the reference (constant)
    predictor that always outputs p.

    At a 2.1% positive rate that reference already scores p(1-p) = 0.0206, so an absolute
    threshold like "Brier <= 0.10" is passed by a constant predictor and carries no
    information -- it was written for a balanced dataset. BSS is the informative number:
    1 = perfect, 0 = no better than a constant, negative = worse than a constant.
    (Raised by Wang, 2026-09-27.)
    """
    y = np.asarray(y_true, dtype=np.float64)
    p = float(y.mean()) if base_rate is None else float(base_rate)
    ref = p * (1.0 - p)
    if ref <= 0:
        return float('nan')
    return float(1.0 - brier_score(y, proba) / ref)


def calibration_curve(y_true, proba, n_bins=10):
    """Equal-width bins over [0,1]: predicted mean vs observed positive rate per bin."""
    y_true = np.asarray(y_true, dtype=np.float64)
    proba = np.asarray(proba, dtype=np.float64)
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    idx = np.clip(np.digitize(proba, edges[1:-1]), 0, n_bins - 1)
    rows = []
    for b in range(n_bins):
        m = idx == b
        rows.append({
            'bin': b,
            'lo': float(edges[b]),
            'hi': float(edges[b + 1]),
            'count': int(m.sum()),
            'mean_prediction': float(proba[m].mean()) if m.any() else None,
            'observed_rate': float(y_true[m].mean()) if m.any() else None,
        })
    return rows


def make_batches(idx_np, batch_size, shuffle, rng):
    idx = idx_np.copy()
    if shuffle:
        rng.shuffle(idx)
    return [idx[i:i + batch_size] for i in range(0, len(idx), batch_size)]


def to_batch_tensors(n_id_np, ei_local, et_local, ew_local, device):
    # ei_local/et_local/ew_local are NumPy arrays (see _sample_task); indices arrive as int32
    # (halved IPC payload) and are widened to int64 here for safe indexing on device.
    n_id = torch.from_numpy(n_id_np).long().to(device)
    if ei_local.shape[1] > 0:
        ei = torch.from_numpy(ei_local).long().transpose(0, 1).to(device)
    else:
        ei = torch.zeros((0, 2), dtype=torch.long, device=device)
    et = torch.from_numpy(et_local).long().to(device)
    ew = torch.from_numpy(ew_local).to(device)
    return n_id, ei, et, ew


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--variant', type=str, required=True, choices=['node_only', 'node_edge'])
    parser.add_argument('--n_epoch', type=int, default=30)
    parser.add_argument('--seed', type=int, default=0)
    parser.add_argument('--use_class_weight', action='store_true')
    parser.add_argument('--input_dim', type=int, default=16)
    parser.add_argument('--output_dim', type=int, default=12)
    parser.add_argument('--batch_size', type=int, default=1024)
    parser.add_argument('--eval_batch_size', type=int, default=4096)
    parser.add_argument('--fanout', type=int, default=10)
    parser.add_argument('--eval_every', type=int, default=5)
    parser.add_argument('--device', type=str, default='auto', choices=['auto', 'cpu', 'cuda'])
    parser.add_argument('--num_workers', type=int, default=8)
    parser.add_argument('--data_dir', type=str, default='data_sg_v7/comrisk_export',
                        help='comrisk_export folder to load. Defaults to the current v7 export; the older v5/v6 exports differ only in the edge build (v5 predates the v3 edge fix).')
    parser.add_argument('--edges_file', type=str, default=None,
                        help='Optional override for the edge table (e.g. edges_no_liq.parquet); only used for --variant node_edge.')
    parser.add_argument('--dump_preds', type=str, default=None,
                        help='Optional .npz path: saves the test-fold logprob/proba/true/pred arrays so ranking and calibration metrics can be recomputed offline without another run.')
    args = parser.parse_args()

    # Only `load_comrisk` lives inside the export folder, so --data_dir is added to sys.path to
    # import the loader that matches the data being loaded (byte-identical across v2/v3 as of
    # 2026-09-26, but this keeps loader and data in lockstep). `gnn` and `utils` are NOT in the
    # export folder -- they resolve from the repo root (comrisk_sg/), which is intended.
    sys.path.insert(0, args.data_dir)
    from load_comrisk import ComRiskExport   # noqa: E402  (loaded from --data_dir)
    from gnn import RiskGNN                  # noqa: E402  (from repo root)
    from utils import Classifier, set_random_seed  # noqa: E402  (from repo root)

    t0 = time.time()
    def log(msg):
        print('[%.1fs] %s' % (time.time() - t0, msg), flush=True)

    set_random_seed(args.seed)
    if args.device == 'auto':
        device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    else:
        device = torch.device(args.device)
    log('device=%s variant=%s num_workers=%d data_dir=%s edges_file=%s' % (
        device, args.variant, args.num_workers, args.data_dir, args.edges_file))

    ds = ComRiskExport(path=args.data_dir, verbose=True).load()
    if args.edges_file is not None:
        ds.edges = pd.read_parquet(args.edges_file)
        log('edges overridden from %s: %d rows' % (args.edges_file, len(ds.edges)))
    ds.build_labels()
    X = ds.build_features(mode='no_priors')
    n_feat = X.shape[1]
    company_num = len(ds.ca)
    log('feature matrix: %s (%d dims)' % (X.shape, n_feat))

    sp = ds.load_frozen_splits(seed=args.seed)
    train_idx_np, valid_idx_np, test_idx_np = sp['train'], sp['val'], sp['test']
    y = ds.y
    log('splits: train=%d valid=%d test=%d' % (len(train_idx_np), len(valid_idx_np), len(test_idx_np)))

    if args.variant == 'node_edge':
        ds.build_id_map()
        e = ds.edges
        s = e['src_id'].map(ds.id2idx)
        d = e['dst_id'].map(ds.id2idx)
        ok = s.notna() & d.notna()
        s = s[ok].astype(np.int64).values
        d = d[ok].astype(np.int64).values
        rel_codes, rel_uniq = pd.factorize(e.loc[ok, 'rel_type'])
        rel_num = len(rel_uniq)
        log('  relation types: %s' % list(rel_uniq))
        edge_index_full = torch.tensor(np.vstack([np.concatenate([s, d]), np.concatenate([d, s])]), dtype=torch.long)
        edge_type_full = torch.tensor(np.concatenate([rel_codes, rel_codes]), dtype=torch.long)
        edge_weight_full = torch.ones(edge_index_full.shape[1], dtype=torch.float32)
        log('  edges: %d directed, %d relation types' % (edge_index_full.shape[1], rel_num))
    else:
        rel_num = 1
        edge_index_full = torch.zeros((2, 0), dtype=torch.long)
        edge_type_full = torch.zeros((0,), dtype=torch.long)
        edge_weight_full = torch.zeros((0,), dtype=torch.float32)

    indptr, dst, et, ew = build_csr(edge_index_full, edge_type_full, edge_weight_full, company_num)
    fanouts = [args.fanout] * 5
    log('adjacency built')

    gnn = RiskGNN(args.input_dim, args.output_dim, company_num, 0, rel_num,
                  cause_type_num=11, device=device,
                  com_initial_emb=np.random.RandomState(args.seed).normal(0, 0.1, size=(company_num, 32)),
                  person_initial_emb=np.zeros((0, 32)),
                  court_type_num=4, category_num=4, time_label_num=5,
                  use_hypergraph=False, use_edgegraph=True,
                  n_company_attr_dims=n_feat, hyper_impl='vectorized',
                    # This loader forces every edge weight to 1.0, so ALL relations take
                    # message()'s concat path and every per-relation Linear must be
                    # 2*output_dim wide. Passed explicitly because the gnn.py default (None)
                    # means "ComRisk's original index-6..9 convention", which would crash
                    # here as soon as the graph has 7+ relation types (e.g. the
                    # address-type split).
                    hete_scalar_weights=False).to(device)
    classifier = Classifier(args.output_dim, 2).to(device)
    model = nn.Sequential(gnn, classifier)
    optimizer = torch.optim.Adam(model.parameters(), lr=0.01)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, 20, eta_min=1e-6)

    if args.use_class_weight:
        tl = y[train_idx_np].astype(int)
        counts = np.bincount(tl, minlength=2)
        weight = torch.FloatTensor(len(tl) / (2 * np.maximum(counts, 1))).to(device)
        criterion = nn.CrossEntropyLoss(weight=weight)
        log('class weights: counts=%s weights=%s' % (counts.tolist(), weight.tolist()))
    else:
        criterion = nn.CrossEntropyLoss()

    pool = ProcessPoolExecutor(max_workers=args.num_workers, initializer=_worker_init,
                                initargs=(indptr, dst, et, ew, fanouts))

    def run_eval(idx_np, y_np, batch_size):
        model.eval()
        seeds_list = make_batches(idx_np, batch_size, shuffle=False, rng=None)
        source = ParallelBatchSource(pool, seeds_list, base_seed=args.seed + 999999, lookahead=args.num_workers * 2)
        all_pred, all_score, all_true = [], [], []
        with torch.no_grad():
            for n_id_np, ei_local, et_local, ew_local, bsz in source:
                n_id, ei, et_, ew_ = to_batch_tensors(n_id_np, ei_local, et_local, ew_local, device)
                emb = gnn.forward_batch(X, ei, et_, ew_, n_id, bsz)
                res = classifier.forward(emb)
                all_pred.append(res.argmax(dim=1).cpu().numpy())
                all_score.append(res[:, 1].detach().cpu().numpy())
                all_true.append(y_np[n_id_np[:bsz]].astype(int))
        return np.concatenate(all_pred), np.concatenate(all_score), np.concatenate(all_true)

    log('model built, training (%s, fanout=%d, batch=%d, %d epochs, %d workers)' % (
        args.variant, args.fanout, args.batch_size, args.n_epoch, args.num_workers))
    rng_train = np.random.default_rng(args.seed)
    for epoch in range(args.n_epoch):
        st = time.time()
        model.train()
        ep_loss, n_batches = 0.0, 0
        seeds_list = make_batches(train_idx_np, args.batch_size, shuffle=True, rng=rng_train)
        source = ParallelBatchSource(pool, seeds_list, base_seed=args.seed * 100 + epoch, lookahead=args.num_workers * 2)
        for n_id_np, ei_local, et_local, ew_local, bsz in source:
            if n_batches % 50 == 0:
                log('  batch %d/%d...' % (n_batches, len(seeds_list)))
            n_id, ei, et_, ew_ = to_batch_tensors(n_id_np, ei_local, et_local, ew_local, device)
            emb = gnn.forward_batch(X, ei, et_, ew_, n_id, bsz)
            res = classifier.forward(emb)
            label = torch.LongTensor(y[n_id_np[:bsz]].astype(int)).to(device)
            loss = criterion(res, label)
            optimizer.zero_grad(); loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 0.25)
            optimizer.step()
            ep_loss += loss.item(); n_batches += 1
        scheduler.step()
        if epoch % args.eval_every == 0 or epoch == args.n_epoch - 1:
            pred, score, true = run_eval(valid_idx_np, y, args.eval_batch_size)
            log('Epoch %d (%.2fs, %d batches) TrainLoss=%.3f ValidAcc=%.4f ValidROC=%.4f' % (
                epoch, time.time() - st, n_batches, ep_loss / max(n_batches, 1), acc(true, pred),
                roc(true, score) if len(set(true.tolist())) > 1 else float('nan')))
        else:
            log('Epoch %d (%.2fs, %d batches) TrainLoss=%.3f' % (epoch, time.time() - st, n_batches, ep_loss / max(n_batches, 1)))

    pred, score, true = run_eval(test_idx_np, y, args.eval_batch_size)
    # Kept byte-identical to previous runs: with deterministic seeds this line must
    # reproduce exactly, which is the integrity check Wang asked for. Report any drift
    # rather than silently accepting it.
    log('FINAL TEST: Acc=%.4f Pre=%.4f Recall=%.4f F1=%.4f ROC=%.4f KS=%.4f AP=%.4f' % (
        acc(true, pred), pre(true, pred, zero_division=0), rec(true, pred, zero_division=0),
        f1(true, pred, zero_division=0), roc(true, score), ks_stat(true, score), ap_score(true, score)))
    # Ranking + calibration. `score` is a log-probability -> exp() for anything that
    # needs real probabilities (Brier, calibration bins).
    proba = proba_from_logprob(score)
    log('FINAL METRICS: Capture@5%%=%.4f Lift@10%%=%.4f Brier=%.4f n=%d n_pos=%d' % (
        capture_at_frac(true, score, 0.05), lift_at_frac(true, score, 0.10),
        brier_score(true, proba), len(true), int(true.sum())))
    for row in calibration_curve(true, proba):
        if row['count']:
            log('  CALIB bin%02d [%.1f,%.1f) n=%-6d pred=%.4f obs=%.4f' % (
                row['bin'], row['lo'], row['hi'], row['count'],
                row['mean_prediction'], row['observed_rate']))
    if args.dump_preds:
        # Validation predictions are dumped too so the probabilities can be recalibrated
        # offline (fit the calibration map on validation, apply it to test). --use_class_weight
        # inflates the raw probabilities by ~47x (w1/w0), which wrecks Brier and the
        # calibration curve while leaving the rank-based ROC/KS/AP untouched.
        vpred, vscore, vtrue = run_eval(valid_idx_np, y, args.eval_batch_size)
        np.savez(args.dump_preds,
                 test_logprob=np.asarray(score), test_proba=proba,
                 test_true=np.asarray(true), test_pred=np.asarray(pred),
                 valid_logprob=np.asarray(vscore), valid_proba=proba_from_logprob(vscore),
                 valid_true=np.asarray(vtrue), valid_pred=np.asarray(vpred))
        log('  dumped test+valid fold predictions -> %s' % args.dump_preds)
    pool.shutdown()


if __name__ == '__main__':
    main()
