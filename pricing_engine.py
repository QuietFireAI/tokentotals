"""Auditable pricing engine for TokenTotals.

The engine reads the checked-in catalog and may overlay a locally verified OpenAI
snapshot produced from official OpenAI documentation. Unknown models never receive a
made-up dollar rate.
"""
from __future__ import annotations

import json
import math
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict

CATALOG_PATH = Path(__file__).with_name("pricing_catalog.json")


class UnknownModelPrice(ValueError):
    """Raised when TokenTotals does not have a verified price for a model."""


def _normalize_model(model: str) -> str:
    return (model or "").strip().lower()


def _openai_verified_path() -> Path:
    pricing_dir = Path(os.environ.get(
        "TOKENTOTALS_PRICING_DIR",
        str(Path.home() / ".tokentotals" / "pricing"),
    ))
    return pricing_dir / "openai_verified.json"


def _load_verified_openai_overlay() -> Dict[str, Any] | None:
    path = _openai_verified_path()
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as handle:
            snapshot = json.load(handle)
    except Exception:
        return None
    if snapshot.get("provider") != "OpenAI" or snapshot.get("status") != "verified":
        return None
    models = snapshot.get("models")
    if not isinstance(models, dict) or not models:
        return None
    return snapshot


@lru_cache(maxsize=1)
def load_catalog() -> Dict[str, Any]:
    with CATALOG_PATH.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data.get("models"), dict):
        raise RuntimeError("pricing_catalog.json is missing a models object")

    overlay = _load_verified_openai_overlay()
    if overlay:
        for model_id, record in overlay["models"].items():
            if record.get("provider") != "OpenAI":
                continue
            merged = dict(record)
            merged["verified_at"] = overlay.get("verified_at")
            merged["source_checked_at"] = overlay.get("source_checked_at")
            data["models"][model_id] = merged
        data.setdefault("dynamic_sources", {})["openai"] = {
            "verified_at": overlay.get("verified_at"),
            "source_checked_at": overlay.get("source_checked_at"),
            "combined_source_hash": overlay.get("combined_source_hash"),
        }
    return data


def clear_catalog_cache() -> None:
    load_catalog.cache_clear()


def list_models() -> Dict[str, Dict[str, Any]]:
    return load_catalog()["models"]


def resolve_model(model: str) -> Dict[str, Any]:
    """Resolve a canonical model or declared alias without fuzzy matching."""
    wanted = _normalize_model(model)
    catalog = load_catalog()
    for canonical, record in catalog["models"].items():
        names = [canonical, *record.get("aliases", [])]
        if wanted in {_normalize_model(name) for name in names}:
            resolved = dict(record)
            resolved["canonical_model"] = canonical
            resolved["verified_at"] = record.get("verified_at") or catalog.get("verified_at")
            resolved["source_url"] = (
                record.get("source_url")
                or catalog.get("sources", {}).get(record.get("source"))
            )
            return resolved
    raise UnknownModelPrice(
        f"No verified pricing entry for model '{model}'. "
        "Update the verified pricing catalog from an official provider receipt before "
        "using this model."
    )


def calculate_cost(
    pricing: Dict[str, Any],
    input_tokens: int,
    output_tokens: int,
    *,
    conservative: bool = False,
) -> Dict[str, float]:
    """Calculate the current supported text-token estimate from verified rates."""
    input_tokens = max(0, int(input_tokens or 0))
    output_tokens = max(0, int(output_tokens or 0))
    in_key = "guard_input_price_per_1m" if conservative else "input_price_per_1m"
    out_key = "guard_output_price_per_1m" if conservative else "output_price_per_1m"
    in_rate = float(pricing[in_key])
    out_rate = float(pricing[out_key])
    input_cost = (input_tokens / 1_000_000.0) * in_rate
    output_cost = (output_tokens / 1_000_000.0) * out_rate
    return {
        "input_cost_usd": input_cost,
        "output_cost_usd": output_cost,
        "total_cost_usd": input_cost + output_cost,
        "input_rate_per_1m": in_rate,
        "output_rate_per_1m": out_rate,
    }


def estimate_text_tokens(text: str, model: str | None = None) -> int:
    """Conservative local token estimate; not a provider/model tokenizer."""
    raw = (text or "").encode("utf-8")
    return max(1, math.ceil(len(raw) / 3.0))


def affordable_output_tokens(
    pricing: Dict[str, Any],
    remaining_usd_after_input: float,
) -> int:
    """Maximum output tokens affordable at the conservative guard output rate."""
    rate = float(pricing["guard_output_price_per_1m"])
    if rate <= 0 or remaining_usd_after_input <= 0:
        return 0
    return max(0, math.floor((remaining_usd_after_input * 1_000_000.0) / rate))
