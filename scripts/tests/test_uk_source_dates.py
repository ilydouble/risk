"""Date evidence must distinguish registration, legal commencement and publication."""

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1]))

from verify_uk_source_dates import (
    event_verdict,
    filings,
    insolvencies,
    ix_fingerprint,
    verify_report,
)


class SourceDateContracts(unittest.TestCase):
    def test_filing_date_is_not_date_in_description_and_pagination_is_retained(self):
        raw = b'''Company number SC123456 <table id="fhTable"><tr>
        <td>13 Mar 2020</td><td>WU01(Scot)</td><td>Court order made on 27 February 2020</td>
        <td><a href="/company/SC123456/filing-history/abc/document?format=pdf&amp;download=0">PDF</a></td>
        </tr></table><a id="next-page" href="/company/SC123456/filing-history?page=2">Next</a>'''
        entries, following = filings(raw, "SC123456")
        self.assertEqual(entries[0]["date"], "2020-03-13")
        self.assertIn("format=pdf&download=0", entries[0]["pdf"])
        self.assertTrue(following.endswith("?page=2"))

    def test_challenge_or_wrong_company_page_is_not_empty_evidence(self):
        for raw in [b"Check your browser", b'Company number SC000000 <table id="fhTable"></table>']:
            with self.assertRaises(ValueError):
                filings(raw, "SC123456")

    def test_petition_is_not_winding_up_and_case_types_are_not_mixed(self):
        raw = b'''Company number SC123456
        <p id="case-1">Case number 1 Compulsory liquidation</p>
        <dd id="petitioned-on_date_1">1 January 2020</dd>
        <dd id="wound-up-on_date_1">27 February 2020</dd>
        <p id="case-2">Case number 2 Administration</p>
        <dd id="wound-up-on_date_2">1 March 2020</dd>'''
        cases = insolvencies(raw, "SC123456")
        self.assertEqual(cases, [{"petitioned-on": "2020-01-01", "wound-up-on": "2020-02-27"}])

    def test_registration_match_does_not_verify_exact_order_or_publication_date(self):
        verdict = event_verdict(
            {"target_event_month": "2020-03", "observation_month": "2019-03"},
            [{"type": "WU01(Scot)", "date": "2020-03-13", "pdf": "official-document"}],
            [{"wound-up-on": "2020-02-27"}],
        )
        self.assertEqual(verdict["registry_month_status"], "order_filing_month_matches")
        self.assertTrue(verdict["start_month_differs_from_target"])
        self.assertFalse(verdict["exact_court_order_date_verified"])
        self.assertFalse(verdict["start_on_or_before_observation"])

    def test_appointment_is_not_a_court_order_filing(self):
        verdict = event_verdict(
            {"target_event_month": "2020-03", "observation_month": "2020-02"},
            [{"type": "WU03(Scot)", "date": "2020-03-13", "pdf": "appointment"}],
            [{"wound-up-on": "2020-02-27"}],
        )
        self.assertEqual(verdict["registry_month_status"], "unresolved_no_matching_order_filing")
        self.assertTrue(verdict["start_on_or_before_observation"])

    def test_archive_month_is_not_used_to_force_registry_date_agreement(self):
        import gzip
        import hashlib

        class Fetch:
            def get(self, url):
                return b"same report", {"sha256": "evidence"}

        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "original.gz"
            path.write_bytes(gzip.compress(b"same report"))
            report = {"report_id": "r", "company_id": "SC123456", "period_end": "2018-12-31",
                      "filing_month": "2019-06", "availability_upper_bound": "2019-07-31",
                      "raw_cache_path": str(path), "member_sha256": hashlib.sha256(b"same report").hexdigest()}
            entry = {"type": "AA", "date": "2019-07-01", "description": "Accounts made up to 31 December 2018", "xhtml": "official"}
            result = verify_report(report, [entry], Fetch())
        self.assertTrue(result["filing_date_exact_verified"])
        self.assertFalse(result["archive_month_matches_registry_date"])
        self.assertEqual(result["filing_date_exact"], "2019-07-01")

    def test_incomplete_history_does_not_verify_date_from_partial_match(self):
        from verify_uk_source_dates import verify_financial_company

        class Fetch:
            def get(self, url):
                raise OSError("interrupted history")

        report = {"report_id": "r", "company_id": "SC123456", "period_end": "2018-12-31"}
        with patch("verify_uk_source_dates.verify_report", return_value={"report_id": "r", "status": "verified_registry_filing_date", "filing_date_exact_verified": True}):
            result = verify_financial_company(("SC123456", [report]), Fetch())
        self.assertEqual(result["reports"][0]["status"], "unresolved_history_incomplete")
        self.assertFalse(result["reports"][0]["filing_date_exact_verified"])

    def test_tagged_fingerprint_preserves_scale_context_and_units(self):
        original = b'''<html xmlns:ix="http://www.xbrl.org/2013/inlineXBRL"
          xmlns:x="http://www.xbrl.org/2003/instance" xmlns:g="urn:gaap" xmlns:c="urn:currency">
          <x:context id="p"><x:period><x:instant>2020-12-31</x:instant></x:period></x:context>
          <x:unit id="u"><x:measure>c:GBP</x:measure></x:unit>
          <ix:nonFraction name="g:Assets" contextRef="p" unitRef="u" scale="3">10</ix:nonFraction>
          <ix:nonNumeric name="g:Policy" contextRef="p">a<br/>b</ix:nonNumeric></html>'''
        rendering = original.replace(b'a<br/>b', b'a <br/> b').replace(b'xmlns:g=', b'xmlns:z=').replace(b'g:', b'z:')
        self.assertEqual(ix_fingerprint(original), ix_fingerprint(rendering))
        for altered in [original.replace(b'scale="3"', b'scale="0"'),
                        original.replace(b'c:GBP', b'c:USD'),
                        original.replace(b'2020-12-31', b'2021-12-31'),
                        original.replace(b'>10<', b'>11<')]:
            self.assertNotEqual(ix_fingerprint(original), ix_fingerprint(altered))


if __name__ == "__main__":
    unittest.main()
