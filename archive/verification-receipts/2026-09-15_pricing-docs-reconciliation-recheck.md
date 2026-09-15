# TokenTotals Pricing Documentation Reconciliation Recheck Receipt

Date: 2026-09-15

## Scope

This receipt closes the public-document/runtime pricing reconciliation item.

The concern was not merely old model names. The public documentation had begun to diverge from the runtime architecture by maintaining a second hand-written pricing snapshot and simplified architectural claims alongside the provider-specific registries/calculators that now drive TokenTotals.

## Diagnosis

The review found three related mismatches in current public documentation:

1. `MODEL_COMPARISON_MATRIX.md` was labeled with a 2026-09-15 snapshot date while still presenting older hand-picked Claude and Gemini model/rate rows. That created a provenance conflict with the current provider registries.
2. `README.md` repeated the stale comparison table and showed an apparently live telemetry badge containing hard-coded pricing/sync values, even though runtime pricing now comes from provider-specific registries and observed request/response telemetry.
3. `TokenTotals_Security_Whitepaper.md` still described preflight as a single BPE-token count multiplied by a generic "local real-time pricing matrix" and used "zero-egress" language that could be read as no network egress at all. In reality, TokenTotals' control plane is local, but permitted requests necessarily egress to the selected upstream AI provider.

These were documentation/source-of-truth problems. The runtime provider engines were not changed in this item.

## Decision

The documentation was reconciled around **pricing mechanics and provenance**, not another duplicated model-price database.

The repo-contained machine-readable sources for dedicated first-party pricing rules are:

- `pricing/openai_registry.json`
- `pricing/anthropic_registry.json`
- `pricing/google_registry.json`

Current public documentation now points to those registries and describes their relationship to observed telemetry, provider-specific calculators, incomplete-estimate behavior, and the pinned exact-model LiteLLM secondary fallback used only outside the three dedicated provider families.

## Implementation commits

- `32aa8dbd5f3c313a506f339d8d5aaaf6d687bd82` — replaced the stale human price leaderboard with `MODEL_COMPARISON_MATRIX.md` as a provider pricing-mechanics/provenance matrix.
- `073c9f20c445106cdc590fc6bc99005667cb46cc` — reconciled README pricing architecture, removed the duplicated static price table and hard-coded live-looking telemetry pricing sample, clarified explicit-model behavior and estimate boundaries.
- `d015151a172c5d75860e8183110c955768d70973` — reconciled the security whitepaper with provider-specific preflight/post-response accounting and the actual network boundary: local TokenTotals control plane, upstream provider egress still exists.
- `d0f4cc2649386b2b94751a069c9d1173d7fe43d1` — added documentation provenance/boundary regressions.

## Documentation invariants now enforced

The new regression file `tests/test_pricing_docs_reconciliation.py` enforces that:

1. the human comparison is a mechanics matrix rather than a stale rate leaderboard;
2. README, mechanics matrix, and whitepaper all reference the three provider registry paths;
3. README does not present the removed standardized static model/rate comparison or hard-coded public-sync values as runtime truth;
4. the whitepaper no longer documents one universal real-time pricing matrix/BPE formula as the actual preflight architecture;
5. the whitepaper explicitly states that upstream provider egress still exists and distinguishes that from the absence of a TokenTotals-operated secondary telemetry SaaS.

Historical receipts under `archive/verification-receipts/` were not rewritten. They remain evidence of earlier repository states.

## Clean-machine evidence

GitHub Actions run: `35023944730`
Job: `104566286609`
Commit: `d0f4cc2649386b2b94751a069c9d1173d7fe43d1`
Result: **SUCCESS**

Clean runner stages:

- dependency install: success
- Python compile: success
- live `proxy_server` import: success
- regression suite: **90/90 passed**

Documentation-specific tests passing:

- `test_current_pricing_docs_all_reference_the_three_registries`
- `test_mechanics_matrix_does_not_duplicate_stale_price_leaderboard`
- `test_readme_does_not_present_static_rates_as_live_runtime_truth`
- `test_whitepaper_describes_provider_specific_preflight_not_one_rate_matrix`
- `test_whitepaper_states_real_network_boundary`

Existing OpenAI, Anthropic, Google/Gemini, legacy-removal, safe-preflight-fallback, runtime-model-catalog, optimizer-retirement, and proxy-integration regressions also remained green.

## Result

**COMPLETE for this documentation item.**

Current public pricing documentation now describes the architecture actually implemented: provider-specific versioned rules plus observable telemetry, disclosed fallbacks, explicit uncertainty, and no invoice-exact claim. It no longer maintains a competing current-rate leaderboard under the same date as the provider registries.

## Explicitly not claimed

This receipt does not claim that registry rates will remain current indefinitely. Each registry records its own verification date and provider sources. Pricing changes require re-verification and a new evidence trail.

It also does not claim that local loopback operation eliminates upstream provider network traffic. Permitted requests still reach the explicitly selected AI provider.
