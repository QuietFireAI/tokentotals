# TokenTotals Legacy Pricing Sync — Removal & Recheck Receipt

**Receipt date:** 2026-09-15  
**Repository:** `QuietFireAI/tokentotals`  
**Branch:** `main`

## Status

**REMOVED AND REGRESSION-TESTED.**

This receipt records the removal of the old daily third-party pricing synchronization path. It is historical evidence of what was found and changed; it does not rewrite the earlier audit receipts that documented the previous behavior.

## Diagnosis

The removed `pricing_sync.py` module downloaded LiteLLM's public `model_prices_and_context_window.json` catalog from GitHub, cached it locally as `model_prices.json`, and stored a `last_pricing_sync` timestamp.

The desktop GUI imported that module and automatically started its daily synchronization daemon during application startup.

Repository search found no runtime consumer of `get_pricing_catalog()`. The OpenAI, Anthropic, and Google/Gemini pricing engines use their repo-contained provider registries instead. The downloaded catalog therefore did not power the current pricing calculation path.

The practical effect of the old code was an automatic outbound network request and a locally cached third-party catalog that could create the impression of a live pricing source without supplying the active provider calculators.

## Repair

### GUI startup hook removed

`app_gui.py` no longer imports `pricing_sync` and no longer calls `pricing_sync.start_daily_sync_daemon()`.

Commit:

`1c102cf7d67fff8edfa5642a5cae663d787d625d`

### Dead synchronization module removed

`pricing_sync.py` was deleted from the repository.

Commit:

`28976559e96472acbaee7ab8ec4e180d82f1ba9b`

The historical receipts that describe the old synchronization path remain intact as evidence.

## Regression protection

Added:

`tests/test_no_legacy_pricing_sync.py`

The regression suite verifies that:

- `pricing_sync.py` does not exist
- `app_gui.py` does not import `pricing_sync`
- `app_gui.py` does not start the old synchronization daemon
- the runtime pricing files do not reference LiteLLM's remote `model_prices_and_context_window.json` catalog

Regression commit:

`d438975152489c1d64b62c6a17efd98b1532cfe2`

## CI evidence

GitHub Actions verification:

- **Run:** `35020196685`
- **Job:** `104553676689`
- **Head commit:** `d438975152489c1d64b62c6a17efd98b1532cfe2`
- clean dependency installation: PASS
- Python compile: PASS
- real `proxy_server` smoke import: PASS
- full regression suite: **68 tests run, 68 passed**

The CI log explicitly passed:

- `test_pricing_sync_module_is_removed`
- `test_gui_does_not_start_pricing_sync`
- `test_no_runtime_file_references_litellm_remote_catalog`

The existing OpenAI, Anthropic, Google/Gemini, and provider-integration suites also remained green.

## Interpretation

This change does not reduce the active provider-specific pricing capability because the removed catalog was not consumed by the active calculators.

It removes an unused automatic third-party pricing download and makes the architecture more consistent with TokenTotals' stated model: versioned provider-specific pricing references plus observed telemetry, with explicit fallbacks rather than an implied universal live catalog.

This receipt does **not** claim that TokenTotals performs no network traffic. Its purpose is narrower: the automatic daily LiteLLM pricing-catalog fetch has been removed.

## Next unresolved legacy pricing item

`proxy_server.py` still contains a machine-specific filesystem path for an external `pricing_engine` / `token_estimator` plugin and hard-coded fallback behavior when that import is unavailable.

That path must be diagnosed separately before removal so unknown-provider and preflight failure behavior is not changed blindly.
