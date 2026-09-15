"""Daily stop-the-line integrity refresh for TokenTotals pricing surfaces.

A successful run means all represented providers passed official-source checks before
freshness metadata and generated public pricing surfaces are updated. A failed source
check must fail the workflow; it must never stamp stale pricing as current.
"""
from __future__ import annotations

import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import generate_model_matrix
import matrix_source_check
import openai_pricing_sync
import pricing_engine

CATALOG_PATH = ROOT / "pricing_catalog.json"
MAX_SAFE_RATE_FACTOR = 5.0
RATE_ABS_TOLERANCE = 1e-12

RATE_FIELDS = (
    "input_price_per_1m",
    "cached_input_price_per_1m",
    "cache_write_price_per_1m",
    "output_price_per_1m",
    "guard_input_price_per_1m",
    "guard_output_price_per_1m",
)
OPENAI_SEMANTIC_FIELDS = (
    *RATE_FIELDS,
    "pricing_rules",
)
OPENAI_COPY_FIELDS = (
    "aliases",
    *RATE_FIELDS,
    "source_url",
    "source_markdown_url",
    "source_hash",
    "pricing_rules",
)


def _utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_catalog() -> dict:
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def _normalize_rate(value: object) -> object:
    """Keep JSON pricing stable when binary floats produce display-noise changes."""
    if isinstance(value, (int, float)):
        return round(float(value), 12)
    return value


def _rates_equal(old: object, new: object) -> bool:
    if isinstance(old, (int, float)) and isinstance(new, (int, float)):
        return math.isclose(
            float(old), float(new), rel_tol=0.0, abs_tol=RATE_ABS_TOLERANCE
        )
    return old == new


def _semantic_equal(field: str, old: object, new: object) -> bool:
    if field in RATE_FIELDS:
        return _rates_equal(old, new)
    return old == new


def _rate_factor(old: object, new: object) -> float:
    if old is None or new is None:
        return 1.0
    if not isinstance(old, (int, float)) or not isinstance(new, (int, float)):
        return 1.0
    if old <= 0 or new <= 0:
        return math.inf
    return max(float(new) / float(old), float(old) / float(new))


def _refresh_openai(catalog: dict) -> tuple[dict, list[dict]]:
    candidate = openai_pricing_sync.build_candidate()
    openai_pricing_sync.validate_snapshot(candidate)

    previous_refresh = catalog.get("daily_integrity_refresh", {}) or {}
    previous_openai = (previous_refresh.get("providers", {}) or {}).get("OpenAI", {}) or {}
    previous_hash = previous_openai.get("combined_source_hash")
    semantic_changes: list[dict] = []

    live_models = set(candidate["models"])
    catalog_models = {
        model_id
        for model_id, record in catalog.get("models", {}).items()
        if record.get("provider") == "OpenAI"
    }
    if live_models != catalog_models:
        raise RuntimeError(
            "OpenAI represented model set changed. Refusing implicit daily model-set expansion/removal; review and deliberately update the supported catalog. "
            f"live={sorted(live_models)} catalog={sorted(catalog_models)}"
        )

    for model_id, live in candidate["models"].items():
        current = catalog["models"][model_id]
        for field in RATE_FIELDS:
            factor = _rate_factor(current.get(field), live.get(field))
            if factor > MAX_SAFE_RATE_FACTOR:
                raise RuntimeError(
                    f"OpenAI {model_id} {field} changed by {factor:.2f}x; refusing automatic daily promotion"
                )

        for field in OPENAI_SEMANTIC_FIELDS:
            old = current.get(field)
            new = live.get(field)
            if not _semantic_equal(field, old, new):
                semantic_changes.append(
                    {
                        "model": model_id,
                        "field": field,
                        "old": _normalize_rate(old) if field in RATE_FIELDS else old,
                        "new": _normalize_rate(new) if field in RATE_FIELDS else new,
                    }
                )

        for field in OPENAI_COPY_FIELDS:
            if field in live:
                value = live[field]
                current[field] = _normalize_rate(value) if field in RATE_FIELDS else value
        current["provider"] = "OpenAI"
        current["source"] = "openai"

    new_hash = candidate["combined_source_hash"]
    if previous_hash and previous_hash != new_hash and not semantic_changes:
        raise RuntimeError(
            "OpenAI source content changed without a recognized supported pricing/rule change; manual review required before stamping the daily refresh current"
        )

    return candidate, semantic_changes


def _dated_provider_receipt(provider: str, audit: dict) -> dict:
    info = audit["providers"][provider]
    return {
        "status": "verified",
        "source_url": info["source"],
        "source_sha256": info["source_sha256"],
        "models_checked": [row["model"] for row in info["models"]],
        "mode": "official live base+guard drift validation; mismatch, missing model, parse ambiguity, or expiry fails closed",
    }


def refresh() -> dict:
    # Validate all providers first. No freshness metadata is written before these pass.
    catalog = _load_catalog()
    dated_audit = matrix_source_check.validate_live_sources()
    openai_candidate, openai_changes = _refresh_openai(catalog)

    checked_at = _utcnow()
    verified_date = checked_at[:10]
    catalog["verified_at"] = verified_date
    catalog["daily_integrity_refresh"] = {
        "status": "verified",
        "source_checked_at": checked_at,
        "verified_at": verified_date,
        "providers": {
            "OpenAI": {
                "status": "verified",
                "source_url": "https://developers.openai.com/api/docs/pricing",
                "combined_source_hash": openai_candidate["combined_source_hash"],
                "models_checked": sorted(openai_candidate["models"]),
                "recognized_changes": openai_changes,
                "mode": "official structured source parse; recognized safe changes refresh catalog, suspicious/source-only/model-set changes fail closed",
            },
            "Anthropic": _dated_provider_receipt("Anthropic", dated_audit),
            "Google": _dated_provider_receipt("Google", dated_audit),
        },
    }

    # Only after all live checks pass do we write today's catalog receipt.
    CATALOG_PATH.write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8")
    pricing_engine.clear_catalog_cache()
    generate_model_matrix.write_all()

    summary = {
        "status": "verified",
        "source_checked_at": checked_at,
        "verified_at": verified_date,
        "providers": catalog["daily_integrity_refresh"]["providers"],
        "generated": [
            "pricing_catalog.json",
            "MODEL_COMPARISON_MATRIX.md",
            "README.md pricing block",
            "TokenTotals_Security_Whitepaper.md pricing receipt",
            "docs/PRICING_DAILY_STATUS.md",
        ],
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return summary


def main() -> int:
    refresh()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
