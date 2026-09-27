from __future__ import annotations

import io
import math
import random
import time
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
import torch
from torch import nn

from workbench.data import BundleData
from workbench.metrics import evaluate, select_threshold
from workbench.tabular import FittedVariant


@dataclass(frozen=True)
class EncodedColumn:
    name: str
    kind: str
    median: float | None = None
    mean: float | None = None
    std: float | None = None
    vocabulary: dict[str, int] | None = None


@dataclass
class GraphBatch:
    sample_numeric: torch.Tensor
    sample_categorical: torch.Tensor
    node_numeric: torch.Tensor
    node_categorical: torch.Tensor
    node_type: torch.Tensor
    sample_node: torch.Tensor
    edge_source: torch.Tensor
    edge_target: torch.Tensor
    edge_type: torch.Tensor
    edge_weight: torch.Tensor
    event_node: torch.Tensor
    event_type: torch.Tensor
    event_amount: torch.Tensor
    event_decay: torch.Tensor
    hyper_node: torch.Tensor
    hyperedge: torch.Tensor
    hyper_type: torch.Tensor
    split: np.ndarray
    target: torch.Tensor
    sample_columns: list[EncodedColumn]
    node_columns: list[EncodedColumn]
    vocabularies: dict[str, dict[str, int]]


def _fit_columns(
    frame: pd.DataFrame,
    fit_mask: np.ndarray,
    definitions: list[tuple[str, str]],
) -> tuple[torch.Tensor, torch.Tensor, list[EncodedColumn], list[int]]:
    numeric_values: list[np.ndarray] = []
    categorical_values: list[np.ndarray] = []
    columns: list[EncodedColumn] = []
    category_sizes: list[int] = []
    for name, kind in definitions:
        if kind == "numeric":
            values = pd.to_numeric(frame[name], errors="coerce")
            fit = values[fit_mask]
            median = float(fit.median()) if fit.notna().any() else 0.0
            filled = values.fillna(median)
            mean = float(filled[fit_mask].mean())
            std = float(filled[fit_mask].std(ddof=0)) or 1.0
            scaled = ((filled - mean) / std).clip(-10, 10).to_numpy(dtype=np.float32)
            missing = values.isna().to_numpy(dtype=np.float32)
            numeric_values.extend([scaled, missing])
            columns.append(EncodedColumn(name, kind, median, mean, std))
        else:
            values = frame[name].astype("string").fillna("__MISSING__")
            vocabulary = {
                value: index + 1
                for index, value in enumerate(sorted(set(values[fit_mask].astype(str))))
            }
            encoded = values.astype(str).map(vocabulary).fillna(0).to_numpy(dtype=np.int64)
            categorical_values.append(encoded)
            category_sizes.append(len(vocabulary) + 1)
            columns.append(EncodedColumn(name, kind, vocabulary=vocabulary))
    numeric = (
        torch.tensor(np.stack(numeric_values, axis=1))
        if numeric_values
        else torch.zeros((len(frame), 0), dtype=torch.float32)
    )
    categorical = (
        torch.tensor(np.stack(categorical_values, axis=1))
        if categorical_values
        else torch.zeros((len(frame), 0), dtype=torch.long)
    )
    return numeric, categorical, columns, category_sizes


def _vocabulary(values: pd.Series, mask: np.ndarray) -> dict[str, int]:
    fit = values[mask].astype("string").fillna("__MISSING__").astype(str)
    return {value: index + 1 for index, value in enumerate(sorted(set(fit)))}


def _encode(values: pd.Series, vocabulary: dict[str, int]) -> torch.Tensor:
    encoded = (
        values.astype("string")
        .fillna("__MISSING__")
        .astype(str)
        .map(vocabulary)
        .fillna(0)
        .to_numpy(dtype=np.int64)
    )
    return torch.tensor(encoded, dtype=torch.long)


def prepare_graph_batch(
    data: BundleData,
    selected_features: list[str],
    *,
    use_events: bool,
) -> tuple[GraphBatch, list[int], list[int]]:
    if data.nodes is None or data.relations is None:
        raise ValueError("nodes and relations are required for GNN variants")
    samples = data.samples.reset_index(drop=True).copy()
    train_mask = samples["split"].to_numpy() == "train"
    definitions = {feature.name: feature.kind for feature in data.metadata.features}
    sample_numeric, sample_categorical, sample_columns, sample_category_sizes = _fit_columns(
        samples,
        train_mask,
        [(name, definitions[name]) for name in selected_features],
    )
    nodes = data.nodes.reset_index(drop=True).copy()
    nodes["graph_snapshot_id"] = nodes["graph_snapshot_id"].astype(str)
    nodes["node_id"] = nodes["node_id"].astype(str)
    node_keys = list(
        nodes[["graph_snapshot_id", "node_id"]].itertuples(index=False, name=None)
    )
    node_index = {key: index for index, key in enumerate(node_keys)}
    sample_keys = list(
        zip(
            samples["graph_snapshot_id"].astype(str),
            samples["entity_id"].astype(str),
            strict=True,
        )
    )
    sample_node = torch.tensor([node_index[key] for key in sample_keys], dtype=torch.long)
    fit_nodes = np.zeros(len(nodes), dtype=bool)
    fit_nodes[sample_node[torch.tensor(train_mask)].numpy()] = True
    node_excluded = {"graph_snapshot_id", "node_id", "node_type"}
    node_definitions = []
    for column in nodes.columns:
        if column in node_excluded:
            continue
        numeric = pd.to_numeric(nodes[column], errors="coerce")
        kind = "numeric" if numeric.notna().mean() >= 0.9 else "categorical"
        node_definitions.append((str(column), kind))
    node_numeric, node_categorical, node_columns, node_category_sizes = _fit_columns(
        nodes, fit_nodes, node_definitions
    )
    node_type_vocabulary = _vocabulary(nodes["node_type"], fit_nodes)
    node_type = _encode(nodes["node_type"], node_type_vocabulary)

    relations = data.relations.copy()
    relation_values = pd.concat(
        [
            relations["relation_type"].astype(str),
            "reverse:" + relations["relation_type"].astype(str),
        ],
        ignore_index=True,
    )
    relation_vocabulary = {
        value: index for index, value in enumerate(sorted(set(relation_values)))
    }
    source = []
    target = []
    relation_type = []
    weights = []
    for row in relations.itertuples(index=False):
        snapshot = str(row.graph_snapshot_id)
        source_index = node_index[(snapshot, str(row.source_id))]
        target_index = node_index[(snapshot, str(row.target_id))]
        source.extend([source_index, target_index])
        target.extend([target_index, source_index])
        relation_type.extend(
            [
                relation_vocabulary[str(row.relation_type)],
                relation_vocabulary[f"reverse:{row.relation_type}"],
            ]
        )
        weights.extend([float(row.weight), float(row.weight)])

    event_node: list[int] = []
    event_type = torch.zeros(0, dtype=torch.long)
    event_amount = torch.zeros((0, 1), dtype=torch.float32)
    event_decay = torch.zeros((0, 1), dtype=torch.float32)
    event_vocabulary: dict[str, int] = {}
    if use_events and data.events is not None and len(data.events):
        events = data.events.copy()
        event_node = [
            node_index[(str(snapshot), str(node))]
            for snapshot, node in events[["graph_snapshot_id", "node_id"]].itertuples(
                index=False, name=None
            )
        ]
        event_fit = fit_nodes[np.asarray(event_node)]
        event_vocabulary = _vocabulary(events["event_type"], event_fit)
        event_type = _encode(events["event_type"], event_vocabulary)
        amount = (
            pd.to_numeric(events.get("amount", pd.Series(0, index=events.index)), errors="coerce")
            .fillna(0)
            .clip(lower=0)
        )
        fit_amount = np.log1p(amount[event_fit])
        mean = float(fit_amount.mean()) if len(fit_amount) else 0.0
        std = float(fit_amount.std(ddof=0)) if len(fit_amount) else 1.0
        std = std or 1.0
        event_amount = torch.tensor(
            ((np.log1p(amount) - mean) / std).to_numpy(dtype=np.float32).reshape(-1, 1)
        )
        cutoff = samples.groupby("graph_snapshot_id")["observation_time"].min()
        cutoffs = events["graph_snapshot_id"].map(cutoff)
        age_days = (cutoffs - events["event_time"]).dt.total_seconds() / 86400
        event_decay = torch.tensor(
            np.exp(-math.log(2) * age_days.to_numpy(dtype=np.float32) / 365).reshape(-1, 1)
        )

    hyper_nodes: list[int] = []
    hyperedge_ids: list[int] = []
    hyper_types: list[int] = []
    hyper_vocabulary: dict[str, int] = {}
    if data.hyperedges is not None and len(data.hyperedges):
        memberships = data.hyperedges.copy()
        hyper_keys = sorted(
            set(
                memberships[["graph_snapshot_id", "hyperedge_id"]]
                .astype(str)
                .itertuples(index=False, name=None)
            )
        )
        hyper_index = {key: index for index, key in enumerate(hyper_keys)}
        hyper_vocabulary = {
            value: index
            for index, value in enumerate(sorted(set(memberships["hyperedge_type"].astype(str))))
        }
        for row in memberships.itertuples(index=False):
            snapshot = str(row.graph_snapshot_id)
            hyper_nodes.append(node_index[(snapshot, str(row.node_id))])
            hyperedge_ids.append(hyper_index[(snapshot, str(row.hyperedge_id))])
            hyper_types.append(hyper_vocabulary[str(row.hyperedge_type)])

    target_values = (
        samples["target"].astype(str) == str(data.metadata.target.positive_value)
    ).astype(np.float32)
    vocabularies = {
        "nodeType": node_type_vocabulary,
        "relationType": relation_vocabulary,
        "eventType": event_vocabulary,
        "hyperedgeType": hyper_vocabulary,
    }
    batch = GraphBatch(
        sample_numeric=sample_numeric,
        sample_categorical=sample_categorical,
        node_numeric=node_numeric,
        node_categorical=node_categorical,
        node_type=node_type,
        sample_node=sample_node,
        edge_source=torch.tensor(source, dtype=torch.long),
        edge_target=torch.tensor(target, dtype=torch.long),
        edge_type=torch.tensor(relation_type, dtype=torch.long),
        edge_weight=torch.tensor(weights, dtype=torch.float32),
        event_node=torch.tensor(event_node, dtype=torch.long),
        event_type=event_type,
        event_amount=event_amount,
        event_decay=event_decay,
        hyper_node=torch.tensor(hyper_nodes, dtype=torch.long),
        hyperedge=torch.tensor(hyperedge_ids, dtype=torch.long),
        hyper_type=torch.tensor(hyper_types, dtype=torch.long),
        split=samples["split"].to_numpy(),
        target=torch.tensor(target_values.to_numpy()),
        sample_columns=sample_columns,
        node_columns=node_columns,
        vocabularies=vocabularies,
    )
    return batch, sample_category_sizes, node_category_sizes


class MixedEncoder(nn.Module):
    def __init__(self, numeric_width: int, category_sizes: list[int], hidden: int):
        super().__init__()
        self.embeddings = nn.ModuleList([nn.Embedding(size, 8) for size in category_sizes])
        width = numeric_width + len(category_sizes) * 8
        self.network = nn.Sequential(
            nn.Linear(max(width, 1), hidden), nn.ReLU(), nn.LayerNorm(hidden)
        )

    def forward(self, numeric: torch.Tensor, categorical: torch.Tensor) -> torch.Tensor:
        parts = [numeric]
        parts.extend(
            embedding(categorical[:, index])
            for index, embedding in enumerate(self.embeddings)
        )
        values = torch.cat(parts, dim=1) if parts else numeric
        if values.shape[1] == 0:
            values = torch.zeros((len(numeric), 1), device=numeric.device)
        return self.network(values)


class WorkbenchGNN(nn.Module):
    def __init__(
        self,
        sample_numeric_width: int,
        sample_categories: list[int],
        node_numeric_width: int,
        node_categories: list[int],
        node_type_count: int,
        relation_type_count: int,
        event_type_count: int,
        hyper_type_count: int,
        hidden: int = 32,
    ):
        super().__init__()
        self.hidden = hidden
        self.sample_encoder = MixedEncoder(sample_numeric_width, sample_categories, hidden)
        self.node_encoder = MixedEncoder(node_numeric_width, node_categories, hidden)
        self.node_type = nn.Embedding(max(node_type_count, 1), 8)
        self.node_fusion = nn.Linear(hidden + 8 + hidden, hidden)
        self.event_type = nn.Embedding(max(event_type_count, 1), 8)
        self.event_project = nn.Linear(9, hidden)
        self.relation_type = nn.Embedding(max(relation_type_count, 1), hidden)
        self.message = nn.Linear(hidden, hidden)
        self.relation_gate = nn.Linear(hidden * 2, 1)
        self.relation_norm = nn.LayerNorm(hidden)
        self.hyper_type_weight = nn.Parameter(torch.zeros(max(hyper_type_count, 1)))
        self.hyper_gate = nn.Linear(hidden * 2, 1)
        self.hyper_norm = nn.LayerNorm(hidden)
        self.classifier = nn.Sequential(
            nn.Linear(hidden * 2, hidden), nn.ReLU(), nn.Dropout(0.1), nn.Linear(hidden, 1)
        )

    def forward(self, batch: GraphBatch, mode: str) -> tuple[torch.Tensor, dict[str, Any]]:
        sample = self.sample_encoder(batch.sample_numeric, batch.sample_categorical)
        node_base = self.node_encoder(batch.node_numeric, batch.node_categorical)
        event = torch.zeros((len(node_base), self.hidden), dtype=node_base.dtype)
        if len(batch.event_node):
            encoded_event = self.event_project(
                torch.cat([self.event_type(batch.event_type), batch.event_amount], dim=1)
            ) * batch.event_decay
            event.index_add_(0, batch.event_node, encoded_event)
        node = torch.relu(
            self.node_fusion(torch.cat([node_base, self.node_type(batch.node_type), event], dim=1))
        )
        relation_gate_mean = 1.0
        if mode != "gnn_self_only":
            messages = self.message(node[batch.edge_source]) + self.relation_type(batch.edge_type)
            messages = messages * torch.log1p(batch.edge_weight).unsqueeze(1)
            aggregated = torch.zeros_like(node)
            aggregated.index_add_(0, batch.edge_target, messages)
            counts = torch.zeros((len(node), 1), dtype=node.dtype)
            counts.index_add_(0, batch.edge_target, torch.ones((len(messages), 1)))
            aggregated = aggregated / counts.clamp_min(1)
            gate = torch.sigmoid(self.relation_gate(torch.cat([node, aggregated], dim=1)))
            node = self.relation_norm(gate * node + (1 - gate) * aggregated)
            relation_gate_mean = float(gate.detach().mean())
        hyper_weights: list[float] = []
        if mode == "gnn_full" and len(batch.hyper_node):
            hyper_count = int(batch.hyperedge.max()) + 1
            hyper = torch.zeros((hyper_count, self.hidden), dtype=node.dtype)
            hyper.index_add_(0, batch.hyperedge, node[batch.hyper_node])
            counts = torch.zeros((hyper_count, 1), dtype=node.dtype)
            counts.index_add_(0, batch.hyperedge, torch.ones((len(batch.hyperedge), 1)))
            hyper = hyper / counts.clamp_min(1)
            incidence_weight = torch.sigmoid(self.hyper_type_weight[batch.hyper_type]).unsqueeze(1)
            propagated = torch.zeros_like(node)
            propagated.index_add_(0, batch.hyper_node, hyper[batch.hyperedge] * incidence_weight)
            node_counts = torch.zeros((len(node), 1), dtype=node.dtype)
            node_counts.index_add_(0, batch.hyper_node, torch.ones((len(batch.hyper_node), 1)))
            propagated = propagated / node_counts.clamp_min(1)
            gate = torch.sigmoid(self.hyper_gate(torch.cat([node, propagated], dim=1)))
            node = self.hyper_norm(gate * node + (1 - gate) * propagated)
            hyper_weights = torch.sigmoid(self.hyper_type_weight).detach().tolist()
        logits = self.classifier(torch.cat([sample, node[batch.sample_node]], dim=1)).squeeze(1)
        return logits, {
            "relationSelfGateMean": relation_gate_mean,
            "hyperedgeTypeWeights": hyper_weights,
        }


def _save_artifact(
    model: WorkbenchGNN, batch: GraphBatch, mode: str, selected: list[str]
) -> bytes:
    stream = io.BytesIO()
    torch.save(
        {
            "format": "workbench-gnn-v1",
            "variant": mode,
            "selected_features": selected,
            "sample_columns": [column.__dict__ for column in batch.sample_columns],
            "node_columns": [column.__dict__ for column in batch.node_columns],
            "vocabularies": batch.vocabularies,
            "state_dict": model.state_dict(),
        },
        stream,
    )
    return stream.getvalue()


def train_gnn_variants(
    data: BundleData,
    selected_features: list[str],
    requested_models: list[str],
    *,
    use_events: bool,
    seed: int,
    max_epochs: int = 80,
    patience: int = 12,
) -> list[FittedVariant]:
    modes = [name for name in requested_models if name.startswith("gnn_")]
    if not modes:
        return []
    batch, sample_categories, node_categories = prepare_graph_batch(
        data, selected_features, use_events=use_events
    )
    masks = {split: torch.tensor(batch.split == split) for split in ("train", "validation", "test")}
    train_target = batch.target[masks["train"]]
    positive = float(train_target.sum())
    negative = float(len(train_target) - positive)
    loss_function = nn.BCEWithLogitsLoss(
        pos_weight=torch.tensor(negative / max(positive, 1.0))
    )
    variants = []
    for mode in modes:
        if mode == "gnn_full" and not len(batch.hyper_node):
            raise ValueError("gnn_full requires hyperedges")
        started = time.monotonic()
        variant_seed = seed
        random.seed(variant_seed)
        np.random.seed(variant_seed)
        torch.manual_seed(variant_seed)
        torch.set_num_threads(1)
        model = WorkbenchGNN(
            batch.sample_numeric.shape[1],
            sample_categories,
            batch.node_numeric.shape[1],
            node_categories,
            int(batch.node_type.max()) + 1 if len(batch.node_type) else 1,
            int(batch.edge_type.max()) + 1 if len(batch.edge_type) else 1,
            int(batch.event_type.max()) + 1 if len(batch.event_type) else 1,
            int(batch.hyper_type.max()) + 1 if len(batch.hyper_type) else 1,
        )
        optimizer = torch.optim.AdamW(model.parameters(), lr=0.01, weight_decay=1e-4)
        best_loss = math.inf
        best_state: dict[str, torch.Tensor] | None = None
        remaining_patience = patience
        epochs = 0
        for epoch in range(max_epochs):
            model.train()
            optimizer.zero_grad()
            logits, _ = model(batch, mode)
            loss = loss_function(logits[masks["train"]], batch.target[masks["train"]])
            loss.backward()
            optimizer.step()
            model.eval()
            with torch.no_grad():
                validation_logits, _ = model(batch, mode)
                validation_loss = nn.functional.binary_cross_entropy_with_logits(
                    validation_logits[masks["validation"]], batch.target[masks["validation"]]
                ).item()
            epochs = epoch + 1
            if validation_loss < best_loss - 1e-5:
                best_loss = validation_loss
                best_state = {
                    name: value.detach().clone()
                    for name, value in model.state_dict().items()
                }
                remaining_patience = patience
            else:
                remaining_patience -= 1
                if remaining_patience == 0:
                    break
        if best_state is None:
            raise RuntimeError("GNN training did not produce a checkpoint")
        model.load_state_dict(best_state)
        model.eval()
        with torch.no_grad():
            logits, explainability = model(batch, mode)
            probability = torch.sigmoid(logits).numpy()
        validation_target = batch.target[masks["validation"]].numpy().astype(int)
        validation_probability = probability[masks["validation"].numpy()]
        threshold = select_threshold(validation_target, validation_probability)
        test_target = batch.target[masks["test"]].numpy().astype(int)
        result = {
            "name": mode,
            "status": "completed",
            "metrics": {
                "validation": evaluate(validation_target, validation_probability, threshold),
                "test": evaluate(
                    test_target, probability[masks["test"].numpy()], threshold
                ),
            },
            "explainability": {"type": "learned_gates", **explainability},
            "configuration": {
                "fitSplit": "train",
                "earlyStoppingSplit": "validation",
                "epochs": epochs,
                "seed": variant_seed,
                "eventEncoder": use_events and len(batch.event_node) > 0,
                "relationPropagation": mode != "gnn_self_only",
                "hypergraphPropagation": mode == "gnn_full",
            },
            "durationSeconds": time.monotonic() - started,
        }
        variants.append(
            FittedVariant(mode, result, _save_artifact(model, batch, mode, selected_features))
        )
    return variants
