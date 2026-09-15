# 📊 TokenTotals Provider Pricing Mechanics Matrix

TokenTotals produces **best-effort cost estimates** from available API telemetry plus versioned provider-specific pricing rules. It is not a billing mirror and does not claim invoice-exact alignment.

This document intentionally does **not** duplicate a second hand-maintained table of model prices. The machine-readable registries under [`pricing/`](pricing/) are the repository source of truth for first-party pricing rules that TokenTotals has explicitly modeled:

- [`pricing/openai_registry.json`](pricing/openai_registry.json)
- [`pricing/anthropic_registry.json`](pricing/anthropic_registry.json)
- [`pricing/google_registry.json`](pricing/google_registry.json)

> **Documentation reconciliation date:** 2026-09-15  
> Registry entries carry their own `verified_at`, source URLs, scope notes, aliases, rates, modifiers, and model-specific exceptions. Re-verify provider documentation before extending or refreshing a registry.

---

## Why this is a mechanics matrix, not a leaderboard

Modern AI API pricing increasingly resembles cloud infrastructure pricing rather than a single input/output price pair. A model name alone is not sufficient to reconstruct every invoice component. Relevant dimensions can include cache reads and writes, processing/service tiers, long-context thresholds, reasoning/thinking tokens, modalities, hosted tools, geographic processing, batch modes, account allowances, negotiated rates, credits, taxes, and provider-side adjustments.

A static "frontier / workhorse / economy" ranking also implies capability equivalence that TokenTotals does not establish. TokenTotals therefore keeps model selection with the user or calling application and focuses on pricing reconstruction from observable billing dimensions.

---

## Provider mechanics currently modeled

| Billing dimension | OpenAI | Anthropic / Claude API | Google / Gemini Developer API |
| :--- | :--- | :--- | :--- |
| **Canonical model registry** | Yes | Yes | Yes |
| **Uncached input tokens** | Yes | Yes | Yes |
| **Cached input / cache reads** | Yes, model-specific | Yes, model-specific | Yes, model/mode/modality-specific |
| **Cache creation / writes** | Modeled where provider/model rules expose a verified rate | 5-minute and 1-hour write categories where telemetry/rules resolve them | Explicit cache-storage pricing exists; storage-duration cost is not invented when duration is unavailable |
| **Output / reasoning / thinking** | Output/reasoning handling follows observable provider telemetry and model rules | Thinking is not double-charged when already represented in output usage | Thinking tokens are handled separately when raw Gemini telemetry exposes them |
| **Service / processing tier** | Model-specific tier handling; unresolved tier can make the estimate incomplete | Standard, batch, fast, priority/inference constraints as modeled | Standard, batch, flex, priority where modeled and observable |
| **Long-context pricing** | Model-specific thresholds where verified | Provider/model rules as represented in registry | Model-specific thresholds where verified |
| **Hosted/server tools** | Token-only total is refused when known billable tool activity is unresolved | Web-search request pricing and web-fetch behavior modeled; unknown tool SKUs remain incomplete | Search/Maps/tool activity is included only when the necessary usage/counter is observable; allowance state is not guessed |
| **Geographic modifiers** | Only where verified for the modeled rule | Inference geography modeled for applicable Claude generations | Vertex AI is outside the Gemini Developer API registry scope and is not silently treated as equivalent |
| **Modality-specific rates** | Marked incomplete when unsupported telemetry/rules prevent a defensible total | Applied only where the modeled API rules support it | Audio vs. default input/cache rates modeled where provider rules distinguish them |
| **Unknown model behavior** | Never invent a provider-specific rate | Never invent a provider-specific rate | Never invent a provider-specific rate |
| **Incomplete telemetry behavior** | Decline false precision; use disclosed fallback only where available | Prefer local engine; nonzero middleware response cost or known list-equivalent fallback may be recorded with warning | Detect normalization residuals; prefer local engine; nonzero middleware response cost or known list-equivalent fallback may be recorded with warning |

---

## Runtime source-of-truth order

For OpenAI, Anthropic, and Google/Gemini models recognized by the repo-contained provider engines:

1. **Provider-specific TokenTotals registry + calculator** is the primary path.
2. **Observed response telemetry** is preferred over request assumptions whenever it can resolve the actual billing dimension.
3. If a provider-specific calculation is incomplete, TokenTotals may use an available nonzero LiteLLM `response_cost` as a secondary estimate, or a deliberately labeled known list-equivalent fallback for supported cases.
4. Missing billing dimensions are disclosed rather than filled with fabricated precision.

For a provider outside those three dedicated engines, preflight may use the **exact model key** from the pinned LiteLLM catalog as a secondary estimate. If no defensible preflight price exists, TokenTotals blocks the request rather than substitute a universal rate.

---

## Generic arithmetic

Where a billing component and its applicable rate are both known, the arithmetic is straightforward:

$$\text{Estimated Component Cost} = \frac{\text{Billable Units}}{1,000,000} \times \text{Applicable Rate}$$

The hard part is determining the correct **billable units, rate category, and modifiers** for that specific provider/model/request. The provider calculators and registries exist to perform that interpretation rather than assuming every response is simply `input_tokens × one rate + output_tokens × one rate`.

---

## Estimation boundary

A TokenTotals calculation is only as complete as the billing-relevant information available at that moment. Public list pricing also cannot reveal private offers, negotiated contracts, account/project allowance state, credits, taxes, or every provider-side adjustment.

The arithmetic can be deterministic once all applicable inputs are known. **The resulting TokenTotals value should never be represented as a mirror of the provider's final invoice.** The provider's account records and final invoice remain authoritative.
