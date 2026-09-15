from anthropic_pricing import load_registry as load_anthropic_registry
from google_pricing import load_registry as load_google_registry
from openai_pricing import load_registry as load_openai_registry


_PROVIDER_LOADERS = (
    ("openai", load_openai_registry),
    ("anthropic", load_anthropic_registry),
    ("google", load_google_registry),
)


def registered_model_entries():
    """Return canonical model IDs recognized by TokenTotals provider registries.

    This is a pricing-recognition catalog, not a promise that a user's provider
    account is entitled to invoke every listed model.
    """
    entries = []
    seen = set()

    for provider, loader in _PROVIDER_LOADERS:
        registry = loader()
        verified_at = registry.get("verified_at")
        for model_id, record in (registry.get("models") or {}).items():
            if model_id in seen:
                continue
            seen.add(model_id)
            entries.append(
                {
                    "id": model_id,
                    "object": "model",
                    "owned_by": provider,
                    "tokentotals_pricing_registry": True,
                    "tokentotals_verified_at": verified_at,
                    "tokentotals_limited_availability": bool(
                        isinstance(record, dict) and record.get("limited_availability", False)
                    ),
                }
            )

    return sorted(entries, key=lambda item: (item["owned_by"], item["id"]))


def registered_model_ids():
    return [entry["id"] for entry in registered_model_entries()]
