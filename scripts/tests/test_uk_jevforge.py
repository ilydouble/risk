"""Evaluation and calibration split invariants independent of model execution."""

import importlib.util
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "run_uk_jevforge", Path(__file__).parents[1] / "run_uk_jevforge.py"
)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class PilotContracts(unittest.TestCase):
    def test_perfect_and_tied_ranking(self):
        best = module.metrics([0, 1, 0, 1], [0.1, 0.9, 0.2, 0.8])
        self.assertEqual(best["roc_auc"], 1)
        self.assertEqual(best["pr_auc_average_precision"], 1)
        self.assertEqual(best["confusion_matrix"], [[2, 0], [0, 2]])
        tied = module.metrics([0, 1, 0, 1], [0.5] * 4)
        self.assertEqual(tied["roc_auc"], 0.5)
        self.assertEqual(tied["pr_auc_average_precision"], 0.5)
        self.assertEqual(tied["brier"], 0.25)

    def test_invalid_metrics_are_rejected(self):
        for p in ([0.1, float("nan")], [0.1, 1.1]):
            with self.assertRaises(ValueError):
                module.metrics([0, 1], p)
        with self.assertRaises(ValueError):
            module.metrics([0, 0], [0.1, 0.2])

    def test_temperature_preserves_ranking(self):
        labels, probs = [0, 1, 0, 1], [0.01, 0.99, 0.99, 0.01]
        temperature = module.temperature_fit(labels, probs)
        adjusted = module.calibrated(probs, temperature)
        self.assertGreater(temperature, 1)
        self.assertLess(module.metrics(labels, adjusted)["log_loss"],
                        module.metrics(labels, probs)["log_loss"])
        self.assertEqual(module.metrics(labels, adjusted)["roc_auc"],
                         module.metrics(labels, probs)["roc_auc"])

    def test_repeated_companies_and_pairs_never_cross_calibration(self):
        rows = []
        for i in range(100):
            rows.extend([
                {"line": i * 2 + 1, "company_id": f"a{i}", "pair_id": f"p{i}"},
                {"line": i * 2 + 2, "company_id": f"b{i}", "pair_id": f"p{i}"},
            ])
        rows.append({"line": 201, "company_id": "a0", "pair_id": "p1"})
        selected = module.calibration_lines(rows)
        self.assertTrue(selected)
        for field in ("company_id", "pair_id"):
            inside = {r[field] for r in rows if r["line"] in selected}
            outside = {r[field] for r in rows if r["line"] not in selected}
            self.assertFalse(inside & outside)
        self.assertEqual(selected, module.calibration_lines(list(reversed(rows))))


if __name__ == "__main__":
    unittest.main()
