# TokenTotals Runtime Model Catalog Recheck Receipt

Date: 2026-09-15

## Scope

This receipt closes the runtime model-discovery/request-correctness item only. It does **not** validate or redesign the separate auto-economy/optimizer routing logic.

The intended invariants for this item were:

1. `/v1/models` is derived from the repo-contained provider pricing registries rather than a stale hand-written four-model list.
2. The endpoint advertises canonical registry model IDs only; pricing aliases do not become duplicate catalog entries.
3. Catalog metadata identifies pricing-recognition scope and provider provenance; it is not represented as provider-account entitlement.
4. `/v1/chat/completions` requires an explicit non-empty `model` value and does not silently default to `gpt-4o` or another model.
5. Missing/blank model requests are rejected before any upstream LiteLLM completion call can occur.

## Implementation commits

- `2dca1fdaf49a05a740ee9e53c86012768170b6db` — added `runtime_model_catalog.py`, deriving canonical model entries from the OpenAI, Anthropic, and Google registries.
- `b9bcdc9d03647983439db5dd65875afd70ef443c` — wired `/v1/models` to the registry-derived catalog and removed the silent `gpt-4o` request default.
- `97f7d0fc526b2842d44e05e3e7669e091e81a229` — added six runtime catalog / explicit-model regression tests.
- `10c18358f628d7d09fb95f31a7d06bab889bb993` — corrected test isolation after the first clean-machine run exposed interaction with an earlier intentional LiteLLM test stub.

## Catalog reconciliation

At this recheck, the three provider registries expose 31 canonical pricing-recognized model IDs:

- OpenAI: 8 canonical IDs
- Anthropic: 13 canonical IDs
- Google/Gemini: 10 canonical IDs

`runtime_model_catalog.registered_model_entries()` returns those canonical registry keys with provider, registry-verification date, and limited-availability metadata. Aliases remain pricing-resolution inputs and are not separately advertised as canonical models.

This catalog means **TokenTotals has repo-contained pricing recognition for the listed IDs**. It does not mean a user's provider account is entitled to invoke every listed model, nor does it promise availability in every provider region/account/tier.

## Evidence — initial test run (failure preserved)

GitHub Actions run: `35022252462`
Commit: `97f7d0fc526b2842d44e05e3e7669e091e81a229`
Result: **FAILED — 80 tests executed, 2 errors**

The two errors were in the new missing/blank-model tests. An earlier regression test intentionally replaces the imported `litellm` module with a `types.SimpleNamespace` test stub. The new tests attempted to save `self.proxy.litellm.acompletion` before installing their forbidden-upstream sentinel, but the earlier stub did not define `acompletion`. The tests therefore errored before exercising the endpoint.

This was a test-isolation defect, not a product-runtime failure. The product implementation, catalog parity tests, endpoint catalog test, alias test, and metadata test all passed in that run. The failing assertions were not weakened; the harness was changed so it temporarily creates the sentinel attribute and removes it afterward when the prior stub did not originally expose one.

## Evidence — corrected clean-machine run

GitHub Actions run: `35022364383`
Job: `104560970309`
Commit: `10c18358f628d7d09fb95f31a7d06bab889bb993`
Result: **SUCCESS**

Clean runner evidence:

- dependency install: success
- Python compile: success
- live `proxy_server` import: success
- regression suite: **80/80 passed**

New catalog-specific tests passing:

- `test_catalog_matches_canonical_registry_keys`
- `test_aliases_are_not_advertised_as_separate_canonical_models`
- `test_endpoint_matches_registry_catalog_exactly`
- `test_catalog_metadata_identifies_registry_scope_not_entitlement`
- `test_missing_model_is_rejected_before_upstream_call`
- `test_blank_model_is_rejected_before_upstream_call`

Existing OpenAI, Anthropic, Google/Gemini, legacy-sync-removal, safe-fallback, and proxy-integration regressions also remained green.

## Result

**COMPLETE for this item.**

Runtime model discovery is no longer a stale four-model snapshot, and chat requests no longer inherit a hidden default model. The catalog follows the versioned provider registries while clearly remaining a TokenTotals pricing-recognition catalog rather than a provider entitlement claim.

## Next item

Diagnose the auto-economy / optimizer logic separately. The current optimizer still contains old hard-coded premium/economy model names and model-name-based cross-provider selection. Pricing knowledge alone does not establish capability equivalence, credential compatibility, or safe automatic substitution, so that behavior requires its own diagnosis, tests, and acceptance criteria before any redesign or removal.
