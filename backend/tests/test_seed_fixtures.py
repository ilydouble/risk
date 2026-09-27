from risk_api.modules.company.api.schemas import CompanyDTO, CompanyProfile
from risk_api.modules.graph.api.schemas import GraphData
from risk_api.modules.overview.api.schemas import ResponseGetOverview, ResponseGetOverviewCompany
from risk_api.modules.score.api.schemas import ScoreDetail
from risk_api.seed import load_demo_records, load_overview_records


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


def test_singapore_overview_fixture_is_real_and_stratified() -> None:
    records = load_overview_records()
    assert len(records) == 1
    record = records[0]
    snapshot = ResponseGetOverview.model_validate(record)

    assert snapshot.dataset.id == "sg-comrisk-v2-profile-v1-20260927"
    assert snapshot.dataset.sourceArchiveSha256 == (
        "7a1148ecae3608aa4d7471f38217c45960def2d9dd87f7edfc3b93268ca1fcbe"
    )
    assert snapshot.stats.companyCount == 2_111_884
    assert snapshot.stats.labeledCount == 634_646
    assert snapshot.stats.distressCount == 13_328
    assert snapshot.sampling.sampleCount == 300
    assert snapshot.sampling.representative is False
    assert {
        category: sum(item.labelCategory == category for item in snapshot.sampleCompanies)
        for category in ("healthy", "distress", "unlabeled")
    } == {"healthy": 100, "distress": 100, "unlabeled": 100}

    profiles = [
        ResponseGetOverviewCompany.model_validate(
            {
                "profileVersion": 1,
                "dataset": record["dataset"],
                "sampling": record["sampling"],
                "company": sample,
                "facts": sample["facts"],
                "observedLabel": {
                    "category": sample["labelCategory"],
                    "status": sample["status"],
                    "taskType": record["dataset"]["taskType"],
                    "modelOutput": False,
                },
                "relations": sample["relationProfile"],
                "groups": sample["groups"],
                "dataAvailability": sample["dataAvailability"],
                "warnings": record["warnings"],
            }
        )
        for sample in record["sampleCompanies"]
    ]
    assert len(profiles) == 300
    assert max(profile.relations.totalCount for profile in profiles) == 199
    assert all(len(profile.relations.neighbors) <= 12 for profile in profiles)
