"""Full UK financial LoRA training with audited batched JevForge computation."""

import argparse
import gc
import hashlib
import json
import math
import os
import random
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from run_uk_jevforge import (
    DEFAULT_MODEL,
    QUESTION,
    REVISION,
    calibrated,
    calibration_lines,
    metrics,
    read,
    temperature_fit,
    write,
)


def file_hash(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def log(message):
    print(message, flush=True)


def load_data(root):
    from jevforge.data.schema import Example

    manifest = json.loads((root / "full/manifest.json").read_text())
    for name, info in manifest["files"].items():
        path = root / "full" / name
        if path.exists() and file_hash(path) != info["sha256"]:
            raise ValueError("Full dataset digest mismatch: " + name)
    index = read(root / "full/sample-index.jsonl")
    calib = calibration_lines([r for r in index if r["split"] == "train"])
    groups, ids = {}, {}
    for split in ("train", "valid", "test"):
        items = []
        for row in read(root / f"full/{split}.financial.jsonl"):
            q = row["questions"][QUESTION]
            items.append(Example(
                json.dumps(row["state"], separators=(",", ":"), allow_nan=False),
                list(q["criteria"].values()), list(q["criteria"]).index(row["expected"][QUESTION]),
                q["instructions"], "uk-research-full-financial",
            ))
        split_index = [r for r in index if r["split"] == split]
        if len(items) != len(split_index):
            raise ValueError("Sample index and input rows differ")
        groups[split], ids[split] = items, [r["sample_id"] for r in split_index]
    groups["calibration"] = [e for i, e in enumerate(groups["train"], 1) if i in calib]
    ids["calibration"] = [e for i, e in enumerate(ids["train"], 1) if i in calib]
    groups["train"] = [e for i, e in enumerate(groups["train"], 1) if i not in calib]
    ids["train"] = [e for i, e in enumerate(ids["train"], 1) if i not in calib]
    if not groups["train"] or not groups["calibration"]:
        raise ValueError("Empty training or calibration partition")
    return groups, ids


def encode_items(tok, items, workers, max_len, reverse=False):
    from jevforge.prompt import render
    from jevforge.trie import encode

    def prepare(e):
        options = list(reversed(e.options)) if reverse else e.options
        result = encode(tok, render(tok, e.state, options, e.instruction), len(options))
        if len(result.prompt_ids) + len(result.trie.nodes) > max_len:
            raise ValueError("Full dataset has an over-budget input; refusing silent truncation")
        return result

    with ThreadPoolExecutor(max_workers=workers) as executor:
        return list(executor.map(prepare, items))


def equivalence_check(model, tok, encodings):
    import torch
    from jevforge.losses import jev_loss
    from jevforge.scorer import NodeLogProbs, candidate_scores, tree_forward
    from jevforge_batch import (
        BatchLogProbs,
        candidate_scores_batch,
        jev_loss_batch,
        tree_batch_forward,
    )

    probes = [min(encodings, key=lambda e: len(e.prompt_ids)),
              max(encodings, key=lambda e: len(e.prompt_ids))] + encodings[:2]
    original_dtype = next(model.parameters()).dtype
    errors = {}
    for dtype in (original_dtype, torch.float32):
        model.to(dtype=dtype)
        with torch.no_grad():
            packed = tree_batch_forward(model, probes, tok.pad_token_id)
            scores = candidate_scores_batch(packed, probes[0])
            reference = torch.stack([
                candidate_scores(tree_forward(model, e), e) for e in probes
            ])
            errors[str(dtype)] = {
                "probability": float((scores.softmax(-1) - reference.softmax(-1)).abs().max()),
                "score": float((scores - reference).abs().max()),
            }
    model.to(dtype=original_dtype)
    del packed, scores, reference
    torch.cuda.empty_cache()
    # FP32 checks the mathematical batching contract; BF16 uses the native scorer's tolerance.
    if errors["torch.float32"]["probability"] > 1e-4:
        raise ValueError(f"Batched/native FP32 disagreement: {errors}")
    if errors[str(original_dtype)]["score"] > 0.25:
        raise ValueError(f"Batched/native low-precision disagreement: {errors}")
    # Compare both objective values and derivatives against the original scalar implementation.
    vocab = max(128, max(n.token for n in probes[0].trie.nodes) + 1)
    shape = (len(probes), len(probes[0].trie.nodes), vocab)
    generator = torch.Generator().manual_seed(7)
    original_logits = torch.randn(shape, generator=generator, dtype=torch.float64)
    original_reply = torch.randn(len(probes), vocab, generator=generator, dtype=torch.float64)
    ref_node = torch.randn(shape, generator=generator, dtype=torch.float64).log_softmax(-1)
    ref_reply = torch.randn(len(probes), vocab, generator=generator,
                            dtype=torch.float64).log_softmax(-1)
    gold = [0, 1, 0, 1]
    logits_a = original_logits.clone().requires_grad_()
    reply_a = original_reply.clone().requires_grad_()
    logits_b = original_logits.clone().requires_grad_()
    reply_b = original_reply.clone().requires_grad_()
    packed_loss = jev_loss_batch(
        BatchLogProbs(logits_a.log_softmax(-1), reply_a.log_softmax(-1)),
        BatchLogProbs(ref_node, ref_reply), probes, gold, random.Random(42),
    )["loss"].mean()
    rng = random.Random(42)
    native_loss = torch.stack([
        jev_loss(
            NodeLogProbs(logits_b[i].log_softmax(-1), reply_b[i].log_softmax(-1)),
            NodeLogProbs(ref_node[i], ref_reply[i]), probes[i], gold[i], rng=rng,
        ).total for i in range(len(probes))
    ]).mean()
    packed_loss.backward()
    native_loss.backward()
    loss_error = abs(float(packed_loss.detach() - native_loss.detach()))
    gradient_error = max(float((logits_a.grad - logits_b.grad).abs().max()),
                         float((reply_a.grad - reply_b.grad).abs().max()))
    if loss_error > 1e-8 or gradient_error > 1e-8:
        raise ValueError("Batched objective or gradient differs from native JevForge")
    return {"forward_errors": errors, "loss_error": loss_error,
            "max_gradient_error": gradient_error}


def score(model, tok, encodings, gold, batch_size):
    import torch
    from jevforge_batch import candidate_scores_batch, tree_batch_forward

    model.eval()
    order = sorted(range(len(encodings)), key=lambda i: len(encodings[i].prompt_ids))
    probabilities = [None] * len(order)
    started = time.perf_counter()
    with torch.inference_mode():
        for start in range(0, len(order), batch_size):
            rows = order[start:start + batch_size]
            encoded = [encodings[i] for i in rows]
            packed = tree_batch_forward(model, encoded, tok.pad_token_id)
            values = candidate_scores_batch(packed, encoded[0]).softmax(-1)[:, 1].tolist()
            for i, value in zip(rows, values, strict=True):
                probabilities[i] = value
            if start // batch_size % 100 == 0:
                log(f"[score] {min(start + len(rows), len(order))}/{len(order)}")
    return probabilities, {
        "metrics": metrics(gold, probabilities),
        "elapsed_s": time.perf_counter() - started,
    }


def train(model, tok, groups, encoded, reverse, args):
    import torch
    from jevforge.train import lr_factor
    from jevforge_batch import jev_loss_batch, tree_batch_forward

    output = args.workspace / "results"
    rng = random.Random(42)
    order = list(range(len(groups["train"])))
    rng.shuffle(order)
    windows = []
    for start in range(0, len(order), args.batch_size * 32):
        bucket = sorted(order[start:start + args.batch_size * 32],
                        key=lambda i: len(encoded["train"][i].prompt_ids))
        windows.extend(
            bucket[i:i + args.batch_size] for i in range(0, len(bucket), args.batch_size)
        )
    rng.shuffle(windows)
    params = [p for p in model.parameters() if p.requires_grad]
    optimizer = torch.optim.AdamW(params, lr=1e-4, weight_decay=0.01)
    total = math.ceil(len(order) / args.batch_size)
    if len(windows) != total or sum(map(len, windows)) != len(order):
        raise ValueError("Length bucketing changed the training population")
    warmup = max(1, int(total * 0.1))
    started = time.perf_counter()
    model.train()
    processed = 0
    log_file = (output / "train_log.jsonl").open("w")
    for step, window in enumerate(windows, 1):
        for group in optimizer.param_groups:
            group["lr"] = 1e-4 * lr_factor(step - 1, total, warmup, 0.1)
        optimizer.zero_grad(set_to_none=True)
        agg = {}
        for offset in range(0, len(window), args.micro_batch):
            indices = window[offset:offset + args.micro_batch]
            encs, gold = [], []
            for i in indices:
                flipped = rng.random() < 0.5
                encs.append(reverse[i] if flipped else encoded["train"][i])
                gold.append(1 - groups["train"][i].gold if flipped else groups["train"][i].gold)
            with torch.no_grad(), model.disable_adapter():
                reference = tree_batch_forward(model, encs, tok.pad_token_id)
            current = tree_batch_forward(model, encs, tok.pad_token_id)
            parts = jev_loss_batch(current, reference, encs, gold, rng)
            if not torch.isfinite(parts["loss"]).all():
                raise ValueError("Non-finite training loss")
            (parts["loss"].sum() / len(window)).backward()
            for name, values in parts.items():
                agg[name] = agg.get(name, 0.0) + float(values.detach().sum())
            del reference, current, parts
        torch.nn.utils.clip_grad_norm_(params, 1.0)
        optimizer.step()
        processed += len(window)
        record = {name: value / len(window) for name, value in agg.items()}
        record.update(step=step, total=total, n=len(window), processed=processed,
                      elapsed_s=time.perf_counter() - started, lr=optimizer.param_groups[0]["lr"])
        log_file.write(json.dumps(record) + "\n")
        log_file.flush()
        if step == 1 or step % 10 == 0 or step == total:
            log(f"[train] {step}/{total} samples={processed}/{len(order)} "
                f"loss={record['loss']:.4f} elapsed={record['elapsed_s']:.1f}s")
            write(output / "status.json", {"stage": "train", **record})
        if record["root_delta"] < -0.5:
            raise ValueError("Native root legal-mass health check failed")
    log_file.close()
    model.save_pretrained(output / "adapter")
    tok.save_pretrained(output / "adapter")
    result = {"steps": total, "examples": processed, "elapsed_s": time.perf_counter() - started,
              "peak_allocated_gib": torch.cuda.max_memory_allocated() / 2**30,
              "peak_reserved_gib": torch.cuda.max_memory_reserved() / 2**30}
    write(output / "training.json", result)
    del optimizer
    gc.collect()
    torch.cuda.empty_cache()
    return result


def run(args):
    import torch
    from jevforge.jev import load_model_and_tokenizer
    from jevforge_batch import candidate_scores_batch, tree_batch_forward
    from peft import LoraConfig, PeftModel, get_peft_model

    root = args.workspace
    output = root / "results"
    output.mkdir(exist_ok=False)
    torch.set_num_threads(4)
    torch.manual_seed(42)
    torch.cuda.set_per_process_memory_fraction(
        args.gpu_gib * 2**30 / torch.cuda.get_device_properties(0).total_memory
    )
    groups, ids = load_data(root)
    write(output / "status.json", {"stage": "encoding"})
    model, tok = load_model_and_tokenizer(args.model, device="cuda", dtype="bfloat16")
    encoded = {}
    for split, items in groups.items():
        log(f"[encode] {split}: {len(items)}")
        encoded[split] = encode_items(tok, items, args.workers, args.max_len)
    reverse = encode_items(tok, groups["train"], args.workers, args.max_len, reverse=True)
    check = equivalence_check(model, tok, encoded["train"][:100])
    write(output / "equivalence.json", check)
    log(f"[equivalence] {check}")
    config = {
        "model": "Qwen/Qwen3-0.6B", "revision": REVISION, "seed": 42,
        "epochs": 1, "global_batch": args.batch_size, "micro_batch": args.micro_batch,
        "eval_batch": args.eval_batch, "gpu_limit_gib": args.gpu_gib,
        "baseline_evaluated": args.baseline,
        "lr": 1e-4, "weight_decay": 0.01, "lora_r": 16, "lora_alpha": 32,
        "lora_targets": "all-linear", "objective": "native LLM-as-Jev, lambda=1",
        "sampling": "seeded shuffled length buckets; each training row exactly once",
        "max_len": args.max_len, "groups": {
            name: {"n": len(items), "positive": sum(e.gold for e in items),
                   "max_tokens": max(len(e.prompt_ids) + len(e.trie.nodes) for e in encoded[name])}
            for name, items in groups.items()
        },
        "source_manifest_sha256": file_hash(root / "full/manifest.json"),
        "script_sha256": file_hash(Path(__file__)),
        "batch_script_sha256": file_hash(Path(__file__).with_name("jevforge_batch.py")),
    }
    write(output / "config.json", config)
    if args.check_only:
        write(output / "status.json", {"stage": "checks_complete"})
        return
    baseline = {}
    for split in (("valid", "test") if args.baseline else ()):
        write(output / "status.json", {"stage": "baseline", "split": split})
        p, baseline[split] = score(model, tok, encoded[split], [e.gold for e in groups[split]],
                                  args.eval_batch)
        write(output / f"baseline.{split}.json", {"sample_ids": ids[split], "probabilities": p,
                                                  **baseline[split]})
    model = get_peft_model(model, LoraConfig(
        r=16, lora_alpha=32, lora_dropout=0, target_modules="all-linear", task_type="CAUSAL_LM"
    ))
    model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
    model.enable_input_require_grads()
    torch.cuda.reset_peak_memory_stats()
    training = train(model, tok, groups, encoded, reverse, args)
    model.eval()
    write(output / "status.json", {"stage": "calibration"})
    cal_y = [e.gold for e in groups["calibration"]]
    cal_p, _ = score(model, tok, encoded["calibration"], cal_y, args.eval_batch)
    temperature = temperature_fit(cal_y, cal_p)
    write(output / "calibration.json", {
        "sample_ids": ids["calibration"], "labels": cal_y,
        "probabilities": cal_p, "temperature": temperature,
    })
    result = {"baseline": baseline, "training": training, "temperature": temperature,
              "config": config, "splits": {}}
    for split in ("valid", "test"):
        write(output / "status.json", {"stage": "evaluate", "split": split})
        y = [e.gold for e in groups[split]]
        p, detail = score(model, tok, encoded[split], y, args.eval_batch)
        adjusted = calibrated(p, temperature)
        result["splits"][split] = {"raw": detail, "calibrated": metrics(y, adjusted)}
        write(output / f"finetuned.{split}.json", {
            "sample_ids": ids[split], "labels": y, "probabilities": p, "calibrated": adjusted,
        })
    probes = encoded["valid"][:5]
    with torch.no_grad():
        before = candidate_scores_batch(tree_batch_forward(model, probes, tok.pad_token_id),
                                        probes[0]).softmax(-1).cpu()
    del model
    gc.collect()
    torch.cuda.empty_cache()
    model, tok = load_model_and_tokenizer(args.model, device="cuda", dtype="bfloat16")
    model = PeftModel.from_pretrained(model, output / "adapter").eval()
    with torch.no_grad():
        after = candidate_scores_batch(tree_batch_forward(model, probes, tok.pad_token_id),
                                       probes[0]).softmax(-1).cpu()
    error = float((before - after).abs().max())
    if error > 1e-5:
        raise ValueError("Reload changed predictions")
    result["reload_max_probability_error"] = error
    write(output / "summary.json", result)
    write(output / "status.json", {"stage": "complete"})
    log(json.dumps(result))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--micro-batch", type=int, default=16)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--eval-batch", type=int, default=32)
    parser.add_argument("--max-len", type=int, default=2048)
    parser.add_argument("--gpu-gib", type=float, default=20)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--baseline", action="store_true")
    args = parser.parse_args()
    args.workspace = args.workspace.resolve()
    if min(args.micro_batch, args.batch_size, args.eval_batch, args.workers) < 1:
        raise ValueError("Batch sizes and workers must be positive")
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    sys.path.insert(0, str(args.workspace / "jevforge"))
    try:
        run(args)
    except Exception as exc:
        if (args.workspace / "results").is_dir():
            write(args.workspace / "results/failure.json", {
                "type": type(exc).__name__, "message": str(exc),
            })
        raise


if __name__ == "__main__":
    main()
