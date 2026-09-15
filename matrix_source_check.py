"""Non-destructive live-source validation for dated matrix pricing providers.

IR-005 guardrail: the committed matrix is generated from pricing_catalog.json, but
Anthropic and Google do not yet have promoted dynamic runtime adapters. This module
checks their dated catalog base rates against the official provider pricing pages.
It never writes or promotes pricing data.
"""
from __future__ import annotations

import hashlib
import html
import json
import re
import urllib.request
from datetime import date, datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parent
CATALOG_PATH = ROOT / "pricing_catalog.json"

SOURCE_URLS = {
    "Anthropic": "https://platform.claude.com/docs/en/about-claude/pricing",
    "Google": "https://cloud.google.com/gemini-enterprise-agent-platform/generative-ai/pricing",
}

DISPLAY_NAMES = {
    "claude-fable-5.1": "Claude Fable 5.1",
    "claude-opus-5": "Claude Opus 5",
    "claude-sonnet-5": "Claude Sonnet 5",
    "claude-haiku-4.5": "Claude Haiku 4.5",
    "gemini-3.1-pro-preview": "Gemini 3.1 Pro Preview",
    "gemini-3.8-flash": "Gemini 3.8 Flash",
    "gemini-3.7-flash": "Gemini 3.7 Flash",
    "gemini-3.6-flash": "Gemini 3.6 Flash",
    "gemini-3.5-flash": "Gemini 3.5 Flash",
    "gemini-3.5-flash-lite": "Gemini 3.5 Flash-Lite",
    "gemini-3.1-flash-lite": "Gemini 3.1 Flash-Lite",
}


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        value = " ".join(data.split())
        if value:
            self.parts.append(value)


def visible_text(document: str) -> str:
    """Return stable visible-ish text from provider HTML/markdown responses."""
    if "<html" not in document.lower() and "<body" not in document.lower():
        return "\n".join(line.strip() for line in document.splitlines() if line.strip())
    parser = _TextExtractor()
    parser.feed(document)
    return "\n".join(parser.parts)


def fetch_source(url: str, timeout: int = 30) -> tuple[str, str]:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "TokenTotals/IR-005-source-validator (+https://github.com/QuietFireAI/tokentotals)",
            "Accept": "text/html,text/plain;q=0.9,*/*;q=0.8",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read()
    digest = hashlib.sha256(raw).hexdigest()
    return raw.decode("utf-8", errors="replace"), digest


def pricing_scope(provider: str, text: str) -> str:
    """Discard navigation/promo text before the provider's base pricing table.

    Both official pages mention model names outside the price table. Anchoring first
    prevents navigation text or marketing banners from being mistaken for a rate row.
    """
    if provider == "Anthropic":
        anchor = text.find("Model pricing")
        if anchor < 0:
            raise ValueError("Anthropic pricing source did not expose the expected Model pricing section")
        return text[anchor:]

    if provider == "Google":
        google_models = text.find("Google models")
        if google_models < 0:
            raise ValueError("Google pricing source did not expose the expected Google models section")
        standard = text.find("Standard", google_models)
        if standard < 0:
            raise ValueError("Google pricing source did not expose the expected Standard pricing section")
        return text[standard:]

    raise ValueError(f"Unsupported live matrix provider: {provider}")


def _next_label_position(text: str, start: int, labels: Iterable[str]) -> int | None:
    positions = [pos for label in labels if (pos := text.find(label, start)) >= 0]
    return min(positions) if positions else None


def model_window(text: str, label: str, provider_labels: Iterable[str]) -> str:
    """Return a model's first base/standard pricing-table occurrence.

    The input text must already be scoped to the provider's base/standard pricing
    section. Later Priority/Flex/Batch tables therefore cannot satisfy this check.
    """
    start = text.find(label)
    if start < 0:
        raise ValueError(f"Model label not found in live source: {label}")
    search_from = start + len(label)
    end = _next_label_position(text, search_from, [x for x in provider_labels if x != label])
    if end is None or end - start > 5000:
        end = min(len(text), start + 5000)
    return text[start:end]


def dollar_values(window: str) -> list[float]:
    return [float(value) for value in re.findall(r"\$\s*([0-9]+(?:\.[0-9]+)?)", html.unescape(window))]


def _contains_rate(values: Iterable[float], expected: float) -> bool:
    return any(abs(value - expected) < 1e-9 for value in values)


def _check_effective_window(model_id: str, record: dict, today: date) -> None:
    effective_from = record.get("effective_from")
    effective_until = record.get("effective_until")
    if effective_from and today < date.fromisoformat(str(effective_from)):
        raise ValueError(
            f"{model_id}: catalog rate is not effective until {effective_from}; today is {today.isoformat()}"
        )
    if effective_until and today > date.fromisoformat(str(effective_until)):
        raise ValueError(
            f"{model_id}: catalog rate expired on {effective_until}; today is {today.isoformat()}"
        )


def validate_provider_text(
    provider: str,
    text: str,
    catalog: dict,
    *,
    today: date | None = None,
) -> list[dict]:
    today = today or datetime.now(timezone.utc).date()
    text = pricing_scope(provider, text)
    models = catalog.get("models", {})
    provider_models = [
        (model_id, record)
        for model_id, record in models.items()
        if record.get("provider") == provider
    ]
    if not provider_models:
        raise ValueError(f"No {provider} models are represented in the catalog")

    labels = [DISPLAY_NAMES[model_id] for model_id, _ in provider_models]
    results: list[dict] = []
    for model_id, record in provider_models:
        _check_effective_window(model_id, record, today)
        label = DISPLAY_NAMES.get(model_id)
        if not label:
            raise ValueError(f"No official display-name mapping for {model_id}")
        window = model_window(text, label, labels)
        values = dollar_values(window)
        input_rate = float(record["input_price_per_1m"])
        output_rate = float(record["output_price_per_1m"])
        if not _contains_rate(values, input_rate):
            raise ValueError(
                f"{provider} {model_id}: catalog input ${input_rate:g}/1M was not found "
                "in the model's live base/standard pricing row"
            )
        if not _contains_rate(values, output_rate):
            raise ValueError(
                f"{provider} {model_id}: catalog output ${output_rate:g}/1M was not found "
                "in the model's live base/standard pricing row"
            )
        results.append(
            {
                "model": model_id,
                "input_price_per_1m": input_rate,
                "output_price_per_1m": output_rate,
                "effective_from": record.get("effective_from"),
                "effective_until": record.get("effective_until"),
            }
        )
    return results


def validate_live_sources() -> dict:
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    audit: dict = {"catalog_verified_at": catalog.get("verified_at"), "providers": {}}
    for provider, url in SOURCE_URLS.items():
        document, digest = fetch_source(url)
        text = visible_text(document)
        records = validate_provider_text(provider, text, catalog)
        audit["providers"][provider] = {
            "source": url,
            "source_sha256": digest,
            "models": records,
        }
    return audit


def main() -> int:
    audit = validate_live_sources()
    print(json.dumps(audit, indent=2, sort_keys=True))
    print("IR-005 live matrix source validation passed; no pricing files were modified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
