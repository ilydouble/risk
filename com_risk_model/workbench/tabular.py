from __future__ import annotations

import io
import time
from dataclasses import dataclass
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, OrdinalEncoder, StandardScaler

from workbench.data import BundleData
from workbench.features import FeatureSelection, graph_statistics, select_features
from workbench.metrics import evaluate, select_threshold


@dataclass(frozen=True)
class FittedVariant:
    name: str
    result: dict[str, Any]
    artifact: bytes


@dataclass(frozen=True)
class TabularSuite:
    selection: FeatureSelection
    variants: list[FittedVariant]


def _columns(data: BundleData, names: list[str]) -> tuple[list[str], list[str]]:
    definitions = {feature.name: feature.kind for feature in data.metadata.features}
    numeric = [name for name in names if definitions.get(name, "numeric") == "numeric"]
    categorical = [name for name in names if definitions.get(name) == "categorical"]
    return numeric, categorical


def _preprocessor(
    numeric: list[str], categorical: list[str], *, linear: bool
) -> ColumnTransformer:
    transformers: list[tuple[str, Pipeline, list[str]]] = []
    if numeric:
        numeric_steps: list[tuple[str, Any]] = [("imputer", SimpleImputer(strategy="median"))]
        if linear:
            numeric_steps.append(("scaler", StandardScaler()))
        transformers.append(("numeric", Pipeline(numeric_steps), numeric))
    if categorical:
        encoder: Any
        if linear:
            encoder = OneHotEncoder(handle_unknown="ignore")
        else:
            encoder = OrdinalEncoder(
                handle_unknown="use_encoded_value", unknown_value=-1, encoded_missing_value=-2
            )
        transformers.append(
            (
                "categorical",
                Pipeline(
                    [
                        ("imputer", SimpleImputer(strategy="most_frequent")),
                        ("encoder", encoder),
                    ]
                ),
                categorical,
            )
        )
    return ColumnTransformer(transformers, remainder="drop")


def _artifact(pipeline: Pipeline) -> bytes:
    stream = io.BytesIO()
    joblib.dump(pipeline, stream, compress=3)
    return stream.getvalue()


def _explain(
    name: str,
    pipeline: Pipeline,
    validation_x: pd.DataFrame,
    validation_y: np.ndarray,
    seed: int,
) -> dict[str, Any]:
    if name == "logistic_regression":
        preprocess: ColumnTransformer = pipeline.named_steps["preprocess"]
        model: LogisticRegression = pipeline.named_steps["model"]
        names = preprocess.get_feature_names_out()
        values = model.coef_[0]
        coefficient_items: list[dict[str, Any]] = [
            {"feature": str(feature), "value": float(value)}
            for feature, value in zip(names, values, strict=True)
        ]
        items = sorted(
            coefficient_items,
            key=lambda item: abs(float(item["value"])),
            reverse=True,
        )[:100]
        return {"type": "coefficient", "items": items}
    importance = permutation_importance(
        pipeline,
        validation_x,
        validation_y,
        scoring="roc_auc",
        n_repeats=3,
        random_state=seed,
        n_jobs=1,
    )
    importance_items: list[dict[str, Any]] = [
        {"feature": name, "value": float(value)}
        for name, value in zip(validation_x.columns, importance.importances_mean, strict=True)
    ]
    items = sorted(
        importance_items,
        key=lambda item: float(item["value"]),
        reverse=True,
    )
    return {"type": "permutation_importance", "items": items}


def _fit_variant(
    name: str,
    frame: pd.DataFrame,
    feature_names: list[str],
    numeric: list[str],
    categorical: list[str],
    positive_value: object,
    seed: int,
) -> FittedVariant:
    started = time.monotonic()
    train = frame[frame["split"] == "train"]
    validation = frame[frame["split"] == "validation"]
    test = frame[frame["split"] == "test"]
    def target(rows: pd.DataFrame) -> np.ndarray:
        return (rows["target"].astype(str) == str(positive_value)).astype(int).to_numpy()
    linear = name == "logistic_regression"
    estimator: Any
    if linear:
        estimator = LogisticRegression(
            max_iter=1000, class_weight="balanced", random_state=seed, solver="lbfgs"
        )
    else:
        estimator = HistGradientBoostingClassifier(
            learning_rate=0.08,
            max_iter=250,
            max_leaf_nodes=31,
            l2_regularization=0.1,
            early_stopping=False,
            random_state=seed,
            class_weight="balanced",
        )
    pipeline = Pipeline(
        [("preprocess", _preprocessor(numeric, categorical, linear=linear)), ("model", estimator)]
    )
    pipeline.fit(train[feature_names], target(train))
    validation_probability = pipeline.predict_proba(validation[feature_names])[:, 1]
    test_probability = pipeline.predict_proba(test[feature_names])[:, 1]
    validation_target = target(validation)
    threshold = select_threshold(validation_target, validation_probability)
    result = {
        "name": name,
        "role": "evaluation_baseline",
        "status": "completed",
        "metrics": {
            "validation": evaluate(validation_target, validation_probability, threshold),
            "test": evaluate(target(test), test_probability, threshold),
        },
        "explainability": _explain(
            name, pipeline, validation[feature_names], validation_target, seed
        ),
        "configuration": {
            "fitSplit": "train",
            "thresholdSplit": "validation",
            "featureCount": len(feature_names),
            "seed": seed,
        },
        "durationSeconds": time.monotonic() - started,
    }
    return FittedVariant(name, result, _artifact(pipeline))


def train_tabular_suite(
    data: BundleData,
    *,
    requested_models: list[str],
    feature_mode: str,
    manual_features: list[str],
    seed: int,
) -> TabularSuite:
    selection = select_features(data, mode=feature_mode, manual=manual_features)
    frame = data.samples.copy()
    variants: list[FittedVariant] = []
    numeric, categorical = _columns(data, selection.selected)
    if "logistic_regression" in requested_models:
        variants.append(
            _fit_variant(
                "logistic_regression",
                frame,
                selection.selected,
                numeric,
                categorical,
                data.metadata.target.positive_value,
                seed,
            )
        )
    if "hist_gradient_boosting" in requested_models:
        variants.append(
            _fit_variant(
                "hist_gradient_boosting",
                frame,
                selection.selected,
                numeric,
                categorical,
                data.metadata.target.positive_value,
                seed,
            )
        )
    if "graph_stats_hgb" in requested_models:
        graph = graph_statistics(data)
        frame = frame.merge(graph, on="sample_id", how="left", validate="one_to_one")
        graph_features = [column for column in graph.columns if column != "sample_id"]
        variants.append(
            _fit_variant(
                "graph_stats_hgb",
                frame,
                selection.selected + graph_features,
                numeric + graph_features,
                categorical,
                data.metadata.target.positive_value,
                seed,
            )
        )
    return TabularSuite(selection, variants)
