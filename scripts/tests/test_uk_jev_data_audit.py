"""Contracts for financial units, missing values and time-comparable audit calculations."""

import csv
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from zipfile import ZipFile

sys.path.insert(0, str(Path(__file__).parents[1]))
SPEC = importlib.util.spec_from_file_location(
    "uk_jev_audit",
    Path(__file__).parents[1] / "audit_uk_jev_data.py",
)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class DataAuditContracts(unittest.TestCase):
    def test_negative_label_meaning_and_multiple_positive_evidence(self):
        def csv_text(records):
            stream = io.StringIO()
            writer = csv.DictWriter(stream, fieldnames=list(records[0]))
            writer.writeheader()
            writer.writerows(records)
            return stream.getvalue()

        shared = {
            "pair_id": "p",
            "observation_month": "2019-01",
            "followup_start_month": "2019-02",
            "followup_end_month": "2020-01",
            "prediction_horizon_months": "12",
            "event_source_coverage_end": "2025-12",
        }
        labels = [
            {
                **shared,
                "sample_id": "case",
                "company_id": "00000001",
                "role": "case",
                "label": "1",
                "label_meaning": "first_observed_primary_formal_insolvency",
                "target_event_month": "2020-01",
                "event_evidence_ids": "e1;e2",
            },
            {
                **shared,
                "sample_id": "control",
                "company_id": "00000002",
                "role": "control",
                "label": "0",
                "label_meaning": "no_event_observed_in_official_source_through_horizon",
                "target_event_month": "",
                "event_evidence_ids": "",
            },
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "labels.csv").write_text(csv_text(labels))
            raw = root / "raw.zip"
            with ZipFile(raw, "w") as zipped:
                zipped.writestr(
                    "Record-level.csv",
                    csv_text(
                        [
                            {
                                "company_number": "1",
                                "month_registered": "2020-01",
                                "case_type": "In Administration",
                                "is_bulk": "",
                            }
                        ]
                    ),
                )
            events = root / "events.zip"
            with ZipFile(events, "w") as zipped:
                zipped.writestr(
                    "test/report.json",
                    json.dumps(
                        {
                            "sourceArchiveSha256": module.digest(raw),
                        }
                    ),
                )
                zipped.writestr(
                    "test/events.csv",
                    csv_text(
                        [
                            {
                                "event_id": key,
                                "company_id": "00000001",
                                "reference_month": "2020-01",
                                "label_candidate": "True",
                                "is_first_observed_month": "True",
                            }
                            for key in ["e1", "e2"]
                        ]
                    ),
                )
            audit = module.Audit(root / "audit")
            try:
                module.label_audit(audit, root, events, raw)
                self.assertFalse(audit.errors)
            finally:
                audit.stream.close()

    def test_source_transform_preserves_decimal_scale_and_negative_sign(self):
        for text, form, scale, sign, expected in [
            ("(1,234.50)", "numdotdecimal", "3", "", "-1234500"),
            ("1.234,50", "numcommadecimal", "-1", "", "123.450"),
            ("123", "numdotdecimal", "0", "-", "-123"),
            ("—", "zerodash", "0", "", "0"),
        ]:
            with self.subTest(text=text):
                fact = {"source_text": text, "format": form, "scale": scale, "sign": sign}
                self.assertEqual(module.source_amount(fact), Decimal(expected))

    def test_plain_dash_is_not_automatically_zero(self):
        with self.assertRaises(ValueError):
            module.source_amount(
                {"source_text": "-", "format": "numdotdecimal", "scale": "0", "sign": ""}
            )

    def test_amount_comparison_requires_same_currency_and_annual_spacing(self):
        current = {"end": "2023-12-31", "currency": "GBP", "values": {"cash": "100"}}
        previous = {"end": "2022-12-31", "currency": "EUR", "values": {"cash": "80"}}
        self.assertFalse(module.comparable("cash", current, previous))
        previous["currency"] = "GBP"
        self.assertTrue(module.comparable("cash", current, previous))
        previous["end"] = "2023-06-30"
        self.assertFalse(module.comparable("cash", current, previous))

    def test_flow_comparison_rejects_short_or_overlapping_periods(self):
        current = {
            "end": "2023-12-31",
            "currency": "GBP",
            "values": {"revenue": "100"},
            "starts": {"revenue": "2023-01-01"},
        }
        previous = {
            "end": "2022-12-31",
            "currency": "GBP",
            "values": {"revenue": "80"},
            "starts": {"revenue": "2022-07-01"},
        }
        self.assertFalse(module.comparable("revenue", current, previous))
        previous["starts"]["revenue"] = "2022-01-01"
        self.assertTrue(module.comparable("revenue", current, previous))

    def test_actual_input_hash_preserves_missing_zero_and_negative_values(self):
        contract = {
            "numericFeatureAllowlist": ["cash", "equity", "revenue", "cash_missing"],
            "categoricalFeatureAllowlist": ["financial_currency"],
        }
        row = {
            "cash": "0",
            "equity": "-1E+3",
            "revenue": "",
            "cash_missing": "False",
            "financial_currency": "GBP",
        }
        state = module.expected_state(row, contract)
        self.assertEqual(state, {"cash": 0, "equity": -1000, "financial_currency": "GBP"})
        self.assertNotEqual(module.state_hash(state), module.state_hash({**state, "revenue": 0}))


if __name__ == "__main__":
    unittest.main()
