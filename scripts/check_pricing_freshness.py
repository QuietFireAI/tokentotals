"""Validate the last successfully published TokenTotals daily pricing receipt.

This checker is a watchdog, not a refresh trigger. The scheduled daily integrity workflow
performs the provider verification, regeneration, tests, and atomic publish. This module
only proves that the last published VERIFIED receipt is still within the 24-hour freshness
window and includes all required provider verification statuses.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "pricing_catalog.json"
MAX_AGE = timedelta(hours=24)


def _parse_utc_timestamp(value: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError("daily pricing refresh receipt has no source_checked_at timestamp")
    normalized = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise RuntimeError(f"invalid daily pricing refresh timestamp: {value!r}") from exc
    if parsed.tzinfo is None:
        raise RuntimeError("daily pricing refresh timestamp must include a timezone")
    return parsed.astimezone(timezone.utc)


def check_freshness(catalog: dict, *, now: datetime | None = None) -> dict:
    """Prove that the most recently published daily refresh receipt is still current."""
    receipt = catalog.get("daily_integrity_refresh") or {}
    if receipt.get("status") != "verified":
        raise RuntimeError("daily pricing refresh receipt is not VERIFIED")

    providers = receipt.get("providers") or {}
    required = {"OpenAI", "Anthropic", "Google"}
    missing = sorted(required - set(providers))
    if missing:
        raise RuntimeError(f"daily pricing refresh receipt is missing providers: {missing}")
    not_verified = sorted(
        provider for provider in required if providers[provider].get("status") != "verified"
    )
    if not_verified:
        raise RuntimeError(f"daily pricing refresh providers are not verified: {not_verified}")

    checked_at = _parse_utc_timestamp(receipt.get("source_checked_at"))
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    age = current - checked_at
    if age < timedelta(0):
        raise RuntimeError(
            f"daily pricing refresh receipt is future-dated by {-age}; refusing invalid completion proof"
        )
    if age > MAX_AGE:
        raise RuntimeError(
            f"STALE DAILY PRICING REFRESH: last successfully published verified receipt is {age} old; "
            f"maximum allowed age is {MAX_AGE}"
        )

    return {
        "status": "DAILY_REFRESH_CURRENT",
        "source_checked_at": checked_at.isoformat().replace("+00:00", "Z"),
        "age_seconds": int(age.total_seconds()),
        "max_age_seconds": int(MAX_AGE.total_seconds()),
        "providers": sorted(required),
        "role": "validator/watchdog for the last successfully published daily refresh",
    }


def main() -> int:
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    result = check_freshness(catalog)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
