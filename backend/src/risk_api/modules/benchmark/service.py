"""Read-only SMEsD test snapshot and its selected model; never joins demo companies."""

import asyncio
import hashlib
import json
import logging
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import torch
from com_risk_runtime.explain import explain
from com_risk_runtime.predictor import Predictor
from com_risk_runtime.schema import Dataset, Node

from risk_api.modules.benchmark.errors import BenchmarkNotFound, BenchmarkUnavailable
from risk_api.shared.config import settings

logger = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[4]


class BenchmarkService:
    def __init__(
        self,
        model_dir: Path | None = None,
        data_path: Path | None = None,
        manifest_path: Path | None = None,
        root: Path | None = None,
    ) -> None:
        self.root = root or ROOT
        self.model_dir = model_dir or Path(settings.benchmark_model_dir)
        self.data_path = data_path or Path(settings.benchmark_data_path)
        self.manifest_path = manifest_path or self.root / "docs/demo-bundle-manifest.json"
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="benchmark")
        self._slots = asyncio.Semaphore(2)
        self._available = False
        self._dataset: Dataset | None = None
        self._predictor: Predictor | None = None
        self._predictions: dict[str, dict[str, Any]] = {}
        self._nodes: dict[str, Node] = {}
        self._companies: list[Node] = []
        self._event_counts: Counter[str] = Counter()
        self._metrics: dict[str, Any] = {}

    async def _run(self, function: Any, *args: Any) -> Any:
        async with self._slots:
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(self._executor, lambda: function(*args))

    def _verify_bundle(self) -> None:
        manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        for item in manifest["files"]:
            relative = Path(item["path"])
            if relative.parts[0] != "backend" or ".." in relative.parts:
                raise ValueError("Invalid bundle manifest path")
            path = self.root.joinpath(*relative.parts[1:])
            if path.stat().st_size != item["bytes"]:
                raise ValueError(f"Bundle size mismatch: {item['path']}")
            with path.open("rb") as stream:
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
            if digest != item["sha256"]:
                raise ValueError(f"Bundle checksum mismatch: {item['path']}")

    def _load(self) -> None:
        # Bound PyTorch CPU parallelism separately from the event loop's request concurrency.
        torch.set_num_threads(1)
        self._verify_bundle()
        predictor = Predictor(self.model_dir)
        dataset = Dataset.read(self.data_path)
        result = predictor.predict(dataset)
        metrics = json.loads((self.model_dir / "metrics.json").read_text(encoding="utf-8"))
        self._predictor = predictor
        self._dataset = dataset
        self._predictions = {row["company_id"]: row for row in result["predictions"]}
        self._nodes = {node.id: node for node in dataset.nodes}
        self._companies = [node for node in dataset.nodes if node.kind == "company"]
        self._event_counts = Counter(event.company for event in dataset.events)
        self._metrics = metrics
        if len(self._companies) != 474:
            raise ValueError("Unexpected SMEsD test company count")

    async def start(self) -> None:
        try:
            await self._run(self._load)
        except Exception:
            self._available = False
            logger.exception("benchmark.model_unavailable")
        else:
            self._available = True
            logger.info("benchmark.model_ready", extra={"company_count": len(self._companies)})

    def close(self) -> None:
        self._executor.shutdown(wait=True, cancel_futures=True)

    def _ready(self) -> tuple[Dataset, Predictor]:
        if not self._available or self._dataset is None or self._predictor is None:
            raise BenchmarkUnavailable()
        return self._dataset, self._predictor

    def _node(self, company_id: str) -> Node:
        self._ready()
        node = self._nodes.get(company_id)
        if node is None or node.kind != "company":
            raise BenchmarkNotFound()
        return node

    def summary(self, node: Node) -> dict[str, Any]:
        return {
            "id": node.id,
            "community": node.community,
            "eventCount": self._event_counts[node.id],
            "riskProbability": self._predictions[node.id]["risk_probability"],
            "creditScore": self._predictions[node.id]["credit_score"],
            "predictedLabel": self._predictions[node.id]["predicted_label"],
        }

    def search(self, keyword: str, page: int, page_size: int) -> tuple[list[dict[str, Any]], int]:
        self._ready()
        query = keyword.strip().casefold()
        matched = [
            node
            for node in self._companies
            if not query or query in node.id.casefold() or query in node.community.casefold()
        ]
        offset = (page - 1) * page_size
        return [self.summary(node) for node in matched[offset : offset + page_size]], len(matched)

    def get(self, company_id: str) -> dict[str, Any]:
        data, _ = self._ready()
        node = self._node(company_id)
        return {
            **self.summary(node),
            "dataset": data.name,
            "features": dict(zip(data.feature_names, node.features, strict=True)),
            "observedLabel": node.label,
            "events": [event.model_dump() for event in data.events if event.company == company_id][
                :20
            ],
        }

    def predict(self, ids: list[str]) -> list[dict[str, Any]]:
        self._ready()
        for company_id in ids:
            self._node(company_id)
        return [self.summary(self._nodes[company_id]) for company_id in ids]

    async def explain(self, company_id: str) -> dict[str, Any]:
        data, predictor = self._ready()
        self._node(company_id)
        return await self._run(explain, predictor, data, company_id)

    def graph(self, company_id: str, limit: int) -> dict[str, Any]:
        data, _ = self._ready()
        self._node(company_id)
        edges = [edge for edge in data.edges if company_id in (edge.source, edge.target)]
        shown = edges[:limit]
        ids = {company_id} | {edge.source for edge in shown} | {edge.target for edge in shown}
        return {
            "center": company_id,
            "totalEdges": len(edges),
            "truncated": len(edges) > limit,
            "edges": [edge.model_dump() for edge in shown],
            "nodes": [
                {
                    "id": node_id,
                    "kind": self._nodes[node_id].kind,
                    "community": self._nodes[node_id].community,
                }
                for node_id in sorted(ids)
            ],
        }

    def evaluation(self) -> dict[str, Any]:
        data, predictor = self._ready()
        return {
            "model": predictor.meta["model"],
            "mode": predictor.meta["mode"],
            "dataset": data.name,
            "threshold": predictor.meta["threshold"],
            "metrics": self._metrics["model"],
            "notes": self._metrics["notes"],
            "companyCount": len(self._companies),
            "relationCount": len(data.edges),
        }

    def model_card(self) -> dict[str, Any]:
        data, predictor = self._ready()
        meta = predictor.meta
        return {
            "model": meta["model"],
            "dataset": data.name,
            "targetDescription": meta["target_description"],
            "featureNames": data.feature_names,
            "relationNames": data.relation_names,
            "hyperedgeTypes": data.hyperedge_types,
            "mode": meta["mode"],
            "threshold": meta["threshold"],
            "calibrated": meta["calibrated"],
            "bestEpoch": meta["best_epoch"],
            "syntheticTraining": meta["synthetic"],
            "companyCount": len(self._companies),
        }
