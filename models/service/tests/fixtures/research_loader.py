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
        labels = pd.read_parquet(self.path / "label.parquet").set_index("company_id")
        self.y = labels.loc[self.ca.company_id, "label"].to_numpy()

    def build_features(self, mode):
        return (
            self.ca[
                [
                    "officers",
                    "name_change_count",
                    "has_unit",
                    "related_company_count",
                    "related_company_weighted",
                    "address_trust",
                ]
            ]
            .fillna(0)
            .to_numpy(dtype=np.float32)
        )

    def load_frozen_splits(self, seed):
        s = pd.read_parquet(self.path / "splits_5seed.parquet")
        s = s[s.seed == seed]
        return {name: s[s.split == name].node_idx.to_numpy() for name in ["train", "val", "test"]}

    def build_id_map(self):
        self.id2idx = {x: i for i, x in enumerate(self.ca.company_id)}
