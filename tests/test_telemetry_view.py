import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import telemetry_view
import turn_ledger


class TelemetryViewTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.ledger_path = Path(self.tempdir.name) / "turns.jsonl"
        self.override = patch.object(turn_ledger, "_LEDGER_FILE_OVERRIDE", self.ledger_path)
        self.override.start()
        self.addCleanup(self.override.stop)
        with turn_ledger._LEDGER_LOCK:
            turn_ledger._SEEN_LEDGER_PATH = None
            turn_ledger._SEEN_TURN_IDS = None
        self.addCleanup(self._reset_seen)

    def _reset_seen(self):
        with turn_ledger._LEDGER_LOCK:
            turn_ledger._SEEN_LEDGER_PATH = None
            turn_ledger._SEEN_TURN_IDS = None

    def _record(
        self,
        turn_id,
        model,
        provider,
        *,
        input_tokens,
        output_tokens,
        total_tokens=None,
        cached_tokens=None,
        reasoning_tokens=None,
        cost=None,
        latency_ms=1000,
    ):
        tokens = {
            "input_tokens": input_tokens,
            "uncached_input_tokens": (
                input_tokens - cached_tokens if cached_tokens is not None else None
            ),
            "cached_input_tokens": cached_tokens,
            "cache_write_tokens": None,
            "output_tokens": output_tokens,
            "reasoning_tokens": reasoning_tokens,
            "tool_input_tokens": None,
            "provider_reported_total_tokens": total_tokens,
            "reconstructed_total_tokens": input_tokens + output_tokens,
            "unclassified_tokens": (
                max(0, total_tokens - (input_tokens + output_tokens))
                if total_tokens is not None
                else None
            ),
            "reconciliation_delta_tokens": (
                total_tokens - (input_tokens + output_tokens)
                if total_tokens is not None
                else None
            ),
        }
        basis = {
            name: ("unavailable" if value is None else "observed")
            for name, value in tokens.items()
        }
        basis["reconstructed_total_tokens"] = "derived"
        if cached_tokens is not None:
            basis["uncached_input_tokens"] = "derived"
        if total_tokens is not None:
            basis["unclassified_tokens"] = "derived"
            basis["reconciliation_delta_tokens"] = "derived"
        return {
            "turn_id": turn_id,
            "thread_id": "thread-1",
            "provider": provider,
            "requested_model_id": model,
            "canonical_model_id": model,
            "observed_model_id": model,
            "completed_at": f"2026-09-15T22:00:0{turn_id[-1]}+00:00",
            "latency_ms": latency_ms,
            "tokens": tokens,
            "token_basis": basis,
            "estimated_cost_usd": cost,
            "cost_basis": (
                "provider_registry_complete" if cost is not None else "unavailable"
            ),
            "estimate_complete": cost is not None,
            "registry_verified_at": "2026-09-15",
        }

    def _seed_mixed_thread(self):
        records = [
            self._record(
                "turn-1",
                "gemini-3.8-flash",
                "google",
                input_tokens=80,
                output_tokens=20,
                total_tokens=100,
                cached_tokens=40,
                reasoning_tokens=None,
                cost=0.10,
                latency_ms=1000,
            ),
            self._record(
                "turn-2",
                "claude-sonnet-5",
                "anthropic",
                input_tokens=180,
                output_tokens=20,
                total_tokens=200,
                cached_tokens=None,
                reasoning_tokens=5,
                cost=None,
                latency_ms=500,
            ),
            self._record(
                "turn-3",
                "gemini-3.8-flash",
                "google",
                input_tokens=900,
                output_tokens=100,
                total_tokens=1000,
                cached_tokens=450,
                reasoning_tokens=0,
                cost=0.40,
                latency_ms=2000,
            ),
        ]
        for record in records:
            self.assertTrue(turn_ledger.append_turn(record))

    def test_thread_view_preserves_mixed_model_totals_and_cost_coverage(self):
        self._seed_mixed_thread()
        view = telemetry_view.thread_view("thread-1")

        self.assertEqual(view["turn_count"], 3)
        self.assertEqual([item["model_id"] for item in view["by_model"]], [
            "gemini-3.8-flash",
            "claude-sonnet-5",
        ])
        gemini = view["by_model"][0]
        claude = view["by_model"][1]
        self.assertEqual(gemini["turn_count"], 2)
        self.assertEqual(gemini["tokens"]["input_tokens"]["sum"], 980)
        self.assertEqual(gemini["cost"]["costed_turns"], 2)
        self.assertEqual(gemini["cost"]["coverage"], "complete")
        self.assertEqual(claude["turn_count"], 1)
        self.assertEqual(claude["cost"]["estimated_cost_usd"], None)
        self.assertEqual(claude["cost"]["coverage"], "unavailable")

        self.assertEqual(view["cost"]["estimated_cost_usd"], 0.5)
        self.assertEqual(view["cost"]["costed_turns"], 2)
        self.assertEqual(view["cost"]["total_turns"], 3)
        self.assertEqual(view["cost"]["coverage"], "partial")

    def test_thread_token_coverage_does_not_turn_missing_into_zero(self):
        self._seed_mixed_thread()
        view = telemetry_view.thread_view("thread-1")

        reasoning = view["tokens"]["reasoning_tokens"]
        self.assertEqual(reasoning["sum"], 5)
        self.assertEqual(reasoning["observed_turns"], 2)
        self.assertEqual(reasoning["total_turns"], 3)
        self.assertEqual(reasoning["coverage"], "partial")

        cache_write = view["tokens"]["cache_write_tokens"]
        self.assertIsNone(cache_write["sum"])
        self.assertEqual(cache_write["observed_turns"], 0)
        self.assertEqual(cache_write["coverage"], "unavailable")

    def test_turn_size_stats_use_provider_total_then_reconstructed_fallback(self):
        self._seed_mixed_thread()
        view = telemetry_view.thread_view("thread-1")
        stats = view["turn_token_stats"]

        self.assertEqual(stats["sampled_turns"], 3)
        self.assertEqual(stats["sum"], 1300)
        self.assertAlmostEqual(stats["average"], 1300 / 3)
        self.assertEqual(stats["median"], 200)
        self.assertEqual(stats["p95_nearest_rank"], 1000)
        self.assertEqual(stats["max"], 1000)
        self.assertEqual(stats["coverage"], "complete")

    def test_latest_turn_exposes_token_basis_cache_share_and_wall_clock_rate(self):
        self._seed_mixed_thread()
        latest = telemetry_view.thread_view("thread-1")["latest_turn"]

        self.assertEqual(latest["model"]["canonical"], "gemini-3.8-flash")
        self.assertEqual(latest["turn_total_tokens"], {
            "value": 1000,
            "basis": "provider_reported",
        })
        self.assertEqual(latest["tokens"]["reasoning_tokens"], {
            "value": 0,
            "basis": "observed",
        })
        self.assertEqual(latest["cache_share"]["pct_of_input"], 50.0)
        self.assertEqual(latest["output_tokens_per_wall_second"], 50.0)
        self.assertIn("not pure model generation throughput", latest["output_rate_scope"])
        self.assertEqual(latest["cost"]["estimated_usd"], 0.40)
        self.assertEqual(latest["cost"]["basis"], "provider_registry_complete")

    def test_context_is_explicitly_unavailable_not_invented(self):
        self._seed_mixed_thread()
        context = telemetry_view.thread_view("thread-1")["context"]
        self.assertEqual(context["status"], "unavailable")
        self.assertIn("No defensible normalized", context["reason"])

    def test_empty_thread_returns_none(self):
        self.assertIsNone(telemetry_view.thread_view("does-not-exist"))

    def test_presentation_contains_no_financial_clearance_language(self):
        self._seed_mixed_thread()
        text = str(telemetry_view.thread_view("thread-1")).lower()
        for prohibited in ("remaining budget", "available headroom", "runway", "you have $"):
            self.assertNotIn(prohibited, text)


if __name__ == "__main__":
    unittest.main()
