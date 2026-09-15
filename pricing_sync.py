"""Provider pricing synchronization entry point.

OpenAI is the first live official-source implementation. Anthropic and Google remain on
the checked-in verified catalog until equivalent provider adapters are implemented and
tested. No third-party registry overwrites production pricing.
"""
from datetime import date, datetime

from openai_pricing_sync import start_daily_openai_sync, sync_openai_pricing
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
    return True, f"checked-in catalog verified {verified_at} ({age_days} days old)"


def get_pricing_catalog():
    return load_catalog()


def fetch_live_pricing():
    """Run the official OpenAI source check; never overwrite from a third party."""
    return sync_openai_pricing()


def start_daily_sync_daemon():
    """Start the OpenAI official-source daily checker."""
    start_daily_openai_sync()
    return True


if __name__ == "__main__":
    print(fetch_live_pricing())
