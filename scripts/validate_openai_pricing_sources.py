"""Non-destructive live validation of the official OpenAI pricing sources.

This script fetches and parses the live OpenAI model documentation into a temporary
candidate only. It never writes TokenTotals' runtime verified pricing snapshot.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import openai_pricing_sync


def main() -> int:
    # Redirect every sync artifact into a disposable directory before any source check.
    with tempfile.TemporaryDirectory(prefix="tokentotals-openai-source-check-") as tmp:
        root = Path(tmp)
        openai_pricing_sync.PRICING_DIR = root
        openai_pricing_sync.VERIFIED_PATH = root / "openai_verified.json"
        openai_pricing_sync.CANDIDATE_PATH = root / "openai_candidate.json"
        openai_pricing_sync.STATUS_PATH = root / "openai_sync_status.json"
        openai_pricing_sync.HISTORY_DIR = root / "history"

        candidate = openai_pricing_sync.build_candidate()
        openai_pricing_sync.validate_snapshot(candidate)

        summary = {
            model_id: {
                "input": record["input_price_per_1m"],
                "cached_input": record["cached_input_price_per_1m"],
                "cache_write": record.get("cache_write_price_per_1m"),
                "output": record["output_price_per_1m"],
                "guard_input": record["guard_input_price_per_1m"],
                "guard_output": record["guard_output_price_per_1m"],
                "source_url": record["source_url"],
                "source_hash": record["source_hash"],
            }
            for model_id, record in candidate["models"].items()
        }
        print(json.dumps({
            "provider": candidate["provider"],
            "source_checked_at": candidate["source_checked_at"],
            "combined_source_hash": candidate["combined_source_hash"],
            "models": summary,
        }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
