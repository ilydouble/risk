"""Fetch pinned official data only, verify checksums, never execute pickle payloads."""

import hashlib
import urllib.request
from pathlib import Path

COMMIT = "a80524b3b67436cd2f74755f6ffa08a554ff2d02"
FILES = {
    "train_data.pkl": "73e69100353945bf4e2c99cb8c057093d7fc9f4640f5271dc3d68bbf327f1e5c",
    "validate_data.pkl": "b1614e44f0eb8c3133fbcdf47922ff263fd65a76289b75605ab2a3f047a1e8bb",
    "test_data.pkl": "c58a1d3af63330105c889cf03f9cdaf312592f30a66a3bb488b45eb0ef38da4d",
    "split_data_idx.pkl": "d81780ffcad976cb6977fc5bb74b7e3a6085623c982eb824383c3aaba358c035",
}


def fetch(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    for name, digest in FILES.items():
        path = root / name
        if path.exists():
            payload = path.read_bytes()
        else:
            url = f"https://raw.githubusercontent.com/shaopengw/ComRisk/{COMMIT}/data/{name}"
            with urllib.request.urlopen(url, timeout=60) as response:
                payload = response.read()
        if hashlib.sha256(payload).hexdigest() != digest:
            raise ValueError(f"Checksum mismatch: {name}")
        if not path.exists():
            path.write_bytes(payload)
        print("verified", name)
