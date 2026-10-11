from pathlib import Path

import numpy as np
import pandas as pd


class ComRiskExport:
    def __init__(self, path, verbose=False):
        self.path = Path(path)

    def load(self):
        self.ca = pd.read_parquet(self.path / "company_attr.parquet")
        self.edges = pd.read_parquet(self.path / "edges.parquet")
        return self

    def build_labels(self):
        self.y = pd.read_parquet(self.path / "label.parquet").label.to_numpy()

    def build_features(self, mode):
        return self.ca.drop(columns="company_id").to_numpy(dtype=np.float32)

    def load_frozen_splits(self, seed):
        s = pd.read_parquet(self.path / "splits_5seed.parquet")
        s = s[s.seed == seed]
        return {name: s[s.split == name].node_idx.to_numpy() for name in ["train", "val", "test"]}

    def build_id_map(self):
        self.id2idx = {x: i for i, x in enumerate(self.ca.company_id)}
