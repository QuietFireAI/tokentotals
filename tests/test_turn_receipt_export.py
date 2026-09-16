import csv
import io
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import proxy_server
import turn_ledger
import turn_receipt_export
import turn_receipt_chat_surface


class TurnReceiptExportTests(unittest.TestCase):
    def _record(self, turn_id, cost, *, model="gpt-example", provider="openai", thread_id="thread-a"):
        tokens = {name: None for name in turn_ledger.TOKEN_FIELDS}
        basis = {name: "unavailable" for name in turn_ledger.TOKEN_FIELDS}
        tokens.update({
            "input_tokens": 100,
            "cached_input_tokens": 20,
            "uncached_input_tokens": 80,
            "output_tokens": 25,
            "provider_reported_total_tokens": 125,
            "reconstructed_total_tokens": 125,
        })
        basis.update({
            "input_tokens": "observed",
            "cached_input_tokens": "observed",
            "uncached_input_tokens": "derived",
            "output_tokens": "observed",
            "provider_reported_total_tokens": "observed",
            "reconstructed_total_tokens": "derived",
        })
        return {
            "turn_id": turn_id,
            "thread_id": thread_id,
            "started_at": "2026-09-16T12:00:00+00:00",
            "completed_at": "2026-09-16T12:00:01+00:00",
            "latency_ms": 1000,
            "provider": provider,
            "requested_model_id": model,
            "canonical_model_id": model,
            "observed_model_id": model,
            "requested_service_tier": None,
            "observed_service_tier": "standard",
            "tokens": tokens,
            "token_basis": basis,
            "modalities": {},
            "server_tools": {},
            "estimated_cost_usd": cost,
            "pricing_components_usd": {},
            "cost_basis": "provider_registry_complete" if cost is not None else "unavailable",
            "estimate_complete": cost is not None,
            "registry_verified_at": "2026-09-16",
            "notes": [],
            # These deliberately-sensitive extras must never leak to the export.
            "prompt_text": "SECRET PROMPT",
            "response_text": "SECRET ANSWER",
            "api_key": "SECRET KEY",
        }

    def _parse(self, text):
        return list(csv.DictReader(io.StringIO(text.lstrip("\ufeff"))))

    def test_one_row_per_completed_turn_with_running_cost_and_coverage(self):
        records = [
            self._record("turn-1", None),
            self._record("turn-2", 0.0),
            self._record("turn-3", 0.125),
        ]
        with patch.object(turn_receipt_export.turn_ledger, "read_turns", return_value=records):
            rows = self._parse(turn_receipt_export.thread_csv("thread-a"))

        self.assertEqual([row["turn_number"] for row in rows], ["1", "2", "3"])
        self.assertEqual(rows[0]["turn_estimate_usd"], "")
        self.assertEqual(rows[0]["running_thread_estimate_usd"], "")
        self.assertEqual(rows[0]["thread_cost_coverage_to_date"], "unavailable")
        self.assertEqual(rows[1]["turn_estimate_usd"], "0")
        self.assertEqual(rows[1]["running_thread_estimate_usd"], "0")
        self.assertEqual(rows[1]["costed_turns_to_date"], "1")
        self.assertEqual(rows[1]["thread_cost_coverage_to_date"], "partial")
        self.assertEqual(rows[2]["running_thread_estimate_usd"], "0.125")
        self.assertEqual(rows[2]["costed_turns_to_date"], "2")
        self.assertEqual(rows[2]["thread_cost_coverage_to_date"], "partial")

    def test_export_uses_canonical_receipt_fields_and_excludes_content_and_keys(self):
        record = self._record("turn-private", 0.0125)
        with patch.object(turn_receipt_export.turn_ledger, "read_turns", return_value=[record]):
            text = turn_receipt_export.thread_csv("thread-a")
        header = text.lstrip("\ufeff").splitlines()[0]
        self.assertIn("receipt_id", header)
        self.assertIn("estimate_status", header)
        self.assertNotIn("prompt_text", header)
        self.assertNotIn("response_text", header)
        self.assertNotIn("api_key", header)
        self.assertNotIn("SECRET PROMPT", text)
        self.assertNotIn("SECRET ANSWER", text)
        self.assertNotIn("SECRET KEY", text)

    def test_spreadsheet_formula_prefixes_are_neutralized(self):
        record = self._record(
            "=SUM(A1:A2)",
            0.01,
            model="  +cmd|' /C calc'!A0",
            provider="@danger",
            thread_id="-thread",
        )
        with patch.object(turn_receipt_export.turn_ledger, "read_turns", return_value=[record]):
            row = self._parse(turn_receipt_export.thread_csv("-thread"))[0]
        self.assertTrue(row["receipt_id"].startswith("'="))
        self.assertTrue(row["model"].startswith("'  +"))
        self.assertTrue(row["provider"].startswith("'@"))
        self.assertTrue(row["thread_id"].startswith("'-"))

    def test_unknown_thread_returns_none_and_blank_id_is_rejected(self):
        with patch.object(turn_receipt_export.turn_ledger, "read_turns", return_value=[]):
            self.assertIsNone(turn_receipt_export.thread_csv("missing"))
        with self.assertRaisesRegex(ValueError, "thread_id must be non-empty"):
            turn_receipt_export.thread_rows("   ")

    def test_http_export_is_attachment_and_surfaces_missing_thread(self):
        client = TestClient(proxy_server.app)
        with patch.object(proxy_server.turn_receipt_export, "thread_csv", return_value="\ufeffa,b\r\n1,2\r\n") as mocked:
            response = client.get("/api/threads/thread-a/turn-receipts.csv")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.headers["content-type"].startswith("text/csv"))
        self.assertIn("TokenTotals_Thread_Receipts.csv", response.headers["content-disposition"])
        self.assertEqual(response.headers["x-content-type-options"], "nosniff")
        mocked.assert_called_once_with("thread-a")

        with patch.object(proxy_server.turn_receipt_export, "thread_csv", return_value=None):
            missing = client.get("/api/threads/missing/turn-receipts.csv")
        self.assertEqual(missing.status_code, 404)

    def test_http_export_surfaces_ledger_corruption(self):
        client = TestClient(proxy_server.app)
        with patch.object(
            proxy_server.turn_receipt_export,
            "thread_csv",
            side_effect=turn_ledger.LedgerCorruptionError("bad export line"),
        ):
            response = client.get("/api/threads/thread-a/turn-receipts.csv")
        self.assertEqual(response.status_code, 500)
        self.assertIn("bad export line", response.json()["detail"])

    def test_chat_surface_exposes_export_only_after_receipt_settles(self):
        html = turn_receipt_chat_surface.CHAT_HTML
        self.assertIn('id="exportThreadButton" type="button" disabled', html)
        self.assertIn('/api/threads/${encodeURIComponent(threadId)}/turn-receipts.csv', html)
        self.assertIn('exportThreadButton.disabled = false', html)
        self.assertIn('exportThreadButton.disabled = true', html)
        self.assertIn('exportThreadButton.addEventListener("click", exportThreadCsv)', html)

    def test_windows_package_workflow_tracks_export_runtime_and_guide(self):
        workflow = Path(".github/workflows/windows-package.yml").read_text(encoding="utf-8")
        self.assertEqual(workflow.count('      - "turn_receipt_export.py"'), 2)
        self.assertEqual(workflow.count('      - "USER_GUIDE.md"'), 2)


if __name__ == "__main__":
    unittest.main()
