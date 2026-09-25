"""Local inference API. Configure artifacts explicitly; never train on a request."""
from contextlib import asynccontextmanager
import os
import json
from pathlib import Path
from collections import Counter

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from .data import Dataset
from .pipeline import Predictor


class Request(BaseModel):
    model_config = ConfigDict(extra="forbid")
    company_ids: list[str] = Field(min_length=1, max_length=1000)


@asynccontextmanager
async def lifespan(app):
    app.state.predictor = Predictor(os.environ["COMRISK_MODEL_DIR"])
    app.state.dataset = Dataset.read(os.environ["COMRISK_DATA_PATH"])
    # Validate schema and target semantics at startup, not on the first user request.
    result = app.state.predictor.predict(app.state.dataset)
    app.state.predictions = {r['company_id']: r for r in result['predictions']}
    app.state.nodes = {n.id: n for n in app.state.dataset.nodes}
    app.state.event_counts = Counter(e.company for e in app.state.dataset.events)
    metric_path = Path(os.environ['COMRISK_MODEL_DIR']) / 'metrics.json'
    app.state.metrics = json.loads(metric_path.read_text()) if metric_path.exists() else None
    yield


app = FastAPI(title="ComRisk research inference", version="0.1.0", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok", "model": app.state.predictor.meta["model"],
            "synthetic_training": app.state.predictor.meta["synthetic"], "calibrated": app.state.predictor.meta["calibrated"]}


@app.post("/v1/predict")
def predict(request: Request):
    try:
        return app.state.predictor.predict(app.state.dataset, request.company_ids)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.get('/v1/model-card')
def model_card():
    meta=app.state.predictor.meta
    return {k:v for k,v in meta.items() if k not in {'prior','preprocessor'}}


@app.get('/v1/explain/{company_id}')
def explanation(company_id: str):
    from .explain import explain
    try:
        return explain(app.state.predictor,app.state.dataset,company_id)
    except ValueError as error:
        raise HTTPException(status_code=404,detail=str(error)) from error


def company_node(company_id):
    node = app.state.nodes.get(company_id)
    if node is None or node.kind != 'company':
        raise HTTPException(status_code=404, detail='unknown company ID')
    return node


def company_summary(node):
    return {'id': node.id, 'name': f'匿名企业 {node.id}', 'community': node.community,
            'split': node.split, 'event_count': app.state.event_counts[node.id],
            **app.state.predictions[node.id]}


@app.get('/v1/companies')
def companies(q: str = '', offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100)):
    query = q.strip().casefold()
    nodes = [n for n in app.state.dataset.nodes if n.kind == 'company'
             and (not query or query in n.id.casefold() or query in n.community.casefold())]
    return {'total': len(nodes), 'offset': offset, 'limit': limit,
            'dataset': app.state.dataset.name,
            'items': [company_summary(n) for n in nodes[offset:offset+limit]]}


@app.get('/v1/companies/{company_id}')
def company_detail(company_id: str):
    node = company_node(company_id)
    data = app.state.dataset
    return {**company_summary(node), 'dataset': data.name,
            'features': dict(zip(data.feature_names, node.features)),
            'observed_label': node.label,
            'events': [e.model_dump() for e in data.events if e.company == company_id][:20],
            'events_limit': 20,
            'label_note': 'Observed benchmark label, displayed only for evaluation; not a model input.'}


@app.get('/v1/companies/{company_id}/graph')
def company_graph(company_id: str, limit: int = Query(30, ge=1, le=100)):
    company_node(company_id)
    edges = [e for e in app.state.dataset.edges if company_id in (e.source, e.target)]
    shown = edges[:limit]
    ids = {company_id} | {e.source for e in shown} | {e.target for e in shown}
    return {'center': company_id, 'total_edges': len(edges), 'truncated': len(edges) > limit,
            'edges': [e.model_dump() for e in shown],
            'nodes': [{'id': i, 'kind': app.state.nodes[i].kind,
                       'community': app.state.nodes[i].community} for i in sorted(ids)],
            'note': 'Directed one-hop observed relations; codes are not inferred business semantics.'}


@app.get('/v1/evaluation')
def evaluation():
    metrics = app.state.metrics
    if metrics is None:
        raise HTTPException(status_code=503, detail='Evaluation artifact unavailable')
    meta = app.state.predictor.meta
    return {'model': meta['model'], 'mode': meta['mode'], 'seed': meta['seed'],
            'dataset': app.state.dataset.name, 'training_dataset': meta['dataset'],
            'synthetic': meta['synthetic'], 'threshold': meta['threshold'],
            'best_epoch': meta['best_epoch'], 'calibration': meta['calibration'],
            'metrics': metrics['model'], 'notes': metrics['notes'],
            'feature_names': app.state.dataset.feature_names,
            'company_count': len(app.state.predictions),
            'relation_count': len(app.state.dataset.edges)}
