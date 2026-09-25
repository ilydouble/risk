from risk_api.modules.company.api.schemas import CompanyDTO, CompanyProfile
from risk_api.modules.graph.api.schemas import GraphData
from risk_api.modules.score.api.schemas import ScoreDetail
from risk_api.seed import load_demo_records


def test_demo_fixtures_cover_the_selected_company_contract() -> None:
    records = load_demo_records()
    ids = [record["company"]["id"] for record in records]
    assert ids == [f"C-{number}" for number in range(1001, 1009)]

    for record in records:
        company = CompanyDTO.model_validate(record["company"])
        CompanyProfile.model_validate(record["profile"])
        for lang in ("zh", "en"):
            ScoreDetail.model_validate(record["scores"][lang])
            graph = GraphData.model_validate(record["graphs"][lang])
            assert graph.rootId == company.id
            assert {node.hop for node in graph.nodes} >= {0, 2, 3}
            assert all(node.companyId is None or node.companyId in ids for node in graph.nodes)
