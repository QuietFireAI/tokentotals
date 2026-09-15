"""Fail closed when TokenTotals' last verified pricing receipt is older than 24 hours."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "pricing_catalog.json"
MAX_AGE = timedelta(hours=24)


def _parse_utc_timestamp(value: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError("pricing freshness receipt has no source_checked_at timestamp")
    normalized = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise RuntimeError(f"invalid pricing freshness timestamp: {value!r}") from exc
    if parsed.tzinfo is None:
        raise RuntimeError("pricing freshness timestamp must include a timezone")
    return parsed.astimezone(timezone.utc)


def check_freshness(catalog: dict, *, now: datetime | None = None) -> dict:
    receipt = catalog.get("daily_integrity_refresh") or {}
    if receipt.get("status") != "verified":
        raise RuntimeError("pricing freshness receipt is not VERIFIED")

    providers = receipt.get("providers") or {}
    required = {"OpenAI", "Anthropic", "Google"}
    missing = sorted(required - set(providers))
    if missing:
        raise RuntimeError(f"pricing freshness receipt is missing providers: {missing}")
    not_verified = sorted(
        provider for provider in required if providers[provider].get("status") != "verified"
    )
    if not_verified:
        raise RuntimeError(f"pricing providers are not verified: {not_verified}")

    checked_at = _parse_utc_timestamp(receipt.get("source_checked_at"))
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    age = current - checked_at
    if age < timedelta(0):
        raise RuntimeError(
            f"pricing freshness receipt is future-dated by {-age}; refusing invalid freshness proof"
        )
    if age > MAX_AGE:
        raise RuntimeError(
            f"STALE PRICING RECEIPT: last verified source check is {age} old; maximum allowed age is {MAX_AGE}"
        )

    return {
        "status": "CURRENT",
        "source_checked_at": checked_at.isoformat().replace("+00:00", "Z"),
        "age_seconds": int(age.total_seconds()),
        "max_age_seconds": int(MAX_AGE.total_seconds()),
        "providers": sorted(required),
    }


def main() -> int:
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    result = check_freshness(catalog)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
