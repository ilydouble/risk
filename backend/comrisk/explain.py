"""Local feature occlusion sensitivity. These values are not SHAP or causal effects."""
import copy
import torch
from .data import tensorize
from .prior import add_prior


def explain(predictor, data, company_id):
    index=next((i for i,n in enumerate(data.nodes) if n.id==company_id and n.kind=='company'),None)
    if index is None: raise ValueError('unknown company ID')
    base=predictor.predict(data,[company_id])['predictions'][0]['risk_probability']
    graph=tensorize(data,predictor.meta['preprocessor'])
    if predictor.meta['prior']:add_prior(graph,data,predictor.meta['prior'])
    width=len(data.feature_names);contributions=[]
    with torch.no_grad():
        for j,name in enumerate(data.feature_names):
            masked=dict(graph);masked['x']=graph['x'].clone()
            # Replace feature by the fitted training mean; keep observed/missing status.
            masked['x'][index,j]=0
            p=(predictor.model(masked,predictor.meta['mode'])[index]+predictor.meta['calibration']['intercept']).sigmoid().item()
            contributions.append({'feature':name,'value':data.nodes[index].features[j],
                                  'probability_without_feature':p,'probability_delta':base-p})
    edges=[e.model_dump() for e in data.edges if e.target==company_id]
    return {'company_id':company_id,'risk_probability':base,'method':'feature_occlusion_to_training_mean',
            'interpretation':'Sensitivity only; not SHAP, not additive, not evidence of causality.',
            'features':sorted(contributions,key=lambda r:abs(r['probability_delta']),reverse=True),
            'incoming_edges':edges[:50], 'incoming_edge_count':len(edges)}
