# TokenTotals Anthropic Pricing Engine — Integration & Recheck Receipt

**Receipt date:** 2026-09-15  
**Repository:** `QuietFireAI/tokentotals`  
**Branch:** `main`

## Status

**COMPLETE FOR THE CURRENT FIRST-PARTY CLAUDE API PRICING SCOPE.**

This receipt records the implementation and verification state of the Anthropic provider-specific pricing path. It is evidence of what was implemented and tested; it is not a representation that TokenTotals mirrors Anthropic invoices or that provider pricing will remain unchanged.

TokenTotals treats LLM cost calculation as cloud-style metering: a best-effort estimate assembled from the telemetry actually available, versioned published pricing references, provider-specific billing mechanics, and explicit fallbacks when a billing dimension cannot be resolved safely.

## Scope

The Anthropic calculator covers **first-party Claude API public list-pricing mechanics** represented by the repository registry. It does not infer invoice totals for Amazon Bedrock, Google Vertex AI / partner marketplaces, private offers, negotiated discounts, contractual Priority Tier commitments, taxes, credits, or other account-specific adjustments.

The engine currently represents, where telemetry is sufficient:

- base input tokens
- 5-minute prompt-cache writes
- 1-hour prompt-cache writes
- prompt-cache reads
- output tokens
- thinking-token telemetry without double charging output
- inference geography and the registered US-only multiplier
- Fast-mode rates where verified for the model
- Batch token-price discount in the provider engine
- Standard vs. Priority service-tier handling
- Anthropic web-search request charges
- web-fetch usage where no separate request charge applies
- raw Anthropic usage shapes
- LiteLLM-normalized usage shapes
- ambiguous cache-token bases, which are refused rather than guessed
- unknown models and unknown server-tool meters, which are refused rather than assigned invented prices

## Runtime integration

The provider engine is no longer detached from the product path.

`proxy_server.py` now imports the repo-contained Anthropic pricing engine and routes Anthropic traffic through it.

### Preflight / circuit-breaker estimate

For recognized Anthropic models, preflight input estimation uses the local Anthropic registry rather than the machine-specific legacy pricing plugin whenever the required model/rate information is available.

For geography-sensitive models, unresolved geography is treated conservatively for the preflight circuit breaker by using the highest known first-party geography multiplier represented in the registry rather than silently assuming the cheaper geography.

Preflight remains an estimate. It cannot know final output tokens, future tool activity, cache outcomes, or every account-level pricing condition before the request runs.

### Post-response accounting order

For Anthropic responses the live accounting path is now:

1. Calculate from the repo-contained Anthropic registry and observed response telemetry when the required billing dimensions can be reconstructed safely.
2. If the local calculation is incomplete, use LiteLLM `response_cost` when LiteLLM supplies a non-zero response cost.
3. If LiteLLM supplies no response cost but the Anthropic calculator can produce a known public-list-equivalent amount from the telemetry it does have, record that estimate instead of silently recording `$0`.
4. Only when no defensible provider-derived, middleware-derived, or known-list-equivalent estimate is available can the accounting path reach zero.

A known-list-equivalent fallback is explicitly logged as incomplete and is **not** described as an invoice mirror.

## Defects found during recheck

The recheck found material issues after the first integration pass. They were preserved rather than hidden.

### 1. Anthropic engine was not wired into the live proxy

The registry, calculator, and unit tests existed, but `proxy_server.py` imported only the OpenAI provider engine. From the product perspective the Anthropic feature was therefore incomplete.

**Repair:** wired Anthropic provider detection, preflight estimation, response telemetry calculation, and fallback behavior into `proxy_server.py`.

Primary integration commit:

`550ef08ae9fd3aa5a69a86dcfd29feb004e1e476`

### 2. LiteLLM was an undeclared runtime dependency

`proxy_server.py` imports LiteLLM, but `requirements.txt` did not declare `litellm`. A fresh installation could therefore fail before the proxy started.

**Repair:** added LiteLLM to the declared runtime requirements.

Commit:

`d751f3389fb34fd9d306f63682608c168da12b51`

### 3. Incomplete telemetry plus missing middleware cost could record zero

The first live integration fell back to LiteLLM when Anthropic telemetry was insufficient for a complete local calculation. If LiteLLM also supplied no `response_cost`, the generic fallback could record `$0`, which is unsafe for a cost guardrail.

**Repair:** when Anthropic has a calculable public-list-equivalent amount but not a complete all-in total, that amount is now used as the last-resort non-zero estimate if LiteLLM supplies no cost. The runtime emits a warning that the value is incomplete.

Repair commit:

`38323c718d102a6f73d988e5c3e5af94aa199080`

Regression coverage commit:

`a1feff88c3ddc216aaf3200f2aa096b81205933f`

## Integration regression coverage

`tests/test_proxy_anthropic_integration.py` verifies that:

- complete Anthropic telemetry causes the local provider engine to win over an intentionally bogus LiteLLM response cost
- incomplete Anthropic telemetry falls back to a supplied LiteLLM cost
- incomplete Anthropic telemetry with no LiteLLM cost records the known public-list-equivalent estimate rather than zero
- Anthropic preflight uses the provider registry
- unresolved geography is treated conservatively in preflight
- verified Fast-mode input pricing is used when requested
- unknown Anthropic models do not receive an invented local preflight price
- provider hints can be recovered from nested LiteLLM callback parameters

The provider-level Anthropic regression suite separately covers cache TTLs, cache reads/writes, inference geography, Fast mode, Batch calculations, service tiers, web search/fetch, unknown server tools, model resolution, thinking-token handling, and LiteLLM cache-normalization ambiguity.

## CI evidence

A permanent GitHub Actions workflow was added in:

`.github/workflows/tests.yml`

Workflow commit:

`eea6346fea76d911865b49738ebaf3d0ad396086`

The final verification run for the latest regression commit was:

- **GitHub Actions run:** `35002945386`
- **Job:** `104495548749`
- **Head commit:** `a1feff88c3ddc216aaf3200f2aa096b81205933f`
- **Runner:** Ubuntu 24.04
- **Python:** 3.12.14
- **Dependency installation:** PASS
- **Python compile check:** PASS
- **Real `proxy_server` smoke import with LiteLLM installed:** PASS
- **Regression suite:** **41 tests run, 41 passed**

The final run explicitly passed:

`test_missing_litellm_cost_uses_known_list_equivalent_not_zero`

and emitted the expected warning that the public-list-equivalent fallback is incomplete and is not an invoice mirror.

## Interpretation

The Anthropic pricing path is now a functioning product path rather than a detached provider module. Within the current first-party Claude API scope, it is wired into both preflight protection and post-response accounting and has executable regression evidence.

That does **not** make TokenTotals a deterministic billing calculator. Anthropic can change model prices, cache mechanics, tool charges, service tiers, platform behavior, telemetry fields, regional policies, contractual pricing, or middleware normalization. The system therefore remains deliberately conservative: use the best available measured inputs and known rules, identify provenance, refuse unsupported certainty, and fall back visibly when a complete estimate cannot be reconstructed.

## Next provider-specific item

Google/Gemini pricing still remains on the legacy pricing path and has not yet received the same provider-specific registry, telemetry normalization, integration, and recheck treatment. That is the next unresolved provider-pricing item after this receipt.