"""Persist numerical buffers that PEFT adapters and base state_dicts do not retain."""

import json
from pathlib import Path

import torch

RUNTIME_FILE = "decision_runtime.json"


def restore_buffers(model, buffers):
    current = dict(model.named_buffers())
    for name, value in buffers.items():
        if name not in current or value.shape != current[name].shape:
            raise ValueError("Runtime buffer does not match model: " + name)
        parent, _, key = name.rpartition(".")
        module = model.get_submodule(parent) if parent else model
        setattr(module, key, value.to(device=current[name].device))


def save_runtime_buffers(model, adapter):
    buffers = {}
    for name, value in model.named_buffers():
        if value.is_complex() or not torch.isfinite(value).all():
            raise ValueError("Unsupported runtime buffer: " + name)
        buffers[name] = {
            "dtype": str(value.dtype).removeprefix("torch."),
            "shape": list(value.shape), "values": value.detach().cpu().tolist(),
        }
    path = Path(adapter) / RUNTIME_FILE
    path.write_text(json.dumps({"version": 1, "buffers": buffers}, indent=2, allow_nan=False))


def restore_runtime_buffers(model, adapter):
    data = json.loads((Path(adapter) / RUNTIME_FILE).read_text())
    if data["version"] != 1:
        raise ValueError("Unsupported decision runtime version")
    if set(data["buffers"]) != set(dict(model.named_buffers())):
        raise ValueError("Decision runtime must include every model buffer")
    buffers = {}
    for name, record in data["buffers"].items():
        dtype = getattr(torch, record["dtype"])
        value = torch.tensor(record["values"], dtype=dtype)
        if list(value.shape) != record["shape"] or not torch.isfinite(value).all():
            raise ValueError("Invalid runtime buffer: " + name)
        buffers[name] = value
    restore_buffers(model, buffers)


def load_decision_model(model_id, adapter, device="cuda", dtype="bfloat16"):
    from jevforge.jev import load_model_and_tokenizer

    model, tokenizer = load_model_and_tokenizer(
        model_id, adapter=str(adapter), device=device, dtype=dtype,
    )
    restore_runtime_buffers(model, adapter)
    return model, tokenizer
