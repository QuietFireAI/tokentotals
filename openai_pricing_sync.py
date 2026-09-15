"""Official OpenAI pricing synchronization for TokenTotals.

Only official developers.openai.com model documentation is fetched. A complete candidate
for every supported OpenAI model must parse and validate before it can replace the last
verified OpenAI snapshot used by the runtime.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, Any

PRICING_DIR = Path(os.environ.get(
    "TOKENTOTALS_PRICING_DIR",
    str(Path.home() / ".tokentotals" / "pricing"),
))
VERIFIED_PATH = PRICING_DIR / "openai_verified.json"
CANDIDATE_PATH = PRICING_DIR / "openai_candidate.json"
STATUS_PATH = PRICING_DIR / "openai_sync_status.json"
HISTORY_DIR = PRICING_DIR / "history"

MODEL_SPECS = {
    "gpt-6-astra": {
        "url": "https://developers.openai.com/api/docs/models/gpt-6-astra.md",
        "aliases": ["openai/gpt-6-astra"],
    },
    "gpt-5.6-sol": {
        "url": "https://developers.openai.com/api/docs/models/gpt-5.6-sol.md",
        "aliases": ["gpt-5.6", "openai/gpt-5.6-sol", "openai/gpt-5.6"],
    },
    "gpt-5.6-terra": {
        "url": "https://developers.openai.com/api/docs/models/gpt-5.6-terra.md",
        "aliases": ["openai/gpt-5.6-terra"],
    },
    "gpt-5.6-luna": {
        "url": "https://developers.openai.com/api/docs/models/gpt-5.6-luna.md",
        "aliases": ["openai/gpt-5.6-luna"],
    },
}

MAX_AUTOPROMOTE_RATE_FACTOR = 5.0
_SYNC_THREAD = None
_SYNC_LOCK = threading.Lock()


class PricingSyncError(RuntimeError):
    pass


def _utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _atomic_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, sort_keys=True)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)


def _fetch_text(url: str, timeout: int = 15) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "TokenTotals/3 OpenAIPricingSync",
            "Accept": "text/markdown,text/plain;q=0.9,*/*;q=0.1",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        if getattr(response, "status", 200) != 200:
            raise PricingSyncError(f"OpenAI pricing source returned HTTP {response.status}: {url}")
        return response.read().decode("utf-8")


def _money_after(label: str, text: str) -> float | None:
    patterns = [
        rf"(?ims)(?:^|\n)\s*{re.escape(label)}\s*(?:\||:|-)?\s*\n+\s*(?:\|?\s*)?\$([0-9]+(?:\.[0-9]+)?)",
        rf"(?im)^\s*\|?\s*{re.escape(label)}\s*\|[^$\n]*\$([0-9]+(?:\.[0-9]+)?)",
        rf"(?i){re.escape(label)}\s*[:|-]\s*\$([0-9]+(?:\.[0-9]+)?)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return float(match.group(1))
    return None


def parse_model_markdown(model_id: str, text: str, source_url: str) -> Dict[str, Any]:
    input_rate = _money_after("Input", text)
    cached_rate = _money_after("Cached input", text)
    cache_write_rate = _money_after("Cache writes", text)
    output_rate = _money_after("Output", text)

    if input_rate is None or cached_rate is None or output_rate is None:
        raise PricingSyncError(
            f"{model_id}: could not parse required Input/Cached input/Output rates"
        )

    write_mult = None
    match = re.search(
        r"Cache writes are billed at\s+([0-9]+(?:\.[0-9]+)?)x\s+the uncached input token rate",
        text,
        re.I,
    )
    if match:
        write_mult = float(match.group(1))
        if cache_write_rate is None:
            cache_write_rate = input_rate * write_mult

    long_threshold = None
    long_input_mult = None
    long_cache_mult = None
    long_output_mult = None
    match = re.search(
        r"(?:more than|>)\s*([0-9]+)K input tokens are priced at\s+"
        r"([0-9]+(?:\.[0-9]+)?)x input"
        r"(?: and cache rates)?\s+and\s+"
        r"([0-9]+(?:\.[0-9]+)?)x output",
        text,
        re.I,
    )
    if match:
        long_threshold = int(match.group(1)) * 1000
        long_input_mult = float(match.group(2))
        long_output_mult = float(match.group(3))
        if "and cache rates" in match.group(0).lower():
            long_cache_mult = long_input_mult

    batch_mult = flex_mult = fast_mult = None
    match = re.search(
        r"Batch and Flex are priced at\s+([0-9]+(?:\.[0-9]+)?)%\s+of Standard rates\.\s*"
        r"Fast mode is priced at\s+([0-9]+(?:\.[0-9]+)?)x",
        text,
        re.I,
    )
    if match:
        batch_mult = flex_mult = float(match.group(1)) / 100.0
        fast_mult = float(match.group(2))

    input_guard_mult = max(1.0, long_input_mult or 1.0)
    output_guard_mult = max(1.0, long_output_mult or 1.0)
    if fast_mult:
        input_guard_mult *= fast_mult
        output_guard_mult *= fast_mult

    source_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    spec = MODEL_SPECS[model_id]

    return {
        "provider": "OpenAI",
        "aliases": list(spec["aliases"]),
        "input_price_per_1m": input_rate,
        "cached_input_price_per_1m": cached_rate,
        "cache_write_price_per_1m": cache_write_rate,
        "output_price_per_1m": output_rate,
        "guard_input_price_per_1m": input_rate * input_guard_mult,
        "guard_output_price_per_1m": output_rate * output_guard_mult,
        "source": "openai",
        "source_url": source_url.removesuffix(".md"),
        "source_markdown_url": source_url,
        "source_hash": source_hash,
        "pricing_rules": {
            "cache_write_multiplier": write_mult,
            "long_context": {
                "threshold_input_tokens": long_threshold,
                "input_multiplier": long_input_mult,
                "cache_multiplier": long_cache_mult,
                "output_multiplier": long_output_mult,
            } if long_threshold else None,
            "service_tier_multipliers": {
                "batch": batch_mult,
                "flex": flex_mult,
                "fast": fast_mult,
            },
        },
    }


def build_candidate(fetcher: Callable[[str], str] = _fetch_text) -> Dict[str, Any]:
    checked_at = _utcnow()
    models: Dict[str, Any] = {}
    combined_hash = hashlib.sha256()

    for model_id, spec in MODEL_SPECS.items():
        text = fetcher(spec["url"])
        record = parse_model_markdown(model_id, text, spec["url"])
        models[model_id] = record
        combined_hash.update(model_id.encode("utf-8"))
        combined_hash.update(record["source_hash"].encode("ascii"))

    candidate = {
        "schema_version": 1,
        "provider": "OpenAI",
        "source_checked_at": checked_at,
        "verified_at": checked_at[:10],
        "combined_source_hash": combined_hash.hexdigest(),
        "models": models,
        "status": "candidate",
    }
    validate_snapshot(candidate)
    return candidate


def validate_snapshot(snapshot: Dict[str, Any]) -> None:
    if snapshot.get("provider") != "OpenAI":
        raise PricingSyncError("snapshot provider must be OpenAI")
    models = snapshot.get("models")
    if not isinstance(models, dict) or set(models) != set(MODEL_SPECS):
        raise PricingSyncError("snapshot must contain every supported OpenAI model and no extras")
    for model_id, record in models.items():
        for key in (
            "input_price_per_1m",
            "cached_input_price_per_1m",
            "output_price_per_1m",
            "guard_input_price_per_1m",
            "guard_output_price_per_1m",
        ):
            value = record.get(key)
            if not isinstance(value, (int, float)) or value <= 0:
                raise PricingSyncError(f"{model_id}: invalid {key}")
        if record["cached_input_price_per_1m"] > record["input_price_per_1m"]:
            raise PricingSyncError(f"{model_id}: cached input exceeds ordinary input")
        if record["guard_input_price_per_1m"] < record["input_price_per_1m"]:
            raise PricingSyncError(f"{model_id}: input guard is not conservative")
        if record["guard_output_price_per_1m"] < record["output_price_per_1m"]:
            raise PricingSyncError(f"{model_id}: output guard is not conservative")
        if not record.get("source_hash") or not record.get("source_url"):
            raise PricingSyncError(f"{model_id}: missing source provenance")


def _load_json(path: Path) -> Dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return None


def _rate_changes(previous: Dict[str, Any] | None, candidate: Dict[str, Any]) -> list[dict]:
    if not previous:
        return [{"model": "*", "field": "snapshot", "old": None, "new": "initial_verified"}]
    changes = []
    keys = (
        "input_price_per_1m",
        "cached_input_price_per_1m",
        "cache_write_price_per_1m",
        "output_price_per_1m",
        "guard_input_price_per_1m",
        "guard_output_price_per_1m",
        "pricing_rules",
    )
    for model_id, new in candidate["models"].items():
        old = previous.get("models", {}).get(model_id, {})
        for key in keys:
            if old.get(key) != new.get(key):
                changes.append({"model": model_id, "field": key, "old": old.get(key), "new": new.get(key)})
    return changes


def _suspicious_rate_jump(previous: Dict[str, Any] | None, candidate: Dict[str, Any]) -> str | None:
    if not previous:
        return None
    rate_keys = (
        "input_price_per_1m",
        "cached_input_price_per_1m",
        "output_price_per_1m",
    )
    for model_id, new in candidate["models"].items():
        old = previous.get("models", {}).get(model_id, {})
        for key in rate_keys:
            a, b = old.get(key), new.get(key)
            if not isinstance(a, (int, float)) or not isinstance(b, (int, float)) or a <= 0:
                continue
            factor = max(b / a, a / b)
            if factor > MAX_AUTOPROMOTE_RATE_FACTOR:
                return f"{model_id} {key} changed by {factor:.2f}x"
    return None


def _archive_previous(previous: Dict[str, Any] | None) -> None:
    if not previous:
        return
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    stamp = previous.get("source_checked_at", "unknown").replace(":", "").replace("-", "")
    target = HISTORY_DIR / f"openai-{stamp}.json"
    if not target.exists():
        _atomic_json(target, previous)


def sync_openai_pricing(
    fetcher: Callable[[str], str] = _fetch_text,
    *,
    auto_promote: bool = True,
) -> Dict[str, Any]:
    """Check official OpenAI sources and promote only a complete validated candidate."""
    with _SYNC_LOCK:
        previous = _load_json(VERIFIED_PATH)
        try:
            candidate = build_candidate(fetcher)
        except Exception as exc:
            status = {
                "provider": "OpenAI",
                "checked_at": _utcnow(),
                "result": "failed",
                "message": str(exc),
                "verified_snapshot_preserved": bool(previous),
            }
            _atomic_json(STATUS_PATH, status)
            return status

        changes = _rate_changes(previous, candidate)
        suspicious = _suspicious_rate_jump(previous, candidate)
        candidate["changes"] = changes
        candidate["status"] = "quarantined" if suspicious else "validated"
        if suspicious:
            candidate["quarantine_reason"] = suspicious

        _atomic_json(CANDIDATE_PATH, candidate)

        if suspicious or not auto_promote:
            status = {
                "provider": "OpenAI",
                "checked_at": candidate["source_checked_at"],
                "result": "candidate_only",
                "message": suspicious or "candidate validated; auto-promotion disabled",
                "changes": changes,
            }
            _atomic_json(STATUS_PATH, status)
            return status

        source_changed = bool(
            previous
            and previous.get("combined_source_hash")
            and previous.get("combined_source_hash") != candidate.get("combined_source_hash")
        )

        if previous and not changes and source_changed:
            candidate["status"] = "review_required"
            candidate["review_reason"] = (
                "Official source content changed, but the parser detected no supported "
                "pricing/rule change. Review before accepting the new source revision."
            )
            _atomic_json(CANDIDATE_PATH, candidate)
            status = {
                "provider": "OpenAI",
                "checked_at": candidate["source_checked_at"],
                "result": "candidate_only",
                "message": candidate["review_reason"],
                "changes": [],
            }
            _atomic_json(STATUS_PATH, status)
            return status

        if previous and not changes:
            refreshed = dict(candidate)
            refreshed["status"] = "verified"
            refreshed["promoted_at"] = previous.get("promoted_at")
            _atomic_json(VERIFIED_PATH, refreshed)
            try:
                from pricing_engine import clear_catalog_cache
                clear_catalog_cache()
            except Exception:
                pass
            status = {
                "provider": "OpenAI",
                "checked_at": candidate["source_checked_at"],
                "result": "no_change",
                "message": "Official OpenAI sources parsed and validated; verified rates unchanged.",
                "changes": [],
            }
            _atomic_json(STATUS_PATH, status)
            return status

        _archive_previous(previous)
        promoted = dict(candidate)
        promoted["status"] = "verified"
        promoted["promoted_at"] = _utcnow()
        _atomic_json(VERIFIED_PATH, promoted)

        try:
            from pricing_engine import clear_catalog_cache
            clear_catalog_cache()
        except Exception:
            pass

        status = {
            "provider": "OpenAI",
            "checked_at": candidate["source_checked_at"],
            "result": "promoted",
            "message": "Validated OpenAI pricing snapshot promoted to runtime authority.",
            "changes": changes,
        }
        _atomic_json(STATUS_PATH, status)
        return status


def check_due_today() -> bool:
    status = _load_json(STATUS_PATH) or {}
    if status.get("result") == "failed":
        return True
    checked = str(status.get("checked_at", ""))[:10]
    return checked != datetime.now(timezone.utc).date().isoformat()


def _daily_loop() -> None:
    while True:
        if check_due_today():
            sync_openai_pricing()
        time.sleep(3600)


def start_daily_openai_sync() -> None:
    global _SYNC_THREAD
    if _SYNC_THREAD and _SYNC_THREAD.is_alive():
        return
    if check_due_today():
        threading.Thread(target=sync_openai_pricing, daemon=True).start()
    _SYNC_THREAD = threading.Thread(target=_daily_loop, daemon=True)
    _SYNC_THREAD.start()


if __name__ == "__main__":
    print(json.dumps(sync_openai_pricing(), indent=2))
