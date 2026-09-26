from matplotlib.pyplot import delaxes
import torch
import random
import os
import pandas as pd
import numpy as np
import torch.nn as nn
import time


def  set_random_seed(seed):
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    np.random.seed(seed)
    random.seed(seed)
    os.environ['PYTHONHASHSEED'] = str(seed)
    # os.environ['CUDA_LAUNCH_BLOCKING'] = str(1)
    # os.environ['CUBLAS_WORKSPACE_CONFIG'] = ':4096:8'
    torch.manual_seed(seed)
    torch.cuda.manual_seed(seed)
    torch.backends.cudnn.enabled = False
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    torch.use_deterministic_algorithms(True)


class Classifier(nn.Module):
    def __init__(self, n_hid, n_out):
        super(Classifier, self).__init__()
        self.n_hid = n_hid
        self.n_out = n_out
        self.linear = nn.Linear(n_hid, n_out)

    def forward(self, x):
        tx = self.linear(x)
        return torch.log_softmax(tx.squeeze(), dim=-1)

    def __repr__(self):
        return '{}(n_hid={}, n_out={})'.format(
            self.__class__.__name__, self.n_hid, self.n_out)

#refer to https://github.com/iMoonLab/THU-HyperG/blob/master/hyperg/hyperg.py
class HyperG:
    def __init__(self, H, X=None, w=None):
        """ Initial the incident matrix, node feature matrix and hyperedge weight vector of hypergraph
        :param H: scipy coo_matrix of shape (n_nodes, n_edges)
        :param X: numpy array of shape (n_nodes, n_features)
        :param w: numpy array of shape (n_edges,)
        """
        assert sparse.issparse(H)
        assert H.ndim == 2

        self._H = H
        self._n_nodes = self._H.shape[0]
        self._n_edges = self._H.shape[1]

        if X is not None:
            assert isinstance(X, np.ndarray) and X.ndim == 2
            self._X = X
        else:
            self._X = None

        if w is not None:
            self.w = w.reshape(-1)
            assert self.w.shape[0] == self._n_edges
        else:
            self.w = np.ones(self._n_edges)

        self._DE = None
        self._DV = None
        self._INVDE = None
        self._DV2 = None
        self._THETA = None
        self._L = None

    def num_edges(self):
        return self._n_edges

    def num_nodes(self):
        return self._n_nodes

    def incident_matrix(self):
        return self._H

    def hyperedge_weights(self):
        return self.w

    def node_features(self):
        return self._X

    def node_degrees(self):
        if self._DV is None:
            H = self._H.tocsr()
            dv = H.dot(self.w.reshape(-1, 1)).reshape(-1)
            self._DV = sparse.diags(dv, shape=(self._n_nodes, self._n_nodes))
        return self._DV

    def edge_degrees(self):
        if self._DE is None:
            H = self._H.tocsr()
            de = H.sum(axis=0).A.reshape(-1)
            self._DE = sparse.diags(de, shape=(self._n_edges, self._n_edges))
        return self._DE

    def inv_edge_degrees(self):
        if self._INVDE is None:
            self.edge_degrees()
            inv_de = np.power(self._DE.data.reshape(-1), -1.)
            self._INVDE = sparse.diags(inv_de, shape=(self._n_edges, self._n_edges))
        return self._INVDE

    def inv_square_node_degrees(self):
        if self._DV2 is None:
            self.node_degrees()
            dv2 = np.power(self._DV.data.reshape(-1)+1e-6, -0.5)
            self._DV2 = sparse.diags(dv2, shape=(self._n_nodes, self._n_nodes))
        return self._DV2

    def theta_matrix(self):
        if self._THETA is None:
            self.inv_square_node_degrees()
            self.inv_edge_degrees()

            W = sparse.diags(self.w)
            self._THETA = self._DV2.dot(self._H).dot(W).dot(self._INVDE).dot(self._H.T).dot(self._DV2)

        return self._THETA

    def laplacian(self):
        if self._L is None:
            self.theta_matrix()
            self._L = sparse.eye(self._n_nodes) - self._THETA
        return self._L

    def update_hyedge_weights(self, w):
        assert isinstance(w, (np.ndarray, list)), \
            "The hyperedge array should be a numpy.ndarray or list"

        self.w = np.array(w).reshape(-1)
        assert w.shape[0] == self._n_edges

        self._DV = None
        self._DV2 = None
        self._THETA = None
        self._L = None

    def update_incident_matrix(self, H):
        assert sparse.issparse(H)
        assert H.ndim == 2
        assert H.shape[0] == self._n_nodes
        assert H.shape[1] == self._n_edges

        # TODO: reset hyperedge weights?

        self._H = H
        self._DE = None
        self._DV = None
        self._INVDE = None
        self._DV2 = None
        self._THETA = None
        self._L = None
def print_log(message):
    """
    :param message: str,
    :return:
    """
    print("[{}] {}".format(time.strftime("%Y-%m-%d %X", time.localtime()), message))

import numpy as np
import scipy.sparse as sparse


def gen_attribute_hg(n_nodes, attr_dict, X=None):
    """
    :param attr_dict: dict, eg. {'attri_1': [node_idx_1, node_idx_1, ...], 'attri_2':[...]} (zero-based indexing)
    :param n_nodes: int,
    :param X: numpy array, shape = (n_samples, n_features) (optional)
    :return: instance of HyperG
    """

    if X is not None:
        assert n_nodes == X.shape[0]

    n_edges = len(attr_dict)
    node_idx = []
    edge_idx = []

    for idx, attr in enumerate(attr_dict):
        nodes = sorted(attr_dict[attr])
        node_idx.extend(nodes)
        edge_idx.extend([idx] * len(nodes))

    node_idx = np.asarray(node_idx)
    edge_idx = np.asarray(edge_idx)
    values = np.ones(node_idx.shape[0])

    H = sparse.coo_matrix((values, (node_idx, edge_idx)), shape=(n_nodes, n_edges))
    return HyperG(H, X=X)

def build_incidence(n_nodes, attr_dict):
    """Vectorized-hypergraph counterpart of gen_attribute_hg: same attr_dict input
    ({group_name: [node_idx, ...]}), but returns raw (node, group, count) index
    tensors instead of a scipy HyperG, for use with hyper_laplacian/HyperGNNVectorized.
    """
    node_idx, edge_idx = [], []
    for idx, attr in enumerate(attr_dict):
        nodes = attr_dict[attr]
        node_idx.extend(nodes)
        edge_idx.extend([idx] * len(nodes))
    node = torch.LongTensor(node_idx)
    group = torch.LongTensor(edge_idx)
    return node, group, len(attr_dict)


def hyper_laplacian(x, node, group, count):
    """(I - Dv^-1/2 H De^-1 H^T Dv^-1/2) X, computed via index_add/bincount instead
    of a scipy.sparse matrix product. Mathematically equivalent to HyperG.laplacian()
    @ x with uniform hyperedge weights (w=1), but O(incidences * hidden) and avoids
    the scipy dense-intermediate OOM that HyperGNN hits above ~50k nodes (scipy_sparse
    path tried to allocate ~11.5GB at 50k companies).
    Architecture credit: this formula is Li Ruirui's (backend/comrisk/model.py,
    github.com/ilydouble/risk), ported here unchanged.
    """
    if count == 0:
        return torch.zeros_like(x)
    degree = torch.bincount(node, minlength=len(x)).to(x.dtype)
    inv = degree.clamp_min(1).rsqrt()
    edge_degree = torch.bincount(group, minlength=count).to(x.dtype).clamp_min(1)
    summed = x.new_zeros((count, x.shape[1])).index_add(0, group, x[node] * inv[node, None])
    propagated = torch.zeros_like(x).index_add(0, node, (summed / edge_degree[:, None])[group]) * inv[:, None]
    return (x - propagated) * (degree > 0)[:, None]


def scipy_sparse_mat_to_torch_sparse_tensor(sparse_mx):
    """
    Convert a scipy sparse matrix into a torch sparse tensor.
    """
    sparse_mx = sparse_mx.tocoo().astype(np.float32)
    indices = torch.from_numpy(
        np.vstack((sparse_mx.row, sparse_mx.col)).astype(np.int64))
    values = torch.from_numpy(sparse_mx.data)
    shape = torch.Size(sparse_mx.shape)
    return torch.sparse.FloatTensor(indices, values, shape)

    
#refer to https://github.com/alge24/DyGNN/blob/b161555a5df69bd3fa9cc3ae5d4f5cd65ebe3a0f/decayer.py
class Decayer(nn.Module):
    def __init__(self, w1=0.01,w2=0.1, decay_method='rev'):
    # def __init__(self, w1=100,w2=200, decay_method='rev'):
        super(Decayer,self).__init__()
        self.decay_method = decay_method
        self.w1 = w1
        self.w2=w2

    def exponetial_decay(self, w, delta_t):
        return torch.exp(-w*delta_t)
    def log_decay(self, w, delta_t):
        return 1/torch.log(2.7183 + w*delta_t)
    def rev_decay(self, w, delta_t):
        return 1/(1 + w*delta_t)

    def forward(self,delta_t):
        seq=torch.zeros_like(delta_t)

        idx1=(delta_t<=24)
        idx2=(delta_t>24)

        # # print(delta_t)
        if self.decay_method == 'exp':
            seq[idx1]=self.exponetial_decay(self.w1,delta_t[idx1])
            seq[idx2]=self.exponetial_decay(self.w2,delta_t[idx2])
        elif self.decay_method == 'log':
            seq[idx1]=self.log_decay(self.w1,delta_t[idx1])
            seq[idx2]=self.log_decay(self.w2,delta_t[idx2])
        elif self.decay_method == 'rev':
            seq[idx1]=self.rev_decay(self.w1,delta_t[idx1])
            seq[idx2]=self.rev_decay(self.w2,delta_t[idx2])

        else:
            seq[idx1]=self.exponetial_decay(delta_t[idx1])
            seq[idx2]=self.exponetial_decay(delta_t[idx2])
        # print(seq,"----")

        return seq
        

def initializae_company_info(risk_data,company_attr,company_num,cause_type_num,court_type,category,idx=None):
    if idx:
        idx_dict={index:ser for ser,index in enumerate(idx)}
    company_risk=np.zeros((company_num,cause_type_num+court_type+category+1))
    for index in risk_data:
        risk_info=risk_data[index]
        cause_info=[0 for i in range(cause_type_num)]
        court_info=[0 for i in range(court_type)]
        res_info=[0 for i in range(category)]
        time_info=[]
        for i in range(len(risk_info)):
            justify=risk_info[i]
            cause=justify[0]
            court=justify[1]
            res=justify[2]
            time=justify[3]
            cause_info[cause]+=1
            court_info[court]+=1
            res_info[res]+=1
            time_info+=[time]
        time_ave=[np.average(time_info)]
        if idx:
            company_risk[idx_dict[index]]=np.concatenate((cause_info,court_info,res_info,time_ave),axis=0)
        else:
            company_risk[index]=np.concatenate((cause_info,court_info,res_info,time_ave),axis=0)
    company_attr=np.array(company_attr)
    company_info=np.concatenate((company_attr,company_risk),axis=1)
    return company_info


def fit_bayesian_group_prior(group_dict, label, idx, min_strength=30):
    """Fit a Bayesian-smoothed default-rate prior per group (e.g. per region/area),
    from TRAINING data only. This mirrors the "country x industry" community-risk
    prior described in the team's proposal: rather than trusting a small group's raw
    default rate (unstable when n is small), each group's rate is pulled toward the
    global rate, with the pull strength set by how much data that group has.

    group_dict: hyp_graph[grouping_key], e.g. train_hyp_graph['area'] -->
                {group_name: [company_index, ...], ...}
    label: array-like of 0/1 labels, same order as `idx`
    idx: list of company indices corresponding to `label`

    Returns (group_prior: dict[group_name -> float], global_alpha, global_beta, global_mean).
    Alpha/beta are estimated by the method of moments from the per-group observed
    rates, per standard Bayesian-smoothing practice (e.g. empirical Bayes for rate
    estimation).
    """
    idx_to_label = {i: l for i, l in zip(idx, label)}
    group_rates = []
    group_counts = []
    group_names = []
    for name, members in group_dict.items():
        labels_in_group = [idx_to_label[m] for m in members if m in idx_to_label]
        n = len(labels_in_group)
        if n == 0:
            continue
        y = sum(labels_in_group)
        group_rates.append(y / n)
        group_counts.append(n)
        group_names.append(name)

    global_mean = float(np.mean(list(idx_to_label.values())))
    # Method-of-moments estimate of Beta(alpha, beta) from the spread of group rates.
    rates = np.array(group_rates)
    var = rates.var()
    if var <= 1e-8 or len(rates) < 2:
        # Not enough spread to estimate a meaningful prior strength; fall back to a
        # mild, fixed pseudo-count so smoothing still behaves sensibly.
        alpha, beta = global_mean * 10, (1 - global_mean) * 10
    else:
        m = global_mean
        nu = m * (1 - m) / var - 1
        nu = max(nu, 1e-3)  # guard against a degenerate/negative estimate
        alpha, beta = m * nu, (1 - m) * nu

    # Floor the total pseudo-count (alpha+beta) at min_strength. Found 2026-09-25: with
    # a highly fragmented grouping (e.g. a same-cohort subsample where most groups have
    # 1-2 members), the method-of-moments estimate above can come out very weak
    # (alpha+beta ~= 3-4), which under-smooths small groups -- the leave-one-out fix
    # removes the WORST case (n=1 direct leakage) but a weak prior still lets a group of
    # n=2 lean almost entirely on its 1 remaining member after LOO, which is closer to
    # noise than signal. Flooring the strength forces every small group to be pulled
    # more firmly toward the global mean, at the cost of some responsiveness for groups
    # that do have enough data to be trusted.
    strength = alpha + beta
    if strength < min_strength:
        scale = min_strength / max(strength, 1e-6)
        alpha, beta = alpha * scale, beta * scale

    group_prior = {}
    group_stats = {}  # name -> (n, y), kept for the leave-one-out feature builder below
    for name, members in group_dict.items():
        labels_in_group = [idx_to_label[m] for m in members if m in idx_to_label]
        n = len(labels_in_group)
        y = sum(labels_in_group)
        group_prior[name] = (y + alpha) / (n + alpha + beta)
        group_stats[name] = (n, y)

    return group_prior, alpha, beta, global_mean, group_stats


def build_group_prior_feature_loo(group_dict, idx, label, group_stats, alpha, beta, global_mean):
    """Leave-one-out version of build_group_prior_feature, for use ONLY when scoring
    the same companies (and labels) that fit_bayesian_group_prior was fit on -- i.e.
    building the TRAINING feature. Without this, a company sitting alone in its group
    (n=1) gets a "prior" that is really just its own label rescaled -- caught in
    practice 2026-09-25 (Wang Xiaoxiao found the identical bug independently in her
    own postal/sector/leiden priors: 96.4% of her groups were singletons, and the
    leaky feature correlated 0.85 with the label inside those groups, vs 0.05 outside).
    For a company c in a group with n members and y positives, this returns
    (y - label_c + alpha) / (n - 1 + alpha + beta); groups of size 1 have nothing left
    after removing the company itself, so they fall back to global_mean (no information,
    same as an unseen group).
    """
    idx_to_group = {}
    for name, members in group_dict.items():
        for m in members:
            idx_to_group[m] = name
    idx_to_label = {i: l for i, l in zip(idx, label)}

    feature = np.zeros((len(idx), 1))
    for row, company_idx in enumerate(idx):
        group_name = idx_to_group.get(company_idx)
        if group_name is None or group_name not in group_stats:
            feature[row, 0] = global_mean
            continue
        n, y = group_stats[group_name]
        own_label = idx_to_label.get(company_idx, 0)
        n_loo, y_loo = n - 1, y - own_label
        if n_loo <= 0:
            feature[row, 0] = global_mean  # singleton group: no information left
        else:
            feature[row, 0] = (y_loo + alpha) / (n_loo + alpha + beta)
    return feature


def build_group_prior_feature(group_dict, idx, group_prior, global_mean):
    """Build a (len(idx), 1) array of the Bayesian-smoothed group-risk prior for each
    company in `idx`, using the group -> prior lookup from fit_bayesian_group_prior.
    Companies whose group wasn't seen when the prior was fit (e.g. a region that only
    appears in the valid/test split) fall back to the global mean rate.
    """
    idx_to_group = {}
    for name, members in group_dict.items():
        for m in members:
            idx_to_group[m] = name

    feature = np.zeros((len(idx), 1))
    for row, company_idx in enumerate(idx):
        group_name = idx_to_group.get(company_idx)
        feature[row, 0] = group_prior.get(group_name, global_mean) if group_name is not None else global_mean
    return feature


