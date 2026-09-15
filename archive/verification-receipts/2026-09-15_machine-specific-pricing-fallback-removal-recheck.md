# TokenTotals Machine-Specific Pricing Fallback — Removal & Recheck Receipt

**Receipt date:** 2026-09-15  
**Repository:** `QuietFireAI/tokentotals`  
**Branch:** `main`

## Status

**REMOVED AND REGRESSION-TESTED.**

This receipt records the removal of the machine-specific pricing plugin path and its hard-coded universal fallback. It preserves both the defect and the replacement behavior. It is not a claim that every provider is now modeled by a first-party TokenTotals pricing engine.

## Defect found

`proxy_server.py` previously inserted this local Windows-only path into `sys.path`:

`C:\Users\Command Center\.gemini\config\plugins\token-cost-estimator\scripts`

It then attempted to import an external `pricing_engine` and `token_estimator` from that machine-specific location.

When that import failed, the proxy supplied hard-coded generic rates:

- input: `$2.50 / 1M tokens`
- output: `$10.00 / 1M tokens`

The fallback input calculation was subsequently used in preflight paths when a dedicated provider engine could not resolve a model or billing condition, and for models outside the dedicated OpenAI/Anthropic/Google families.

That behavior was unsafe for a budget circuit breaker because an unknown or newly introduced model could be assigned a plausible-looking but unrelated price. A provider-specific engine failure could also be masked by the generic rate instead of remaining visibly unresolved.

## Repair

The machine-specific path, external `pricing_engine` import, external `token_estimator` import, and hard-coded `$2.50/$10.00` rate fallback were removed from `proxy_server.py`.

Primary repair commit:

`f0d7703bff2c75443a32adf2864226c508d85ea9`

## Replacement preflight hierarchy

The preflight path now follows these rules:

1. **OpenAI-family model:** use the repo-contained OpenAI provider engine/registry. If that provider engine cannot resolve the model/tier, the model remains unresolved; it does not escape into generic middleware pricing.
2. **Anthropic-family model:** use the repo-contained Anthropic provider engine/registry. If unresolved, do not substitute a universal or LiteLLM rate.
3. **Google/Gemini-family model:** use the repo-contained Google provider engine/registry. If unresolved, do not substitute a universal or LiteLLM rate.
4. **Other provider/model family:** TokenTotals may use the **exact model key** from the pinned LiteLLM `model_cost` catalog as an explicitly secondary preflight estimate if that exact record exposes a valid `input_cost_per_token`.
5. **No defensible exact price:** preflight returns unpriced and the request is rejected before it is sent upstream.

The pinned LiteLLM catalog fallback is intentionally narrow. It is a third-party secondary estimate for provider families that do not yet have a TokenTotals provider-specific engine; it is not described as provider truth or invoice-exact pricing.

## No fuzzy model guessing

The fallback lookup uses an exact model key only.

TokenTotals does not strip a provider prefix, select a nearby model, apply a family default, or substitute a generic rate in this fallback path.

If the exact pinned LiteLLM record does not exist or lacks a valid input rate, the preflight remains unresolved.

## Fail-closed behavior

An unpriced request now receives HTTP `422` with a `TokenTotals Pricing Unavailable` error before any upstream model call is made.

This is deliberate. For a cost guardrail, knowingly allowing a request through with a fabricated preflight price is worse than refusing an unsupported model until its pricing basis can be represented defensibly.

## Token-count estimation boundary

Preflight token volume is still an estimate because the provider has not processed the request yet.

TokenTotals now first attempts the pinned LiteLLM tokenizer for the requested model. If that tokenizer cannot be used, it falls back to a local character-length heuristic.

That fallback estimates token volume only. It is explicitly **not** treated as a provider billing counter or post-response usage source.

Actual spend accounting continues to prefer observed response telemetry after the call completes.

## Economy-routing safety change

The existing routine-task/economy heuristic was not redesigned in this item.

However, it can no longer auto-route to an economy target that TokenTotals cannot preflight-price. If the configured/legacy economy target is unpriced:

- no potential-savings amount is fabricated for that target
- auto-economy does not switch the request to that target
- a warning is logged

This prevents stale optimizer model IDs from bypassing the pricing guardrail while leaving model-selection redesign for its own separately diagnosed item.

## Post-response behavior

This change does not remove the existing post-response fallback hierarchy.

For the three provider-specific engines, TokenTotals still attempts the repo-contained provider calculator first. When a provider calculation is incomplete, the pinned LiteLLM `response_cost` may be used when available. Anthropic and Google can additionally expose a known public-list-equivalent fallback when supported by their partial telemetry so that an incomplete measurement does not silently become `$0`.

For providers without a dedicated TokenTotals engine, LiteLLM remains the available post-response cost source.

That secondary dependency is disclosed rather than represented as provider-authoritative billing.

## Regression protection

Added:

`tests/test_preflight_pricing_fallback.py`

Test commit:

`7eaaa113430c660fe397c22060e524ce3b1a9049`

The regression suite verifies that:

- the old `Command Center` machine path is absent
- `pricing_engine` is no longer imported
- `legacy_input_estimate` is absent
- the hard-coded `$2.50/M` input-rate fallback is absent
- the LiteLLM catalog fallback requires an exact model key
- a provider outside the dedicated families can use an exact pinned LiteLLM catalog rate as a secondary estimate
- a model belonging to a dedicated provider family cannot fall through to LiteLLM when the local provider registry cannot resolve it
- negative or missing middleware rates are rejected
- a truly unpriced model is blocked by the live FastAPI route before any upstream call

## CI evidence

GitHub Actions verification:

- **Run:** `35020766156`
- **Job:** `104555549216`
- **Head commit:** `7eaaa113430c660fe397c22060e524ce3b1a9049`
- **Runner:** Ubuntu 24.04
- **Python:** 3.12.14
- **Middleware:** `litellm==1.101.0`
- clean dependency installation: PASS
- Python compile: PASS
- real `proxy_server` smoke import: PASS
- full regression suite: **74 tests run, 74 passed**

The CI log explicitly passed:

- `test_machine_specific_pricing_plugin_is_removed`
- `test_litellm_catalog_fallback_requires_exact_model_key`
- `test_unknown_provider_can_use_pinned_catalog_as_secondary_estimate`
- `test_dedicated_provider_failure_does_not_fall_through_to_litellm`
- `test_negative_or_missing_catalog_rate_is_not_used`
- `test_unpriced_model_is_blocked_before_upstream_call`

Existing OpenAI, Anthropic, Google/Gemini, provider-integration, and legacy-sync-removal regressions also remained green.

## Interpretation

TokenTotals no longer depends on a developer-machine filesystem path for pricing and no longer substitutes a universal hard-coded price when pricing is unknown.

The architecture is now materially clearer:

- provider-specific engines for OpenAI, Anthropic, and Google/Gemini
- pinned LiteLLM as a disclosed secondary fallback where appropriate
- explicit refusal when preflight cannot obtain a defensible model price

This remains an estimation system, not a billing mirror. Provider pricing, telemetry, account terms, tools, processing modes, discounts, taxes, and middleware behavior can still change independently.

## Next unresolved pricing/runtime item

The provider-pricing plumbing is now substantially cleaned up, but `proxy_server.py` still contains stale hard-coded model discovery and optimizer/routing assumptions, including old `/v1/models` entries, premium-model heuristics, and economy-model targets.

Those must be diagnosed separately so model discovery and optimization are derived from the current versioned provider registries rather than from stale hard-coded names.
