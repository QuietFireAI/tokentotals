# TokenTotals Google/Gemini Pricing Engine — Integration & Recheck Receipt

**Receipt date:** 2026-09-15  
**Repository:** `QuietFireAI/tokentotals`  
**Branch:** `main`

## Status

**COMPLETE FOR THE CURRENT FIRST-PARTY GEMINI DEVELOPER API PUBLIC PAID-TIER SCOPE REPRESENTED BY THE VERSIONED REGISTRY.**

This receipt records the implementation and verification state of the Google/Gemini provider-specific pricing path. It is evidence of what was implemented and tested; it is **not** a representation that TokenTotals mirrors Google invoices, reconstructs every Google account adjustment, or can see provider activity that never passes through the TokenTotals request/response path.

TokenTotals treats LLM cost calculation as cloud-style metering: a best-effort estimate assembled from the telemetry actually available, versioned published pricing references, provider-specific billing mechanics, and explicit fallbacks when a billing dimension cannot be resolved safely.

## Why Google required a separate provider engine

Gemini usage cannot be reduced safely to a single input-token and output-token pair.

The first-party response schema can expose separate billing-relevant counters including:

- `promptTokenCount`
- `cachedContentTokenCount`
- `candidatesTokenCount` / `responseTokenCount`
- `thoughtsTokenCount`
- `toolUsePromptTokenCount`
- `totalTokenCount`
- modality detail arrays for prompt, cache, output, and tool-use tokens
- `serviceTier`
- grounding metadata for provider tools

The billing basis can also depend on model, modality, context length, processing mode/tier, caching, grounding/tool use, pricing period, and account/project state.

The provider engine therefore treats Google usage as a structured meter rather than assuming normalized `prompt_tokens` / `completion_tokens` are always sufficient.

## Governing raw-telemetry rules

### Cached content is a subset of prompt tokens

Google documents `cachedContentTokenCount` as cached content contained within the prompt-token count. TokenTotals therefore subtracts cached tokens from prompt tokens when reconstructing uncached input. It does **not** add cached tokens on top of `promptTokenCount`.

This prevents the classic cache double-counting failure mode.

### Thinking tokens are output-billed once

`thoughtsTokenCount` is tracked separately for observability but contributes to the output-billed token amount. It is not charged a second time as an additional independent output bucket.

### Tool-use prompt tokens are a distinct usage bucket

`toolUsePromptTokenCount` can represent input generated for provider-side tool activity. Where the raw counter is present, TokenTotals represents it explicitly rather than silently folding it into ordinary user prompt input.

Where Google Search grounding is positively identified, TokenTotals avoids double-billing the corresponding tool-use prompt bucket as ordinary model input while representing the public grounding charge separately.

### `totalTokenCount` is a reconciliation signal

TokenTotals does not blindly trust middleware-normalized prompt and completion counters.

If `totalTokenCount` contains a positive residual that cannot be explained by the observed prompt, candidate/output, thinking, and tool-use buckets, the calculation is marked incomplete. The residual is evidence that a provider token category may have been omitted or transformed during normalization.

A conservative known-list-equivalent may still be calculated for guardrail purposes, but it is not presented as a complete total.

## Middleware normalization risk

Gemini middleware normalization has changed over time, including historical cases where billing-relevant Google fields were not preserved correctly.

For that reason the Google engine is intentionally independent of LiteLLM's cost calculator for its primary path. LiteLLM remains a secondary fallback and transport/normalization dependency, not the pricing source of truth for a complete Google calculation.

TokenTotals additionally reconciles normalized totals so that a dropped provider bucket can cause an incomplete result instead of silently disappearing from the meter.

## Versioned middleware dependency

During this audit, `requirements.txt` previously declared only:

`litellm`

That meant a fresh install could silently receive a different normalization implementation than the one validated by this evidence.

The dependency is now pinned to the version used by the final regression evidence:

`litellm==1.101.0`

This does not imply that 1.101.0 will remain the preferred version permanently. A future LiteLLM upgrade should be treated as a metering-regression event and rerun the provider reconciliation tests before release.

Commit:

`a948bc32603af39fe1ea61698abf1975b97a0574`

## Scope represented by the Google registry

The versioned registry is:

`pricing/google_registry.json`

The current scope is public paid-tier pricing mechanics for the first-party Gemini Developer API models represented in that file. The registry includes, where applicable:

- Standard processing
- Batch token rates
- Flex processing
- Priority processing
- uncached input
- cached input
- output
- modality-specific input/cache rates such as audio where published
- long-context thresholds/rates where published
- dated/promotional pricing periods where applicable
- published Search / Maps / File Search reference charges used as list-equivalent context

Registry commit:

`fa4eece45c1ab29db301d2e3267c2a270dbacd01`

## Provider engine

The Google calculator is implemented in:

`google_pricing.py`

Primary engine commit:

`646d5e37ac5bdfa6f08fd797950f81eed8f1e9de`

The calculator supports both raw Google-shaped usage and LiteLLM-normalized usage, while preserving a distinction between a **complete calculation** and a **known public-list-equivalent estimate**.

Unknown future model IDs do not receive guessed rates.

## Processing tier behavior

The applied response tier is preferred over the requested tier when it is available.

This is important for Priority processing because a Priority request can be served as Standard under provider behavior. If Priority was requested but the applied tier cannot be observed, TokenTotals marks the result incomplete instead of asserting the Priority rate was definitely billed.

Batch pricing can be calculated when the engine is explicitly told that the request used the Batch processing path. The current synchronous `/v1/chat/completions` TokenTotals proxy does **not** itself execute Google's Batch API, so the presence of Batch rates in the registry must not be interpreted as proof that ordinary proxy traffic used Batch pricing.

## Long-context handling

For models with published context-length pricing thresholds, the engine selects the long-context rate when the observed prompt basis exceeds the registered threshold.

If aggregate provider tool-use telemetry prevents TokenTotals from proving the per-internal-call threshold basis, the engine can mark the result incomplete rather than forcing a single threshold interpretation across hidden internal calls.

## Grounding and provider-tool charges

### Google Search

When response grounding metadata proves Search execution, TokenTotals can represent the applicable public paid-rate equivalent in the known-list calculation.

However, Search includes project/account allowance mechanics that are not exposed as a remaining-allowance counter in an ordinary generation response. A Search-enabled calculation is therefore not asserted to be invoice-complete solely from a single response.

If Search was requested but grounding execution metadata did not survive the response/middleware path, TokenTotals marks the calculation incomplete rather than assuming either zero executions or a fabricated execution count.

### Google Maps

Maps grounding is handled similarly: observable Maps grounding can contribute the published paid-rate equivalent, but project/account allowance state is not inferred from the response.

### File Search

File Search can add embedding charges. Ordinary generation token telemetry does not prove the complete embedding-token bill, so File Search use is an incompleteness signal unless that meter is supplied separately.

### URL context and other tool-use input

Provider tool-use input can be represented when the relevant Google tool-use token telemetry survives the response path. If the feature is known to be enabled but the billing-relevant counter is absent, TokenTotals does not manufacture a complete total.

## Cache-storage boundary

The registry contains published cache-storage rate references where applicable, but an ordinary generation response does not provide the complete duration/lifetime information required to reconstruct a cache-storage bill.

The current per-response calculator therefore does not pretend that cache-storage duration charges are fully reconstructed from generation telemetry alone.

## Vertex AI boundary

This receipt does **not** certify Google Vertex AI pricing.

Model IDs with a Vertex prefix can be recognized, but the current registry scope is the Gemini Developer API public paid tier. Vertex regional behavior, provisioned throughput, marketplace/enterprise arrangements, and contract pricing are not silently mapped onto Developer API list pricing. The engine marks that platform mismatch incomplete.

## Antigravity / agent-loop boundary

A proxied final response cannot prove the cost of provider-side inference calls that never traverse TokenTotals or are not represented in returned usage telemetry.

This matters for autonomous/agentic environments where intermediate model calls, reasoning turns, tool calls, retries, or sub-steps can occur inside the provider product/runtime.

TokenTotals can account for what it can observe and reconcile. It cannot reconstruct invisible internal Antigravity activity from the final answer alone, and this receipt makes no claim that it can.

## Defects found during implementation and recheck

### 1. Normalized tool-use input was initially omitted from the calculation branch

The first local Google implementation normalized LiteLLM `tool_use_tokens`, but the detailed normalized-input costing branch did not add that separate tool-use bucket to cost.

A regression test failed and exposed the omission before the provider implementation was accepted.

**Repair:** the normalized structure now tracks whether tool-use prompt tokens remain a separate billing bucket and charges them once when appropriate.

This unfavorable finding is intentionally preserved because it demonstrates the failure mode the Google work was designed to catch: a field can exist in telemetry and still be omitted from the arithmetic.

### 2. Middleware version was not reproducible

The repo previously installed whichever LiteLLM version happened to be current at install time.

**Repair:** pin the tested normalization version to `litellm==1.101.0` and require the full pricing regression suite for future middleware changes.

### 3. Google was not wired into the live provider path

Before this work, Google/Gemini traffic still depended on the legacy pricing path rather than a repo-contained provider engine.

**Repair:** wire Google provider detection, preflight input estimation, post-response telemetry accounting, request-feature hints, and non-zero incomplete fallback into `proxy_server.py`.

Live integration commit:

`240d7a340f67be7b6a4633d30d1a6ab39a5bbcf2`

## Live post-response accounting order

For recognized Google/Gemini responses the live accounting path is now:

1. Calculate from the repo-contained Google registry and response telemetry when required billing dimensions can be reconstructed safely.
2. If the local Google calculation is incomplete, use LiteLLM `response_cost` when LiteLLM supplies a non-zero value.
3. If LiteLLM supplies no response cost but the Google engine can produce a defensible known public-list-equivalent amount from the telemetry it does have, record that amount instead of silently recording `$0`.
4. Log that the known-list-equivalent value is incomplete and is not an invoice mirror.
5. Only if no defensible provider-derived, middleware-derived, or known-list-equivalent amount exists can the path reach zero.

## Preflight / circuit-breaker behavior

Recognized Google models now use the repo-contained Google registry for preflight input estimation rather than the machine-specific legacy pricing plugin when the required model/rate information is available.

Preflight is explicitly input-only. Final output volume, cache outcomes, grounding/tool execution, free allowances, hidden provider activity, and account-level adjustments are not yet known before the request runs.

## Provider-level regression coverage

`tests/test_google_pricing.py` covers:

- provider-prefixed Gemini model resolution
- raw Google thinking tokens billed once as output
- cache subtraction rather than cache double counting
- raw `toolUsePromptTokenCount`
- residual detection when tool-use/provider token buckets disappear
- LiteLLM-normalized tool-use accounting
- normalized residual refusal
- observed Standard tier overriding requested Priority when Google reports Standard
- unresolved requested Priority being incomplete
- long-context pricing
- audio input pricing
- Search grounding list-equivalent handling
- Search request hints with missing execution telemetry
- Vertex platform refusal/incompleteness
- unknown model refusal
- Priority preflight pricing

Provider-test commit:

`692c4a1d1cbc4b9b0345ddd2ae1973566df1bfa9`

## Live-proxy integration regression coverage

`tests/test_proxy_google_integration.py` proves that:

- complete Google telemetry causes the local provider engine to win over an intentionally bogus LiteLLM response cost
- incomplete Google telemetry falls back to a supplied LiteLLM cost
- incomplete Google telemetry with no LiteLLM cost uses a non-zero known Google list-equivalent rather than `$0`
- Google preflight uses the repo registry
- Priority preflight uses the registered Priority rate
- nested Google server-tool parameters become provider feature hints
- `web_search_options` becomes a Google Search hint
- provider-prefixed Gemini IDs enter the Google path

Integration-test commit:

`6fdb8a229fd043bc9bef9133bccbd04ee39dd238`

## CI evidence

### Provider-engine stage

After the Google provider registry/calculator/tests were added, GitHub Actions run:

- **Run:** `35019342418`
- **Job:** `104550817943`
- clean dependency install: PASS
- Python compile: PASS
- real `proxy_server` smoke import: PASS
- full regression suite: **57 tests run, 57 passed**

This run demonstrated that the Google provider engine did not regress the existing OpenAI or Anthropic suites.

### Live integration stage

After Google was wired into the proxy and integration tests were added:

- **Run:** `35019653855`
- **Job:** `104551879639`
- clean dependency install: PASS
- Python compile: PASS
- real `proxy_server` smoke import: PASS
- full regression suite: **65 tests run, 65 passed**

The log explicitly exercised the incomplete-normalization warning and the no-LiteLLM-cost known-equivalent fallback.

### Final pinned-middleware verification

After pinning LiteLLM to the tested normalization version:

- **Run:** `35019741429`
- **Job:** `104552168578`
- **Head commit:** `a948bc32603af39fe1ea61698abf1975b97a0574`
- **Runner:** Ubuntu 24.04
- **Python:** 3.12.14
- **Installed middleware:** `litellm==1.101.0`
- clean dependency installation: PASS
- Python compile: PASS
- real `proxy_server` smoke import: PASS
- full regression suite: **65 tests run, 65 passed**

Expected warning paths were observed in CI, including:

- normalized Gemini totals with an unexplained residual being refused as complete
- fallback to LiteLLM cost when available
- fallback to Google known list-equivalent rather than `$0` when LiteLLM supplied no response cost

## Interpretation

The Google/Gemini pricing path is now a functioning TokenTotals product path rather than a detached table or generic middleware estimate.

Within the current first-party Gemini Developer API public paid-tier scope represented by the versioned registry, TokenTotals now has provider-specific preflight estimation, post-response accounting, raw/normalized telemetry reconciliation, explicit incompleteness rules, and executable CI evidence.

That does **not** make Google billing deterministic from every response. Google can change model prices, model IDs, modalities, caching, context thresholds, processing tiers, grounding/tool charges, allowances, product behavior, account contracts, middleware normalization, or agent runtime behavior. The provider invoice remains authoritative.

The required operating rule remains: use the best available measured inputs and known rules, preserve provenance, refuse unsupported certainty, and expose the fallback when a complete estimate cannot be reconstructed.

## Next unresolved pricing-hardening item

With OpenAI, Anthropic, and the scoped Google/Gemini Developer API paths now using repo-contained provider engines, the next item is to diagnose and retire or appropriately demote the remaining **legacy pricing plumbing**:

- the machine-specific local pricing-plugin path still present in `proxy_server.py`
- the daily `pricing_sync.py` task that downloads the third-party LiteLLM pricing catalog and labels it as live pricing
- any remaining code paths that still depend on those mechanisms

That cleanup must be diagnosed before removal so unsupported providers or fallback behavior are not broken blindly.
