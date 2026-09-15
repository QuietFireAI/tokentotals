"""Auditable pricing engine for TokenTotals.

The engine is intentionally boring: it reads a checked-in, dated catalog and refuses
unknown models. That is safer than silently inventing a fallback dollar rate.
"""
from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict

CATALOG_PATH = Path(__file__).with_name("pricing_catalog.json")


class UnknownModelPrice(ValueError):
    """Raised when TokenTotals does not have a verified price for a model."""


def _normalize_model(model: str) -> str:
    return (model or "").strip().lower()


@lru_cache(maxsize=1)
def load_catalog() -> Dict[str, Any]:
    with CATALOG_PATH.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data.get("models"), dict):
        raise RuntimeError("pricing_catalog.json is missing a models object")
    return data


def clear_catalog_cache() -> None:
    load_catalog.cache_clear()


def list_models() -> Dict[str, Dict[str, Any]]:
    return load_catalog()["models"]


def resolve_model(model: str) -> Dict[str, Any]:
    """Resolve an exact canonical model or declared alias.

    No fuzzy matching is used because a fuzzy match can silently price the wrong SKU.
    """
    wanted = _normalize_model(model)
    for canonical, record in list_models().items():
        names = [canonical, *record.get("aliases", [])]
        if wanted in {_normalize_model(name) for name in names}:
            resolved = dict(record)
            resolved["canonical_model"] = canonical
            resolved["verified_at"] = load_catalog().get("verified_at")
            resolved["source_url"] = load_catalog().get("sources", {}).get(record.get("source"))
            return resolved
    raise UnknownModelPrice(
        f"No verified pricing entry for model '{model}'. "
        "Update pricing_catalog.json from an official provider receipt before using this model."
    )


def calculate_cost(
    pricing: Dict[str, Any],
    input_tokens: int,
    output_tokens: int,
    *,
    conservative: bool = False,
) -> Dict[str, float]:
    """Calculate token cost using verified rates.

    conservative=True uses the catalog's guard rates, which intentionally choose the
    highest relevant published rate represented by the entry. The circuit breaker uses
    guard rates; post-response estimates use standard rates unless a vendor-reported
    cost is available elsewhere.
    """
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
    """Conservative local fallback token estimate.

    This is deliberately not advertised as an exact BPE count. It assumes at most
    roughly three UTF-8 characters per token and rounds upward. Provider-reported usage
    remains the preferred post-response source.
    """
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
