import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from tokentotals_cc import receipts  # noqa: E402


def assistant(msg_id, model, usage, block="text"):
    return {"type": "assistant", "timestamp": "2026-11-13T00:00:00Z", "requestId": "req_" + msg_id,
            "message": {"id": msg_id, "model": model, "role": "assistant",
                        "content": [{"type": block, "text": "SECRET RESPONSE TEXT"}], "usage": usage}}


def user(text):
    return {"type": "user", "message": {"role": "user", "content": text}}


U1 = {"input_tokens": 10, "cache_creation_input_tokens": 1000, "cache_read_input_tokens": 0, "output_tokens": 100,
      "cache_creation": {"ephemeral_5m_input_tokens": 1000, "ephemeral_1h_input_tokens": 0},
      "service_tier": "standard", "inference_geo": "global"}
U2 = {"input_tokens": 5, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 1000, "output_tokens": 50,
      "service_tier": "standard", "inference_geo": "us"}


class ReceiptTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["CLAUDE_PLUGIN_DATA"] = os.path.join(self.tmp.name, "data")
        self.transcript = os.path.join(self.tmp.name, "t.jsonl")

    def tearDown(self):
        self.tmp.cleanup()
        os.environ.pop("CLAUDE_PLUGIN_DATA", None)

    def write(self, entries, mode="w"):
        with open(self.transcript, mode, encoding="utf-8") as f:
            for e in entries:
                f.write(json.dumps(e) + "\n")

    def test_duplicate_lines_for_one_response_count_once(self):
        self.write([user("SECRET PROMPT"), assistant("m1", "claude-opus-5-5", U1, "thinking"),
                    assistant("m1", "claude-opus-5-5", U1, "text")])
        r = receipts.receipt_for_new_calls("s1", self.transcript)
        self.assertEqual(r["api_calls"], 1)
        expected = (10 * 4 + 1000 * 5 + 100 * 20) / 1e6
        self.assertAlmostEqual(r["estimated_cost_usd"], expected, places=12)
        self.assertEqual(r["cost_basis"], "provider_registry_complete")

    def test_second_turn_gets_only_new_calls(self):
        self.write([user("a"), assistant("m1", "claude-opus-5-5", U1)])
        receipts.receipt_for_new_calls("s1", self.transcript)
        self.write([user("b"), assistant("m2", "claude-sonnet-5-5", U2)], mode="a")
        r2 = receipts.receipt_for_new_calls("s1", self.transcript)
        self.assertEqual(r2["api_calls"], 1)
        expected = 1.1 * (5 * 2 + 1000 * 0.10 + 50 * 10) / 1e6  # US-only geo 1.1x
        self.assertAlmostEqual(r2["estimated_cost_usd"], expected, places=12)
        self.assertIsNone(receipts.receipt_for_new_calls("s1", self.transcript))
        self.assertEqual(receipts.session_total("s1")["receipts"], 2)

    def test_subagent_transcripts_are_counted(self):
        self.write([assistant("m1", "claude-opus-5-5", U1)])
        sub_dir = os.path.join(self.tmp.name, "t", "subagents")
        os.makedirs(sub_dir)
        with open(os.path.join(sub_dir, "agent-1.jsonl"), "w", encoding="utf-8") as f:
            sub = assistant("s1", "claude-haiku-5-5", {"input_tokens": 100, "output_tokens": 10,
                                                       "service_tier": "standard", "inference_geo": "global"})
            sub["isSidechain"] = True
            f.write(json.dumps(sub) + "\n")
        r = receipts.receipt_for_new_calls("s1", self.transcript)
        self.assertEqual(r["api_calls"], 2)
        self.assertEqual(r["subagent_api_calls"], 1)
        expected = (10 * 4 + 1000 * 5 + 100 * 20) / 1e6 + (100 * 0.10 + 10 * 0.50) / 1e6
        self.assertAlmostEqual(r["estimated_cost_usd"], expected, places=12)

    def test_unknown_model_is_unavailable_not_zero(self):
        self.write([assistant("m1", "claude-future-9", U1)])
        r = receipts.receipt_for_new_calls("s1", self.transcript)
        self.assertEqual(r["cost_basis"], "unavailable")
        self.assertIsNone(r["estimated_cost_usd"])
        self.assertIn("unavailable", receipts.render_standard(r))

    def test_synthetic_entries_are_skipped(self):
        self.write([assistant("m1", "<synthetic>", {"input_tokens": 0, "output_tokens": 0})])
        self.assertIsNone(receipts.receipt_for_new_calls("s1", self.transcript))

    def test_ledger_holds_no_prompt_or_response_text(self):
        self.write([user("SECRET PROMPT"), assistant("m1", "claude-opus-5-5", U1)])
        receipts.receipt_for_new_calls("s1", self.transcript)
        with open(receipts.ledger_path(), encoding="utf-8") as f:
            text = f.read()
        self.assertNotIn("SECRET", text)

    def test_hook_script_end_to_end(self):
        self.write([assistant("m1", "claude-opus-5-5", U1)])
        hook = os.path.join(ROOT, "bin", "tokentotals-run")
        payload = json.dumps({"session_id": "s1", "transcript_path": self.transcript, "hook_event_name": "Stop"})
        p = subprocess.run(["sh", hook, "tt_stop_hook.py"], input=payload, capture_output=True, text=True,
                           env=dict(os.environ))
        self.assertEqual(p.returncode, 0)
        out = json.loads(p.stdout)
        self.assertTrue(out["systemMessage"].startswith("Turn Receipt: $"))

    def test_hook_never_exits_nonzero_on_bad_input(self):
        hook = os.path.join(ROOT, "bin", "tokentotals-run")
        for payload in ("not json", "{}", json.dumps({"transcript_path": "/does/not/exist"})):
            p = subprocess.run(["sh", hook, "tt_stop_hook.py"], input=payload, capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, payload)
            self.assertEqual(p.stdout.strip(), "")


if __name__ == "__main__":
    unittest.main()
