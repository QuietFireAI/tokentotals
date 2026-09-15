# TokenTotals Technical & Security Whitepaper
### Localhost Layer-7 FinOps Proxy, Pre-Flight Circuit Breakers, and Defensive Prior Art Specification
**Author:** QuietFireAI (Jeff Phillips)  
**License:** GNU General Public License v3.0 (GPLv3)  
**Date:** September 2026  
**Document Version:** 2.5-DEFENSIVE-SPEC

---

## 1. Abstract & Prior Art Disclosure

This document describes the current TokenTotals architecture and also preserves its defensive-publication intent.

TokenTotals is a local Layer-7 loopback proxy that listens on `127.0.0.1`. Client applications explicitly route supported LLM API requests through the local proxy. Before forwarding a request, TokenTotals estimates its input-side cost using model-aware token counting/estimation plus provider-specific pricing rules, compares that estimate with local accumulated estimated spend and the configured local threshold, and can reject the request before the upstream completion call.

After successful provider responses, TokenTotals uses observed usage telemetry where available to produce a best-effort local cost estimate. OpenAI, Anthropic, and Google/Gemini have repo-contained provider-specific pricing registries/calculators. TokenTotals does not claim that these estimates reproduce the provider's final invoice.

The open-source publication documents mechanisms including:

1. Local pre-flight LLM cost estimation and pacing before an upstream completion call.
2. A localhost proxy gate tied to persistent local estimated-spend state and a user acknowledgment / local threshold-boost flow.
3. Provider-specific reconstruction of billing-relevant LLM telemetry with explicit incomplete-estimate behavior when required dimensions are unavailable.

---

### 1.1 Non-Invasive Observability & Liability Disclaimer

TokenTotals is not an upstream accounting system. It does not query authoritative provider account balances, credit lines, negotiated contracts, or final invoices. It calculates local estimates from observable request/response telemetry, versioned provider-published pricing rules, and explicitly disclosed fallback data where applicable.

The provider's final account records remain authoritative. TokenTotals also does not guarantee absolute operating-system/network blocking outside requests actually routed through the TokenTotals proxy.

---

## 2. Threat Model & Local Loopback Architecture

### 2.1 The Autonomous-Agent Spend Risk

Generative-AI tools can execute recursive agent loops, retries, parallel calls, or unexpectedly large requests. A local pacing layer can provide an additional near-real-time estimated-spend signal for traffic routed through it rather than relying only on later provider account reporting.

### 2.2 Local Control Plane / No Secondary TokenTotals Telemetry Service

TokenTotals' control plane is local:

* **Loopback Boundary:** The application server binds to `127.0.0.1` in the shipped runtime path.
* **Local State:** Configuration and estimated-spend state are stored locally under `~/.tokentotals/`.
* **No TokenTotals SaaS Account:** The local runtime does not require a TokenTotals-operated remote telemetry/analytics account.
* **Upstream Egress Still Exists:** When the pacing gate permits a request, the host necessarily sends that request to the selected upstream model provider through LiteLLM. “Localhost” therefore does not mean “no network egress to the provider.”
* **Credential Path:** Provider credentials supplied by the client are passed into the upstream LiteLLM call. TokenTotals does not intentionally persist those API keys in its config/state files.

This distinction is important: TokenTotals avoids adding a separate TokenTotals-operated observability gateway, but it does not eliminate the network relationship between the client and the selected AI provider.

---

## 3. Pre-Flight Circuit-Breaker Formulation

TokenTotals applies a local preflight pacing decision before invoking the upstream completion function.

### 3.1 Pre-Flight Input Estimate

For request payload $R$ containing messages $M$ targeted at explicit model $m$, TokenTotals first obtains a model-aware input-token estimate where possible and falls back to a local heuristic if the tokenizer cannot provide one:

$$\widehat{T}_{\text{in}} = \text{TokenEstimate}(M, m)$$

The preflight dollar estimate is then calculated from the pricing path applicable to that model and request context:

$$C_{\text{pre}} = \text{InputPricingEstimate}(m, \widehat{T}_{\text{in}}, R)$$

For models recognized by the dedicated OpenAI, Anthropic, or Google/Gemini engines, that estimate uses the corresponding repo-contained registry/rules. If a dedicated provider engine cannot produce a defensible preflight estimate, TokenTotals does not silently substitute a generic cross-provider rate.

For other providers, TokenTotals may use an exact-model input rate from the pinned LiteLLM catalog as a disclosed secondary preflight source. If no defensible preflight price exists, the request is rejected rather than assigned an invented universal price.

This preflight value is a pacing estimate, not a promise of the final full-turn or invoice amount. Output, tools, cache behavior, actual service tier, and other response-dependent dimensions may only be known after execution.

### 3.2 Local Pacing Rule

Let $S_{\text{today}}$ be TokenTotals' locally accumulated estimated spend and $L_{\text{daily}}$ the configured local daily threshold:

$$\text{If } (S_{\text{today}} + C_{\text{pre}}) > L_{\text{daily}} \implies \text{REJECT}(R)$$

When this condition is true in the current proxy path:

1. TokenTotals marks its local state locked.
2. The request receives an HTTP `403` response from the local proxy.
3. The upstream completion function is not invoked for that rejected request.
4. The desktop UI can surface the locked state and user acknowledgment/boost controls.

If TokenTotals cannot obtain a defensible preflight price at all, the current runtime rejects the request with a pricing-unavailable response rather than sending it unmetered.

---

## 4. Local Lockout & User Recovery Flow

When local state is locked, subsequent routed completion requests are rejected by the proxy until the local state is unlocked.

The desktop application can surface a topmost Tkinter modal with an operating-system audio cue. The user can acknowledge the warning with the `"I UNDERSTAND"` phrase or use the local quick-boost control to raise the configured TokenTotals daily threshold and clear the local lock.

This mechanism changes TokenTotals' local pacing state. It does not modify the provider's own billing limit, account balance, or provider-side quota.

---

## 5. Model-Integrity Boundary

TokenTotals preserves the model identifier explicitly selected by the client. It does not automatically downgrade, remap, or substitute a different model or provider based solely on prompt length or comparative list pricing.

This boundary is intentional. A lower token price does not establish functional equivalence. Safe substitution would require information that a pricing meter alone cannot prove, including:

* provider credentials and authorization;
* supported tools and modalities;
* context-window and structured-output requirements;
* reasoning and latency requirements;
* provider-specific policy and data-handling constraints; and
* application-specific quality or capability requirements.

Earlier experimental builds included a heuristic counterfactual downgrade/potential-savings feature. That behavior was retired rather than updated with newer model names because the heuristic could not defensibly prove equivalent execution or full-turn savings. Model selection remains the responsibility of the user or calling application.

---

## 6. Provider-Specific Post-Response Accounting

The post-response meter is intentionally provider-specific rather than one universal input/output formula.

### 6.1 OpenAI

The OpenAI calculator uses the versioned OpenAI registry and observed normalized response telemetry. Depending on model/rule availability, relevant dimensions include uncached/cached input, output/reasoning behavior, service tier, long-context rules, cache-write behavior, and known hosted-feature uncertainty. It declines an all-in claim when known billable dimensions cannot be resolved.

### 6.2 Anthropic / Claude API

The Anthropic calculator distinguishes base input, cache creation/read categories, output, applicable inference geography, batch/fast/service-tier particulars, and supported server-tool charges. Ambiguous cache or tier/geography information can make an estimate incomplete rather than forcing a guessed total.

### 6.3 Google / Gemini Developer API

The Google calculator reconciles raw-Gemini-style usage and LiteLLM-normalized usage where possible. It accounts for provider-specific categories such as cached content, thinking tokens, tool-use prompt tokens, modality-specific rates, context thresholds, processing modes, and supported grounding/tool rules. Normalization residuals are treated as a warning that a provider category may have been dropped, not as permission to assume zero cost.

### 6.4 Fallbacks and Estimate Status

The dedicated provider engine is the primary calculation path for recognized OpenAI, Anthropic, and Google/Gemini models. When a complete local provider calculation is not possible, TokenTotals can use a nonzero LiteLLM response cost or an explicitly labeled known list-equivalent fallback in supported cases. Those fallbacks are estimates and are not represented as provider-authoritative billing.

---

## 7. Pricing Provenance

Machine-readable provider pricing rules are stored under:

* `pricing/openai_registry.json`
* `pricing/anthropic_registry.json`
* `pricing/google_registry.json`

Each registry records a verification date, source documentation, modeled scope, model/rate information, and relevant provider-specific notes. The human-readable `MODEL_COMPARISON_MATRIX.md` documents mechanics and provenance rather than maintaining a second competing table of rates.

Pricing can change. A repository snapshot is therefore evidence of what was modeled and verified at that point in time, not permanent pricing truth.

---

## 8. Conclusion

TokenTotals is a local observability and pacing layer for LLM development traffic routed through it. Its design goal is to make cost estimation more transparent and conservative without pretending to be the provider's accounts-receivable system or silently changing the user's requested model.

The strongest invariant is simple: where TokenTotals has enough information, it applies the modeled provider rules; where it does not, it should expose or act on that uncertainty rather than fabricate precision.
