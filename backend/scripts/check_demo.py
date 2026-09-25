"""Verify the running frontend proxy against the saved model artifacts."""
import json
import os
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
BASE = os.environ.get('COMRISK_DEMO_URL', 'http://127.0.0.1:3000') + '/api'

def get(path, body=None):
    request = Request(BASE + path, data=json.dumps(body).encode() if body else None,
                      headers={'Content-Type': 'application/json'})
    with urlopen(request, timeout=20) as response:
        return json.load(response)

def main():
    listing = get('/v1/companies?limit=2')
    company_id = listing['items'][0]['id']
    company = get(f'/v1/companies/{company_id}')
    prediction = get('/v1/predict', {'company_ids': [company_id]})['predictions'][0]
    explanation = get(f'/v1/explain/{company_id}')
    assert company['risk_probability'] == prediction['risk_probability'] == explanation['risk_probability']
    graph = get(f'/v1/companies/{company_id}/graph')
    assert all(company_id in (e['source'], e['target']) for e in graph['edges'])
    selected = Path(json.loads((ROOT / 'artifacts/smesd-v1/summary.json').read_text())['selected_artifact']).name
    saved = json.loads((ROOT / 'artifacts/smesd-v1' / selected / 'metrics.json').read_text())
    evaluation = get('/v1/evaluation')
    assert evaluation['metrics'] == saved['model']
    assert listing['total'] == evaluation['company_count'] == 474
    assert get('/v1/companies?q=missing-company')['items'] == []
    print(json.dumps({'status': 'passed', 'company_id': company_id,
                      'risk_probability': prediction['risk_probability'], 'companies': listing['total'],
                      'relation_edges': graph['total_edges'], 'test_auc': evaluation['metrics']['test']['roc_auc']}, indent=2))

if __name__ == '__main__':
    main()
