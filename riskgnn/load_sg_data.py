# coding: utf-8
"""
Adapter: converts Wang Xiaoxiao's comrisk_export/ (Singapore ACRA+GLEIF, parquet)
into the same in-memory structures ComRisk's gnn.py/train.py expect.

Rewritten for speed after the first version stalled on the full 2.1M-row
tables (it did full-table reindex/groupby before subsampling, and used
Series.map(dict) over millions of rows instead of vectorized joins).
This version: filter to the companies we actually need FIRST, then join,
using pandas merge (hash join, vectorized) instead of .map(dict).
"""
import time
import numpy as np
import pandas as pd


def load_sg_export(data_dir='./data_sg_v2/comrisk_export', max_companies=None, seed=0, verbose=True, exclude_age=False, cohort_year=None):
    t0 = time.time()
    def log(msg):
        if verbose:
            print('[%.1fs] %s' % (time.time() - t0, msg), flush=True)

    id_map = pd.read_parquet(f'{data_dir}/id_map.parquet')
    label_df = pd.read_parquet(f'{data_dir}/label.parquet', columns=['company_id', 'label', 'is_labeled'])
    log('loaded id_map (%d) + label (%d)' % (len(id_map), len(label_df)))

    labeled = label_df[label_df['is_labeled'] == 1].reset_index(drop=True)
    log('filtered to %d labeled companies' % len(labeled))

    if cohort_year is not None:
        # Same-cohort design (per Wang Xiaoxiao's LEAKAGE_REPORT.md recommendation):
        # restrict to companies registered in the same year, so every company in the
        # sample has the same observation window (age is no longer a confound between
        # companies -- a 2024-registered company hasn't been "given time" to fail the
        # way a 2010-registered one has). Registration year is NOT a column in the
        # export; derived from age_years relative to the 2025-12-31 snapshot date
        # (README.md), i.e. reg_year ~= 2025 - floor(age_years). This is an
        # approximation (age_years is a float, not the actual registration date), off
        # by at most 1 year.
        age_df = pd.read_parquet(f'{data_dir}/company_attr.parquet', columns=['company_id', 'age_years'])
        age_df['reg_year'] = 2025 - age_df['age_years'].astype(int)
        labeled = labeled.merge(age_df[['company_id', 'reg_year']], on='company_id', how='left')
        before = len(labeled)
        labeled = labeled[labeled['reg_year'] == cohort_year].drop(columns=['reg_year']).reset_index(drop=True)
        log('cohort filter year=%d: %d -> %d labeled companies' % (cohort_year, before, len(labeled)))

    if max_companies is not None and max_companies < len(labeled):
        rng = np.random.RandomState(seed)
        pos = labeled[labeled['label'] == 1]
        neg = labeled[labeled['label'] == 0]
        n_pos = max(1, int(max_companies * len(pos) / len(labeled)))
        n_neg = max_companies - n_pos
        pos_s = pos.sample(n=min(n_pos, len(pos)), random_state=seed)
        neg_s = neg.sample(n=min(n_neg, len(neg)), random_state=seed)
        labeled = pd.concat([pos_s, neg_s]).reset_index(drop=True)
        log('subsampled to %d (pos=%d neg=%d)' % (len(labeled), len(pos_s), len(neg_s)))

    keep_ids = set(labeled['company_id'])

    # company_attr, filtered via merge (not full-table reindex)
    attr = pd.read_parquet(f'{data_dir}/company_attr.parquet',
                            columns=['company_id', 'register_capital', 'paid_capital', 'setup_time_months',
                                     'postal_risk_prior_loo', 'sector_risk_prior_loo', 'leiden_risk_prior_loo'])
    attr = attr[attr['company_id'].isin(keep_ids)]
    log('loaded+filtered company_attr (%d rows)' % len(attr))

    merged = labeled.merge(attr, on='company_id', how='left')
    merged = merged.reset_index(drop=True)
    merged['int_id'] = np.arange(len(merged))  # dense local re-indexing: 0..N-1
    id2int = dict(zip(merged['company_id'], merged['int_id']))
    company_num = len(merged)
    log('built dense local id map (company_num=%d)' % company_num)

    company_attr_full = merged[['register_capital', 'paid_capital', 'setup_time_months']].fillna(0.0).to_numpy()
    if exclude_age:
        # register_capital/paid_capital are 100% NULL (already zeroed above), so
        # setup_time_months is the ONLY populated field in this triple -- zeroing it
        # for the age-excluded variant means company_attr_full carries no signal at
        # all here; any remaining discrimination has to come from the graph/hypergraph/
        # community-prior channels instead. See LEAKAGE_REPORT.md: age_years alone
        # gives AUC 0.8894 on this data (survivorship confound, not real risk signal).
        company_attr_full[:, 2] = 0.0
    precomputed_prior = merged[['postal_risk_prior_loo', 'sector_risk_prior_loo', 'leiden_risk_prior_loo']].mean(axis=1).fillna(0.5).to_numpy()
    label_vals = merged['label'].fillna(-1).to_numpy()

    # stratified 70/15/15 split
    rng = np.random.RandomState(seed)
    all_idx = np.arange(company_num)
    pos_idx = all_idx[label_vals == 1]
    neg_idx = all_idx[label_vals == 0]
    rng.shuffle(pos_idx)
    rng.shuffle(neg_idx)

    def split(arr):
        n = len(arr)
        n_tr = int(n * 0.7)
        n_va = int(n * 0.15)
        return arr[:n_tr], arr[n_tr:n_tr + n_va], arr[n_tr + n_va:]

    pos_tr, pos_va, pos_te = split(pos_idx)
    neg_tr, neg_va, neg_te = split(neg_idx)
    train_idx = np.sort(np.concatenate([pos_tr, neg_tr])).tolist()
    valid_idx = np.sort(np.concatenate([pos_va, neg_va])).tolist()
    test_idx = np.sort(np.concatenate([pos_te, neg_te])).tolist()
    log('split: train=%d valid=%d test=%d' % (len(train_idx), len(valid_idx), len(test_idx)))

    train_label = label_vals[train_idx].astype(int).tolist()
    valid_label = label_vals[valid_idx].astype(int).tolist()
    test_label = label_vals[test_idx].astype(int).tolist()
    train_attr = company_attr_full[train_idx].tolist()
    valid_attr = company_attr_full[valid_idx].tolist()
    test_attr = company_attr_full[test_idx].tolist()

    # --- edges: filter via merge/isin on the (small) keep_ids set BEFORE any
    # further processing, then map ids via merge (not python dict .map on millions
    # of rows).
    edges_df = pd.read_parquet(f'{data_dir}/edges.parquet')
    edges_df = edges_df[edges_df['src_id'].isin(keep_ids) & edges_df['dst_id'].isin(keep_ids)]
    log('filtered edges to %d rows' % len(edges_df))

    id2int_df = pd.DataFrame({'company_id': list(id2int.keys()), 'int_id': list(id2int.values())})
    edges_df = edges_df.merge(id2int_df.rename(columns={'company_id': 'src_id', 'int_id': 'src_int'}), on='src_id')
    edges_df = edges_df.merge(id2int_df.rename(columns={'company_id': 'dst_id', 'int_id': 'dst_int'}), on='dst_id')
    log('mapped edge endpoints to local ids')

    rel_types = sorted(edges_df['rel_type'].unique().tolist())
    rel2id = {r: i for i, r in enumerate(rel_types)}
    rel_num = max(1, len(rel_types))
    edge_index = list(zip(edges_df['src_int'].tolist(), edges_df['dst_int'].tolist()))
    edge_type = edges_df['rel_type'].map(rel2id).tolist()
    # NOTE: forced to uniform 1.0, not the real SAME_ADDRESS/equity weights. ComRisk's
    # HeteGNN.message() branches on whether edge_weight sums to exactly edge_count: it
    # picks a weight-only path (needs a Linear sized for x_j alone) for genuinely
    # weighted edges, vs. a concat(x_i,x_j) path (needs a Linear sized for 2x) for
    # unweighted ones -- and the Linear's size is fixed at construction based on
    # edge_type index (a special case for ComRisk's original types 6-9, concat for
    # everything else). Our new edge types don't fall in that special range, so they
    # were built expecting the concat path; real (non-uniform) weights would silently
    # route into the wrong-shaped Linear. Flagging this as a real fidelity loss: the
    # SAME_ADDRESS similarity score and GLEIF ownership % are not used by the edge
    # mechanism as a result -- would need a small HeteGNN change to fix properly.
    edge_weight = [1.0] * len(edges_df)
    hete_graph = (edge_index, edge_type, edge_weight)
    log('built hete_graph: %d edges, %d rel types %s' % (len(edge_index), rel_num, rel_types))

    # --- hypergraph: filter each table to keep_ids BEFORE groupby.
    def build_hyp(name):
        df = pd.read_parquet(f'{data_dir}/hypergraph_{name}.parquet', columns=['company_id', 'group_value'])
        df = df[df['company_id'].isin(keep_ids)]
        df = df.merge(id2int_df, on='company_id')
        d = {}
        for gv, sub in df.groupby('group_value')['int_id']:
            d[str(gv)] = sub.tolist()
        return d

    hyp_graph = {}
    for name in ['industry', 'area', 'qualify']:
        hyp_graph[name] = build_hyp(name)
        log('built hypergraph_%s: %d groups' % (name, len(hyp_graph[name])))

    meta = dict(
        company_num=company_num, person_num=0, rel_num=rel_num, rel_types=rel_types,
        n_train=len(train_idx), n_valid=len(valid_idx), n_test=len(test_idx),
        train_pos_rate=float(np.mean(train_label)) if train_label else 0.0,
    )
    log('DONE')
    return dict(
        train_idx=train_idx, valid_idx=valid_idx, test_idx=test_idx,
        train_label=train_label, valid_label=valid_label, test_label=test_label,
        train_attr=train_attr, valid_attr=valid_attr, test_attr=test_attr,
        hete_graph=hete_graph, hyp_graph=hyp_graph,
        precomputed_prior=precomputed_prior, company_num=company_num,
        meta=meta,
    )


if __name__ == '__main__':
    d = load_sg_export(max_companies=5000, seed=0)
    print(d['meta'])
