"""Train real evidential heads and paired ComRisk controls on SMEsD."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import shutil
import subprocess
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from riskgnn_plus import EvidentialRiskLoss, RiskGNNPlus, evaluate_risk_predictions
from sklearn.metrics import roc_auc_score
from torch import nn

from smesd_uncertainty.comrisk_base.gnn import RiskGNN
from smesd_uncertainty.comrisk_base.utils import Classifier, build_incidence
from smesd_uncertainty.triage import compare_triage, write_report


def load_dataset(directory: Path, policy: str, split_seed: int) -> dict:
    ids = pd.read_pickle(directory / "split_data_idx.pkl")
    com, per = pd.read_pickle(directory / "meta_emb.pkl")
    raw = [
        pd.read_pickle(directory / f"{name}_data.pkl")
        for name in ("train", "validate", "test")
    ]
    overlap = {
        f"{a}_{b}": len(set(ids[a]) & set(ids[b])) for a, b in ((0, 1), (0, 2), (1, 2))
    }
    indices = [np.arange(len(x)) for x in ids]
    if policy == "deduplicated":
        indices[1] = np.array([i for i, x in enumerate(ids[1]) if x not in set(ids[0])])
        seen = set(ids[0]) | set(ids[1])
        indices[2] = np.array([i for i, x in enumerate(ids[2]) if x not in seen])
    rng = (
        np.random.RandomState(split_seed)
        if policy == "original"
        else np.random.default_rng(split_seed)
    )
    perm = rng.permutation(indices[1])
    half = len(perm) // 2
    selections = {
        "train": (0, indices[0]),
        "valid": (1, perm[half:]),
        "cal": (1, perm[:half]),
        "test": (2, indices[2]),
    }
    splits = {}
    for name, (source, positions) in selections.items():
        risk, attr, graph, hyper, labels = raw[source]
        splits[name] = {
            "idx": [ids[source][i] for i in positions],
            "attr": np.asarray(attr)[positions],
            "risk": risk,
            "graph": graph,
            "y": np.asarray(labels, dtype=np.int64)[positions],
            "hyper": [
                build_incidence(len(com), hyper[key])
                for key in ("industry", "area", "qualify")
            ],
        }
    return {"com": com, "per": per, "splits": splits, "original_overlap": overlap}


def seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.use_deterministic_algorithms(True)


def make_model(
    dataset: dict, evidence: bool, device: torch.device, trainable_gate: bool = True
) -> nn.Module:
    config = {
        "input_dim": 16,
        "output_dim": 12,
        "company_num": len(dataset["com"]),
        "person_num": len(dataset["per"]),
        "rel_num": 12,
        "cause_type_num": 11,
        "device": device,
        "com_initial_emb": dataset["com"],
        "person_initial_emb": dataset["per"],
        "court_type_num": 4,
        "category_num": 4,
        "time_label_num": 5,
        "use_hypergraph": True,
        "use_edgegraph": True,
        "hyper_impl": "vectorized",
        "use_community_prior": False,
    }
    if evidence:
        model = RiskGNNPlus(**config)
        model.alpha.requires_grad_(trainable_gate)
        return model.to(device)
    return nn.Sequential(RiskGNN(**config), Classifier(12, 2)).to(device)


def forward(model: nn.Module, split: dict, evidence: bool):
    if evidence:
        return model(
            split["risk"], split["attr"], split["graph"], split["hyper"], split["idx"]
        )
    emb = model[0](
        split["risk"], split["attr"], split["graph"], split["hyper"], split["idx"], None
    )
    return model[1](emb)


def fit(
    dataset: dict,
    evidence: bool,
    seed: int,
    epochs: int,
    lr: float,
    device: torch.device,
    output: Path,
    trainable_gate: bool = True,
) -> tuple[dict, dict]:
    seed_everything(seed)
    model = make_model(dataset, evidence, device, trainable_gate)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizer, T_max=epochs, eta_min=1e-5
    )
    loss_fn = EvidentialRiskLoss()
    labels = torch.as_tensor(dataset["splits"]["train"]["y"], device=device)
    best_auc, best_state, best_epoch = -1.0, None, 0
    started = time.monotonic()
    for epoch in range(1, epochs + 1):
        model.train()
        optimizer.zero_grad()
        result = forward(model, dataset["splits"]["train"], evidence)
        if evidence:
            loss = loss_fn(
                result.fused_alpha,
                result.node_alpha,
                result.graph_alpha,
                labels,
                primary_logits=result.primary_logits,
            )["loss"]
        else:
            loss = nn.functional.nll_loss(result, labels)
        if not torch.isfinite(loss):
            raise RuntimeError(f"Non-finite training loss at epoch {epoch}")
        loss.backward()
        nn.utils.clip_grad_norm_(model.parameters(), 0.25)
        optimizer.step()
        scheduler.step()
        if epoch % 5 == 0 or epoch == epochs:
            model.eval()
            with torch.no_grad():
                result = forward(model, dataset["splits"]["valid"], evidence)
                probs = result.probabilities if evidence else result.exp()
                auc = roc_auc_score(
                    dataset["splits"]["valid"]["y"], probs[:, 1].cpu().numpy()
                )
            if auc > best_auc:
                best_auc, best_epoch = float(auc), epoch
                best_state = {
                    k: v.detach().cpu().clone() for k, v in model.state_dict().items()
                }
            if epoch % 25 == 0 or epoch == epochs:
                print(
                    f"seed={seed} evidence={evidence} epoch={epoch} loss={loss.item():.4f} "
                    f"valid_auc={auc:.4f} best={best_auc:.4f}",
                    flush=True,
                )
    model.load_state_dict(best_state)
    name = "plus" if evidence else "comrisk"
    torch.save(best_state, output / f"{name}_checkpoint.pt")
    predictions, metrics = {}, {}
    model.eval()
    with torch.no_grad():
        for split_name in ("cal", "test"):
            result = forward(model, dataset["splits"][split_name], evidence)
            probs = result.probabilities if evidence else result.exp()
            predictions[f"{name}_{split_name}_p"] = probs.cpu().numpy()
            if evidence:
                predictions[f"plus_{split_name}_u"] = (
                    result.fused_uncertainty.cpu().numpy()
                )
                predictions[f"plus_{split_name}_conflict"] = (
                    result.conflict.cpu().numpy()
                )
                predictions[f"plus_{split_name}_node_alpha"] = (
                    result.node_alpha.cpu().numpy()
                )
                predictions[f"plus_{split_name}_graph_alpha"] = (
                    result.graph_alpha.cpu().numpy()
                )
            metrics[split_name] = evaluate_risk_predictions(
                probs[:, 1].cpu().numpy(), dataset["splits"][split_name]["y"]
            )
    return predictions, {
        "best_valid_auc": best_auc,
        "best_epoch": best_epoch,
        "seconds": time.monotonic() - started,
        "metrics": metrics,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("datasets/smesd"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seeds", type=int, nargs="+", default=[14, 42, 2026])
    parser.add_argument("--epochs", type=int, default=250)
    parser.add_argument("--lr", type=float, default=0.01)
    parser.add_argument("--epsilon", type=float, default=0.05)
    parser.add_argument("--beta", type=float, default=0.2)
    parser.add_argument("--split-seed", type=int, default=42)
    parser.add_argument(
        "--split-policy", choices=["original", "deduplicated"], default="original"
    )
    parser.add_argument("--threads", type=int, default=1)
    parser.add_argument(
        "--gate-policy", choices=["trainable", "fixed"], default="trainable"
    )
    parser.add_argument("--reuse-baselines", type=Path)
    args = parser.parse_args()
    if args.epochs < 1 or len(set(args.seeds)) != len(args.seeds):
        parser.error("epochs must be positive and seeds unique")
    if not 0 < args.epsilon < 1 or not np.isfinite(args.beta) or args.beta < 0:
        parser.error("Require epsilon in (0, 1) and finite beta >= 0")
    if args.output.exists():
        parser.error(
            "Output already exists; use a new directory to preserve prior experiments"
        )
    args.output.mkdir(parents=True)
    torch.set_num_threads(args.threads)
    dataset = load_dataset(args.data_dir, args.split_policy, args.split_seed)
    calibration_test_overlap = sorted(
        set(dataset["splits"]["cal"]["idx"]) & set(dataset["splits"]["test"]["idx"])
    )
    if args.split_policy == "deduplicated" and calibration_test_overlap:
        parser.error("Calibration/test IDs overlap; use the deduplicated split policy")
    if calibration_test_overlap:
        print(
            "Preserving published IDs: calibration/test overlap exists; "
            "report empirical coverage without asserting an independent-calibration guarantee.",
            flush=True,
        )
    config = {
        k: str(v.resolve()) if isinstance(v, Path) else v for k, v in vars(args).items()
    }
    config.update(
        {
            "data_sha256": {
                p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted(args.data_dir.glob("*.pkl"))
            },
            "source_sha256": {
                str(p.relative_to(Path(__file__).parents[1])): hashlib.sha256(
                    p.read_bytes()
                ).hexdigest()
                for folder in ("riskgnn_plus", "smesd_uncertainty")
                for p in sorted((Path(__file__).parents[1] / folder).rglob("*.py"))
            },
            "git_head": subprocess.check_output(
                ["git", "rev-parse", "HEAD"], text=True
            ).strip(),
            "torch": torch.__version__,
            "numpy": np.__version__,
            "device": "cpu",
            "original_overlap": dataset["original_overlap"],
            "calibration_test_overlap": len(calibration_test_overlap),
            "coverage_guarantee_assumptions_verified": False,
            "split_sizes": {name: len(s["y"]) for name, s in dataset["splits"].items()},
            "graph_protocol": "Frozen original transductive graphs and pretrained embeddings; target ID policy recorded separately",
            "community_prior": False,
            "fusion_gate_trainable": args.gate_policy == "trainable",
            "plus_architecture": "Existing RiskGNNPlus, exp(clamped logits) evidence heads",
            "evidence_loss": {"fused": 0.5, "node": 0.15, "graph": 0.15, "kl": 0.001},
        }
    )
    (args.output / "manifest.json").write_text(json.dumps(config, indent=2) + "\n")
    for relative in config["source_sha256"]:
        target = args.output / "source_snapshot" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(Path(__file__).parents[1] / relative, target)
    rows = []
    if args.reuse_baselines:
        previous = json.loads((args.reuse_baselines / "manifest.json").read_text())
        for key in (
            "data_sha256",
            "epochs",
            "lr",
            "split_seed",
            "split_policy",
            "threads",
            "torch",
            "numpy",
            "community_prior",
        ):
            if previous[key] != config[key]:
                parser.error(f"Reused baseline configuration differs: {key}")
        for relative in (
            "smesd_uncertainty/comrisk_base/gnn.py",
            "smesd_uncertainty/comrisk_base/utils.py",
        ):
            if previous["source_sha256"][relative] != config["source_sha256"][relative]:
                parser.error(f"Reused baseline source differs: {relative}")
    for seed in args.seeds:
        out = args.output / f"seed_{seed}"
        out.mkdir()
        data = {"seed": np.asarray(seed), "split_policy": np.asarray(args.split_policy)}
        for name in ("cal", "test"):
            data[f"{name}_ids"] = np.asarray(dataset["splits"][name]["idx"])
            data[f"{name}_y"] = dataset["splits"][name]["y"]
        training = {}
        for evidence in (False, True):
            if not evidence and args.reuse_baselines:
                origin = args.reuse_baselines / f"seed_{seed}"
                with np.load(origin / "predictions.npz", allow_pickle=False) as archive:
                    if int(archive["seed"]) != seed:
                        raise ValueError("Reused baseline seed differs")
                    for key in ("cal_ids", "test_ids", "cal_y", "test_y"):
                        if not np.array_equal(archive[key], data[key]):
                            raise ValueError(f"Reused baseline samples differ: {key}")
                    data.update(
                        {
                            key: archive[key]
                            for key in ("comrisk_cal_p", "comrisk_test_p")
                        }
                    )
                training["comrisk"] = json.loads(
                    (origin / "training.json").read_text()
                )["comrisk"]
                training["comrisk"]["reused_from"] = str(origin.resolve())
                training["comrisk"]["prediction_sha256"] = hashlib.sha256(
                    (origin / "predictions.npz").read_bytes()
                ).hexdigest()
                shutil.copyfile(
                    origin / "comrisk_checkpoint.pt", out / "comrisk_checkpoint.pt"
                )
                print(f"seed={seed} reused unchanged ComRisk baseline", flush=True)
                continue
            predictions, info = fit(
                dataset,
                evidence,
                seed,
                args.epochs,
                args.lr,
                torch.device("cpu"),
                out,
                trainable_gate=args.gate_policy == "trainable",
            )
            data.update(predictions)
            training["plus" if evidence else "comrisk"] = info
        np.savez_compressed(out / "predictions.npz", **data)
        (out / "training.json").write_text(json.dumps(training, indent=2) + "\n")
        seed_rows = [
            dict(row, seed=seed)
            for row in compare_triage(data, args.epsilon, args.beta)
        ]
        write_report(seed_rows, out, config)
        rows.extend(seed_rows)
        write_report(rows, args.output, config)
    (args.output / "COMPLETE").write_text("All requested seeds completed.\n")


if __name__ == "__main__":
    main()
