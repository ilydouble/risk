from collections import defaultdict
from pickle import FALSE
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.autograd import Variable
from torch.nn.modules.activation import PReLU
from torch_geometric.nn import GCNConv, GATConv,RGCNConv
from torch_geometric.nn.conv import MessagePassing
from torch_geometric.nn.inits import glorot, uniform
from torch_geometric.utils import softmax
import math

from utils import *
# torch_sparse (SparseTensor, set_diag, tensor.to) and torch_scatter.scatter were imported
# here but never called anywhere in this file (verified by grep) — dropped since neither
# package ships a prebuilt wheel for this torch/Python combination.
from torch_geometric.utils import remove_self_loops, add_self_loops, softmax, degree, to_undirected
from torch.nn import Sequential, Linear, ReLU, Dropout
import numpy as np

class HeteGNN(MessagePassing):
    def __init__(self, input_dim,output_dim,rel_num,negative_slope=0.2,num_company_rel=7,num_person_rel=3,
    aggr = "add", flow= "source_to_target", node_dim = -2):
        super(HeteGNN,self).__init__(aggr=aggr, flow=flow, node_dim=node_dim)
        self.input_dim=input_dim
        self.output_dim=output_dim
        self.rel_num=rel_num
        self.negative_slope=negative_slope

        self.proj_com=nn.Linear(input_dim,output_dim,bias=False)
        self.proj_per=nn.Linear(input_dim,output_dim,bias=False)

        self.ck_linears   = nn.ModuleList()
        self.cq_linears   = nn.ModuleList()

        for t in range(rel_num):
            self.ck_linears.append(nn.Linear(output_dim,   output_dim))
            self.cq_linears.append(nn.Linear(output_dim,   output_dim))

        self.cv_linear=nn.Linear(output_dim,   output_dim)
        self.crelation_pri   = nn.Parameter(torch.ones(rel_num))

        self.rel_wi=nn.ModuleList()
        for i in range(rel_num):
            if i in [6,7,8,9]:
                self.rel_wi.append(nn.Linear(output_dim,output_dim,bias=False))
            else:
                self.rel_wi.append(nn.Linear(output_dim*2,output_dim,bias=False))


        self.skip = nn.Parameter(torch.ones(1))
        self.bn=nn.BatchNorm1d(output_dim)

    def forward(self,company_emb,person_emb,edge_index,edge_type,edge_weight,company_num,person_num):
        company_emb=self.proj_com(company_emb)
        person_emb=self.proj_per(person_emb)
        emb=torch.cat((company_emb,person_emb),dim=0)
        emb=self.bn(emb)
        dev = emb.device
        # torch.LongTensor(...)/.FloatTensor(...) construct on CPU and reject an
        # already-CUDA input tensor -- use as_tensor (device-agnostic) so this works
        # whether edge_index/type/weight arrive as CPU lists (legacy full-batch
        # callers) or GPU tensors (forward_batch's mini-batch path).
        edge_index = torch.as_tensor(edge_index, dtype=torch.long).transpose(0, 1).to(dev)
        edge_type = torch.as_tensor(edge_type, dtype=torch.long).to(dev)
        edge_weight = torch.as_tensor(edge_weight, dtype=torch.float32).unsqueeze(1).to(dev)

        rs_list=[]
        rel_type=[]

        for i in range(self.rel_num):
            mask = (edge_type == i)
            sub_edge_index = edge_index[:, mask]
            sub_edge_weight=edge_weight[mask]
            if mask.sum() !=0:
                rs=F.leaky_relu((self.propagate(sub_edge_index, x=emb,edge_weight=sub_edge_weight,edge_type=i)),self.negative_slope)
                rs_list+=[rs]
                rel_type+=[i]
        com_att=[]

        for ser,i in enumerate(rel_type):

            rel_emb=rs_list[ser]
            q_mat = self.cq_linears[i](emb)
            k_mat = self.ck_linears[i](rel_emb)
            res_att = ((q_mat * k_mat).sum(dim=-1) * self.crelation_pri[i] / math.sqrt(self.output_dim)).unsqueeze(1)

            com_att+=[res_att]

        com_attscore=torch.cat(com_att,dim=1)
        com_attscore=F.softmax(com_attscore,dim=1)
        res=0
        for i in range(len(com_att)):
            res+= com_attscore[:,i].unsqueeze(1) * self.cv_linear(rs_list[i])
        alpha=torch.sigmoid(self.skip)
        res=(res+alpha*F.gelu(emb))
        res_c,res_p=res[:company_num],res[company_num:]

        return res_c,res_p

    def message(self,edge_index, x_i,x_j, edge_weight, edge_type):
        if torch.sum(edge_weight)!=edge_index.shape[1]:
            x_j=self.rel_wi[edge_type](x_j)
            edge_weight=softmax(edge_weight,edge_index[1])
            rs=x_j*edge_weight
        else:
            node_f = torch.cat((x_i, x_j), 1)                                       #nx2d
            temp = self.rel_wi[edge_type](node_f).to(x_i.device)      #nx1

            alpha=softmax(temp,edge_index[1])

            rs=x_j*alpha
        return rs

    def update(self, inputs):
        return super().update(inputs)
 

class HyperGNN(nn.Module):
    def __init__(self,input_dim,output_dim,hyper_edge_num=3,num_layer=1,negative_slope=0.2):
        super(HyperGNN,self).__init__()
        self.negative_slope=negative_slope
        
        self.proj=nn.Linear(input_dim,output_dim,bias=False)
       
        self.alpha=nn.Parameter(torch.ones(hyper_edge_num,1))
        
        glorot(self.alpha)

    def forward(self,company_emb,hyp_graph):
        outlist=[]
        for i in range(len(hyp_graph)):
            laplacian=scipy_sparse_mat_to_torch_sparse_tensor(hyp_graph[i].laplacian())
            rs= laplacian@self.proj(company_emb)
            outlist+=[rs]
           
        res=0
       
        alpha=torch.sigmoid(self.alpha)
       
        for i in range(len(outlist)):
            res+=outlist[i]*alpha[i]
        return res

class HyperGNNVectorized(nn.Module):
    """Drop-in alternative to HyperGNN that takes raw incidence tensors (from
    utils.build_incidence) instead of precomputed scipy HyperG objects, and computes
    the Laplacian propagation via utils.hyper_laplacian (index_add/bincount) instead
    of a scipy sparse matrix product. Mathematically equivalent output to HyperGNN
    for uniform hyperedge weights (both default w=1); exists purely to remove the
    scipy dense-intermediate OOM at large node counts. Same interface (forward takes
    company_emb + a per-hyperedge-type list) except each list entry is a
    (node, group, count) tuple instead of a HyperG instance.
    """
    def __init__(self,input_dim,output_dim,hyper_edge_num=3,num_layer=1,negative_slope=0.2):
        super(HyperGNNVectorized,self).__init__()
        self.negative_slope=negative_slope
        self.proj=nn.Linear(input_dim,output_dim,bias=False)
        self.alpha=nn.Parameter(torch.ones(hyper_edge_num,1))
        glorot(self.alpha)

    def forward(self,company_emb,hyp_graph):
        z=self.proj(company_emb)
        dev = z.device
        alpha=torch.sigmoid(self.alpha)
        res=0
        for i,(node,group,count) in enumerate(hyp_graph):
            res=res+hyper_laplacian(z,node.to(dev),group.to(dev),count)*alpha[i]
        return res


#risk data: dict-->{company_index:[[cause type, court type, result category, time(months),time_label],...] }
class RiskInfo(nn.Module):
    def __init__(self,input_dim,company_num,cause_type_num,court_type_num,res_num,time_label_num,device=None):
        super(RiskInfo,self).__init__()
        self.input_dim=input_dim
        self.company_num=company_num
        self.time_lable_num=2
        self.device=device if device is not None else torch.device('cpu')


        self.ca_emb=nn.Embedding(cause_type_num,12)
        self.court_emb=nn.Embedding(court_type_num,4)
        self.cate_emb=nn.Embedding(res_num,4)
        self.lstm_hidden=20

        self.proj=nn.Linear(20,20,bias=False)


        self.time_decay=Decayer()


    def forward(self,risk_data):

        com_emb=torch.zeros((self.company_num,self.lstm_hidden),device=self.device)

        for index in risk_data:
            cause=self.ca_emb(torch.LongTensor(risk_data[index])[:,0].to(self.device))
            court=self.court_emb(torch.LongTensor(risk_data[index])[:,1].to(self.device))
            cate=self.cate_emb(torch.LongTensor(risk_data[index])[:,2].to(self.device))
            risk=torch.cat((cause,court,cate),dim=1)

            time_interval=torch.FloatTensor(risk_data[index])[:,3].to(self.device)

            time_interval=self.time_decay(time_interval).unsqueeze(1)

            risk=self.proj(time_interval*risk)

            com_emb[index]=risk.sum(0)
        return com_emb


class RiskGNN(nn.Module):
    def __init__(self,input_dim,output_dim,
    company_num,person_num,rel_num,cause_type_num,
     device,com_initial_emb,person_initial_emb,
     court_type_num=4,category_num=4,time_label_num=5,num_heads=1,dropout=0.2,norm=True,
     use_hypergraph=True,use_edgegraph=True,n_company_attr_dims=3,hyper_impl='scipy',
     ):
        super(RiskGNN,self).__init__()
        # Ablation switches: node-features-only (both False), +hypergraph, +edgegraph,
        # or the full model (both True, the original default -- backward compatible).
        self.use_hypergraph=use_hypergraph
        self.use_edgegraph=use_edgegraph
        # hyper_impl='scipy' (default, unchanged) expects hyp_graph as a list of
        # utils.HyperG (built by gen_attribute_hg) -- OOMs above ~50k companies.
        # hyper_impl='vectorized' expects hyp_graph as a list of (node,group,count)
        # tuples (built by utils.build_incidence) -- same math, no scipy, scales to
        # the full 634k-company Singapore graph.
        self.hyper_impl=hyper_impl
        self.input_dim=input_dim
        self.output_dim=output_dim
        self.company_num=company_num
        self.person_num=person_num
        self.rel_num=rel_num
        self.cause_type=cause_type_num
        self.device=device
        self.court_type=court_type_num
        self.category_=category_num
        self.num_heads=num_heads
        self.dropout=dropout
        self.norm=norm
        self.company_emb=torch.FloatTensor(com_initial_emb).to(device)
        self.person_emb=torch.FloatTensor(person_initial_emb).to(device)

        self.riskinfo=RiskInfo(input_dim,company_num,cause_type_num,court_type_num,category_num,time_label_num=time_label_num,device=device)
        if hyper_impl=='vectorized':
            self.hypergnn=HyperGNNVectorized(input_dim,output_dim,num_layer=1)
        else:
            self.hypergnn=HyperGNN(input_dim,output_dim,num_layer=1)
        self.hetegnn=nn.ModuleList()
        for i in range(5):
            if i==0:
                self.hetegnn.append(HeteGNN(input_dim,output_dim,rel_num))
            else:
                self.hetegnn.append(HeteGNN(output_dim,output_dim,rel_num))

        self.company_proj=nn.Linear(32,input_dim,bias=False)
        self.person_proj=nn.Linear(32,input_dim,bias=False)

        # input_dim + n_company_attr_dims (whatever company_attr actually carries --
        # 3 for the original ComRisk/single-prior setup, 11 for Wang's Protocol A
        # feature set) + 1 (community_prior slot, zeros if unused) + 20 (risk_info,
        # fixed by RiskInfo's lstm_hidden). Default n_company_attr_dims=3 reproduces
        # the original input_dim+24, so old callers are unaffected.
        self.risk_proj=nn.Linear(input_dim+n_company_attr_dims+21,input_dim,bias=False)
        self.info_proj=nn.Linear(output_dim,output_dim,bias=False)

        self.final_proj=nn.Sequential(nn.Linear(input_dim,output_dim,bias=False),nn.ReLU(),nn.Linear(output_dim,output_dim,bias=False))
        self.alpha=torch.ones((1),device=device)


    def forward_batch(self, company_attr_all, edge_index_local, edge_type_local, edge_weight_local,
                       n_id, batch_size, community_prior_all=None):
        """Mini-batch forward for the edge-graph (HeteGNN) path via neighbor sampling
        (e.g. torch_geometric.loader.NeighborLoader), added to fix the full-batch OOM
        at 2.1M nodes / 6M edges without needing more GPU memory (Wang's diagnosis:
        it's activation memory across 5 stacked layers, not the raw edge/node data).

        n_id: LongTensor of GLOBAL node indices in this sampled subgraph; by
        NeighborLoader convention the first `batch_size` entries are the seed/target
        nodes. edge_index_local/edge_type_local/edge_weight_local use LOCAL indices
        (0..len(n_id)-1) already renumbered by the loader.

        Deliberately skips the hypergraph and RiskInfo branches: both are global-
        index-dependent (don't subgraph-batch naturally) and, per the node_only vs
        node_hyper ablation result (2026-09-26, ROC 0.8040 vs 0.8042 -- no measurable
        difference), the hypergraph carries no value worth the complication anyway.
        This makes the comparison node_only vs node_edge (this method), which is
        exactly the exogenous-graph question Wang's message asked to isolate.
        """
        n = len(n_id)
        n_id_np = n_id.detach().cpu().numpy()
        company_emb = self.company_proj(self.company_emb[n_id])
        person_emb = self.person_proj(self.person_emb)
        attr = torch.as_tensor(company_attr_all[n_id_np], dtype=torch.float32, device=self.device)
        if community_prior_all is not None:
            prior = torch.as_tensor(community_prior_all[n_id_np], dtype=torch.float32, device=self.device).unsqueeze(1)
        else:
            prior = torch.zeros((n, 1), device=self.device)
        company_basic_info = torch.cat((attr, prior), dim=1)
        company_emb = torch.cat((company_emb, company_basic_info), dim=1)
        risk_info = torch.zeros((n, 20), device=self.device)  # risk_data is an empty table for this dataset
        company_emb_info = self.risk_proj(torch.cat((company_emb, risk_info), dim=1))

        if edge_index_local.shape[0] > 0:
            for i in range(5):
                src = company_emb_info if i == 0 else company_emb_hete
                company_emb_hete, person_emb = self.hetegnn[i](
                    src, person_emb, edge_index_local, edge_type_local, edge_weight_local, n, 0)
        else:
            company_emb_hete = torch.zeros((n, self.output_dim), device=self.device)

        company_emb_final = self.info_proj(company_emb_hete)
        alpha = torch.sigmoid(self.alpha)
        company_emb_final = alpha * F.gelu(company_emb_final) + (1 - alpha) * self.final_proj(company_emb_info)
        return company_emb_final[:batch_size]

    # risk data: dict-->{company_index:[[cause type, court type, category, time(months),time_label],...] }
    # company attribute information: np.array()-->[[register_captial, paid_captial, set up time(months)]]
    # graph: edge index:[sour,tar].T -->2xN; edge type: [,,...,] -->N; edge weight:[,,...,]-->N
    # hyper graph: dict:{industry:{ind1:[...],ind2:[...],...},area:{area1:[...],area2:[...],...},qualify:{qua1:[...],qua2:[...],...}}
    def forward(self,risk_data,company_attr,hete_graph,hyp_graph,idx,x,community_prior=None):
        company_emb=self.company_proj(self.company_emb)
        person_emb=self.person_proj(self.person_emb)
        company_basic_info=torch.zeros((self.company_num,len(company_attr[0])),device=self.device)

        company_basic_info[idx]=torch.Tensor(company_attr).to(self.device)

        # Bayesian-smoothed community (region/country) risk prior, one scalar per
        # company, computed by utils.fit_bayesian_group_prior/build_group_prior_feature.
        # Defaults to zeros (neutral) if the caller doesn't supply one, so this stays
        # backward-compatible with any existing caller that doesn't pass it.
        community_feat = torch.zeros((self.company_num, 1),device=self.device)
        if community_prior is not None:
            community_feat[idx] = torch.Tensor(community_prior).to(self.device)
        company_basic_info = torch.cat((company_basic_info, community_feat), dim=1)

        company_emb=torch.cat((company_emb,company_basic_info),dim=1)
        risk_info=self.riskinfo(risk_data)
        company_emb_info=self.risk_proj(torch.cat((company_emb,risk_info),dim=1))

        if self.use_hypergraph:
            company_emb_hyper=self.hypergnn(company_emb_info,hyp_graph)
        else:
            company_emb_hyper=torch.zeros((self.company_num,self.output_dim),device=self.device)

        if self.use_edgegraph:
            edge_index,edge_type,edge_weight=hete_graph
            for i in range(5):
                if i==0:
                    company_emb_hete,person_emb=self.hetegnn[i](company_emb_info,person_emb,edge_index,edge_type,edge_weight,self.company_num,self.person_num)
                else:
                    company_emb_hete,person_emb=self.hetegnn[i](company_emb_hete,person_emb,edge_index,edge_type,edge_weight,self.company_num,self.person_num)
        else:
            company_emb_hete=torch.zeros((self.company_num,self.output_dim),device=self.device)
        company_emb_final=self.info_proj(company_emb_hyper+company_emb_hete)

        alpha=torch.sigmoid(self.alpha)
        company_emb_final=alpha*F.gelu(company_emb_final)+(1-alpha)*self.final_proj(company_emb_info)

        return company_emb_final[idx]
