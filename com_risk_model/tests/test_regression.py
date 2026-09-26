"""Selected SMEsD v1 numerics; run with --require-model for release acceptance."""

import pytest
import torch
from com_risk_runtime.explain import explain
from com_risk_runtime.predictor import Predictor


@pytest.mark.model_integration
def test_selected_model_predictions_and_explanation(real_model):
    model, bundle = real_model
    torch.set_num_threads(1)
    predictor = Predictor(model)
    ids = ["C00010", "C00024", "C00010"]
    rows = predictor.predict(bundle.dataset, ids)["predictions"]
    assert [r["company_id"] for r in rows] == ids
    assert [r["risk_probability"] for r in rows] == pytest.approx(
        [0.7268730401992798, 0.7064450979232788, 0.7268730401992798], abs=1e-6
    )
    assert rows[0] == rows[2]
    assert bundle.manifest.snapshot.company_count == 474
    assert sum(e.source == "C00010" or e.target == "C00010" for e in bundle.dataset.edges) == 16
    assert bundle.metrics["model"]["test"]["roc_auc"] == pytest.approx(0.793637480738848)
    explanation = explain(predictor, bundle.dataset, "C00010")
    assert explanation["method"] == "feature_occlusion_to_training_mean"
    assert explanation["risk_probability"] == rows[0]["risk_probability"]
    deltas = {f["feature"]: f["probability_delta"] for f in explanation["features"]}
    assert deltas == pytest.approx(
        {
            "log_registered_capital": -0.21279561519622803,
            "log_paid_capital": -0.1985621452331543,
            "age_months": -0.19199049472808838,
        },
        abs=1e-6,
    )
