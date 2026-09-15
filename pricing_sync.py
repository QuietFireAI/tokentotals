"""Pricing catalog validation helpers.

Previous versions downloaded LiteLLM's community registry and called that an official
provider sync. TokenTotals now treats the checked-in, dated provider-receipt catalog as
the runtime authority. This module keeps the old public function names for compatibility
without silently replacing verified prices from a third-party registry.
"""
from datetime import date, datetime

from pricing_engine import load_catalog


def validate_pricing_catalog():
    catalog = load_catalog()
    verified_at = catalog.get("verified_at")
    if not verified_at:
        return False, "pricing catalog has no verified_at date"
    try:
        verified_date = datetime.strptime(verified_at, "%Y-%m-%d").date()
    except ValueError:
        return False, "pricing catalog verified_at is not YYYY-MM-DD"
    age_days = (date.today() - verified_date).days
    return True, f"verified {verified_at} ({age_days} days old)"


def get_pricing_catalog():
    return load_catalog()


def fetch_live_pricing():
    """Compatibility shim: no third-party runtime overwrite is performed."""
    ok, message = validate_pricing_catalog()
    print(f"[TokenTotals Pricing] {message}. Runtime catalog was not overwritten.")
    return ok


def start_daily_sync_daemon():
    """Compatibility shim retained for app_gui.py; validation is local and immediate."""
    return fetch_live_pricing()


if __name__ == "__main__":
    fetch_live_pricing()
