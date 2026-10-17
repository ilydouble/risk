"""Stable isolation and target-encoding contracts for UK decision datasets."""

import importlib.util
import unittest
from copy import deepcopy
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "prepare_uk_decisions", Path(__file__).parents[1] / "prepare_uk_decisions.py"
)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def snapshot():
    return {
        "nodes": [
            {
                "id": f"s{i}", "label": i % 2,
                "properties": {
                    "pair_id": f"p{i // 2}", "company_id": f"c{i}",
                    "observation_month": "2019-01",
                },
            }
            for i in range(8)
        ],
        "hyperedges": [{"kind": "industry", "members": ["s0", "s1"]}],
        "edges": [],
    }


class DecisionContracts(unittest.TestCase):
    def test_selection_keeps_pairs_and_is_stable_under_source_reordering(self):
        source = snapshot()
        selected = module.select_pairs(source, 2, 42)
        reordered = deepcopy(source)
        reordered["nodes"].reverse()
        again = module.select_pairs(reordered, 2, 42)
        self.assertEqual({n["id"] for n in selected}, {n["id"] for n in again})
        self.assertEqual(len(selected), 4)
        self.assertEqual(sorted(n["label"] for n in selected), [0, 0, 1, 1])

    def test_incomplete_pairs_are_rejected(self):
        source = snapshot()
        source["nodes"].pop()
        with self.assertRaisesRegex(ValueError, "matched pair"):
            module.select_pairs(source, 0, 42)

    def test_features_use_allowlist_and_preserve_missing_zero_and_negative(self):
        contract = {
            "numericFeatureAllowlist": ["cash", "equity", "revenue", "cash_missing"],
            "categoricalFeatureAllowlist": ["currency"],
        }
        row = {
            "cash": "0", "equity": "-1e3", "revenue": "", "cash_missing": "False",
            "currency": "GBP", "label": "1", "role": "case", "company_name": "SECRET",
            "event_evidence_ids": "DO_NOT_ENCODE",
        }
        result = module.feature_state(row, contract)
        self.assertEqual(result, {
            "cash": 0, "equity": -1000, "currency": "GBP",
        })
        self.assertNotIn("revenue", result)
        self.assertNotIn("SECRET", module.encode(result))
        self.assertNotIn("DO_NOT_ENCODE", module.encode(result))
        row["cash"] = "NaN"
        with self.assertRaisesRegex(ValueError, "Non-finite"):
            module.feature_state(row, contract)

    def test_graph_summary_cannot_read_neighbour_labels(self):
        source = snapshot()
        before = module.relationship_summary(source)
        for node in source["nodes"]:
            node["label"] = 1 - node["label"]
            node["name"] = "Changed name"
        self.assertEqual(before, module.relationship_summary(source))
        self.assertEqual(before["s0"]["group_context"]["industry"], {
            "memberships": 1, "largest_group_peer_count": 1,
        })

    def test_graph_rejects_mixed_months_and_duplicate_members(self):
        source = snapshot()
        source["nodes"][1]["properties"]["observation_month"] = "2019-02"
        with self.assertRaisesRegex(ValueError, "crosses observation months"):
            module.relationship_summary(source)
        source = snapshot()
        source["hyperedges"][0]["members"] = ["s0", "s0"]
        with self.assertRaisesRegex(ValueError, "Invalid group"):
            module.relationship_summary(source)


if __name__ == "__main__":
    unittest.main()
