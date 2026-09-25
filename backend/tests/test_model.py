import copy
import numpy as np
import pytest
import torch
from pydantic import ValidationError
from fastapi.testclient import TestClient

from comrisk.data import Dataset, fit_preprocessor, tensorize
from comrisk.demo import generate
from comrisk.model import ComRisk, hyper_laplacian, segment_softmax, RelationLayer
from comrisk.pipeline import train, Predictor, metrics
from comrisk.prior import fit_prior, add_prior


def test_hyper_laplacian_matches_dense_and_gradient():
    x = torch.randn(4, 3, requires_grad=True)
    node = torch.tensor([0, 1, 1, 2]); group = torch.tensor([0, 0, 1, 1])
    h = torch.tensor([[1.,0.], [1.,1.], [0.,1.], [0.,0.]])
    inv = h.sum(1).clamp_min(1).rsqrt().diag()
    expected = (torch.eye(4)-inv@h@torch.diag(1/h.sum(0))@h.T@inv)@x
    expected = expected * (h.sum(1)>0)[:,None]
    actual = hyper_laplacian(x,node,group,2)
    torch.testing.assert_close(actual, expected)
    actual.sum().backward()
    assert torch.isfinite(x.grad).all()


def test_softmax_grouped_stable():
    target = torch.tensor([0,0,2])
    result = segment_softmax(torch.tensor([1000.,1000.,-1000.]),target,4)
    torch.testing.assert_close(result,torch.tensor([.5,.5,1.]))


def test_direction_only_receiving_node_changes():
    torch.manual_seed(1)
    layer = RelationLayer(4,1,0).eval()
    x = torch.randn(3,4)
    edge = [(torch.tensor([0]),torch.tensor([1]),torch.ones(1))]
    before = layer(x,edge)
    changed = x.clone(); changed[0] += torch.tensor([2.,-3.,1.,4.])
    after = layer(changed,edge)
    torch.testing.assert_close(before[2],after[2])
    assert not torch.allclose(before[1],after[1])


def test_empty_graph_finite_and_permutation_equivariant():
    d = generate(100); d.edges=[]; d.hyperedges=[]
    g = tensorize(d,fit_preprocessor(d)); add_prior(g,d,fit_prior(d))
    model=ComRisk(18,2,3,hidden=8).eval()
    output=model(g)
    assert output.shape==(100,) and torch.isfinite(output).all()
    perm=torch.randperm(100)
    gp=dict(g); gp['x']=g['x'][perm];gp['kinds']=g['kinds'][perm];gp['prior']=g['prior'][perm]
    torch.testing.assert_close(model(gp),output[perm])


def test_scaler_and_prior_ignore_heldout_labels_and_features():
    d=generate(100); other=d.model_copy(deep=True)
    for n in other.nodes:
        if n.split!='train': n.features=[1e8]*18; n.label=1-n.label
    assert fit_preprocessor(d)==fit_preprocessor(other)
    assert fit_prior(d)==fit_prior(other)


def test_schema_rejects_broken_edges_and_nonfinite():
    d=generate(100).model_dump()
    d['edges'][0]['target']='absent'
    with pytest.raises(ValidationError): Dataset.model_validate(d)
    d=generate(100).model_dump();d['nodes'][0]['features'][0]=float('inf')
    with pytest.raises(ValidationError): Dataset.model_validate(d)


def test_metrics_known_ranking():
    m=metrics([0,0,1,1],[.1,.2,.8,.9])
    assert m['roc_auc']==1 and m['ks']==1 and m['lift_at_10pct']==2
    assert m['capture_at_5pct']==.5


@pytest.fixture(scope='module')
def trained(tmp_path_factory):
    path=tmp_path_factory.mktemp('model');d=generate(100)
    report=train(d,path,epochs=3,patience=2,hidden=8,pretrain_epochs=2)
    return path,d,report


def test_reload_inference_and_new_company(trained):
    path,d,report=trained
    predictor=Predictor(path)
    a=predictor.predict(d); b=Predictor(path).predict(d)
    assert a==b
    ids=[n.id for n in d.nodes if n.split=='test']
    vals={r['company_id']:r['risk_probability'] for r in a['predictions']}
    measured=metrics([n.label for n in d.nodes if n.split=='test'],[vals[i] for i in ids],a['threshold'])
    assert measured['roc_auc']==report['model']['test']['roc_auc']
    # Neither labels nor split masks affect forward inference.
    unlabeled=d.model_copy(deep=True)
    for n in unlabeled.nodes:n.label=None;n.split=None
    assert predictor.predict(unlabeled)==a
    new=unlabeled.nodes[0].model_copy(deep=True);new.id='NEW';unlabeled.nodes.append(new)
    assert len(predictor.predict(unlabeled,['NEW'])['predictions'])==1
    with pytest.raises(ValueError):predictor.predict(d,['missing'])


def test_api(trained,monkeypatch,tmp_path):
    from comrisk.api import app
    path,d,_=trained;data=tmp_path/'input.json';d.write(data)
    monkeypatch.setenv('COMRISK_MODEL_DIR',str(path));monkeypatch.setenv('COMRISK_DATA_PATH',str(data))
    with TestClient(app) as client:
        assert client.get('/health').status_code==200
        assert client.post('/v1/predict',json={'company_ids':['C00000']}).status_code==200
        assert client.post('/v1/predict',json={'company_ids':['nope']}).status_code==422
        assert client.post('/v1/predict',json={'company_ids':[]}).status_code==422


def test_explanation_is_honest_sensitivity(trained):
    from comrisk.explain import explain
    path,d,_=trained
    result=explain(Predictor(path),d,'C00000')
    assert len(result['features'])==18
    assert result['method']=='feature_occlusion_to_training_mean'
    assert all(np.isfinite(r['probability_delta']) for r in result['features'])


def test_isolated_snapshot_overlap_rejected(tmp_path):
    d=generate(100)
    snapshots={}
    for split in ('train','valid','test'):
        clone=d.model_copy(deep=True)
        for n in clone.nodes:n.split=split
        snapshots[split]=clone
    with pytest.raises(ValueError,match='overlap'):
        train(snapshots,tmp_path,epochs=1)


def test_public_data_splits_disjoint_when_available():
    from pathlib import Path
    from comrisk.pipeline import load_data
    path=Path('data/processed/smesd')
    if not path.exists():pytest.skip('public dataset not fetched')
    ds=load_data(path)
    ids=[{n.id for n in ds[s].nodes if n.kind=='company'} for s in ('train','valid','test')]
    assert [len(i) for i in ids]==[2816,686,474]
    assert not (ids[0]&ids[1] or ids[0]&ids[2] or ids[1]&ids[2])


def test_demo_api_contract_and_error_states(trained, monkeypatch, tmp_path):
    from comrisk.api import app
    path, data, report = trained
    data_path = tmp_path / 'snapshot.json'
    data.write(data_path)
    monkeypatch.setenv('COMRISK_MODEL_DIR', str(path))
    monkeypatch.setenv('COMRISK_DATA_PATH', str(data_path))
    with TestClient(app) as client:
        listing = client.get('/v1/companies', params={'limit': 2}).json()
        assert listing['total'] == sum(n.kind == 'company' for n in data.nodes)
        assert len(listing['items']) == 2
        company_id = listing['items'][0]['id']
        detail = client.get(f'/v1/companies/{company_id}').json()
        prediction = client.post('/v1/predict', json={'company_ids': [company_id]}).json()['predictions'][0]
        assert detail['risk_probability'] == prediction['risk_probability']
        assert detail['features'] == dict(zip(data.feature_names, data.nodes[0].features))
        explanation = client.get(f'/v1/explain/{company_id}').json()
        assert explanation['risk_probability'] == prediction['risk_probability']
        graph = client.get(f'/v1/companies/{company_id}/graph', params={'limit': 1}).json()
        expected = [e.model_dump() for e in data.edges if company_id in (e.source, e.target)]
        assert graph['edges'] == expected[:1]
        assert graph['total_edges'] == len(expected)
        assert graph['truncated'] == (len(expected) > 1)
        assert all(e[k] in {n['id'] for n in graph['nodes']} for e in graph['edges'] for k in ('source', 'target'))
        assert client.get('/v1/evaluation').json()['metrics']['test'] == report['model']['test']
        assert client.get('/v1/companies?q=not-a-company').json()['items'] == []
        assert client.get('/v1/companies?offset=-1').status_code == 422
        assert client.get('/v1/companies?limit=101').status_code == 422
        assert client.get('/v1/companies/unknown').status_code == 404
        assert client.get('/v1/companies/unknown/graph').status_code == 404
