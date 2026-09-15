# TokenTotals Technical & Security Whitepaper
### Localhost Layer-7 FinOps Proxy, Pre-Flight Circuit Breakers, and Defensive Prior Art Specification
**Author:** QuietFireAI (Jeff Phillips)  
**License:** GNU General Public License v3.0 (GPLv3)  
**Date:** September 2026  
**Document Version:** 2.8-DEFENSIVE-SPEC

---

## 1. Abstract & Prior Art Disclosure

This document describes the current TokenTotals architecture and also preserves its defensive-publication intent.

TokenTotals is a local Layer-7 loopback proxy that listens on `127.0.0.1`. Client applications explicitly route supported LLM API requests through the local proxy. Before forwarding a request, TokenTotals estimates its input-side cost using model-aware token counting/estimation plus provider-specific pricing rules, atomically compares posted spend plus active preflight reservations plus the new request estimate against the configured local threshold, and can reject the request before the upstream completion call.

After successful provider responses, TokenTotals uses observed usage telemetry where available to produce a best-effort local cost estimate. OpenAI, Anthropic, and Google/Gemini have repo-contained provider-specific pricing registries/calculators. TokenTotals does not claim that these estimates reproduce the provider's final invoice.

The open-source publication documents mechanisms including:

1. Local pre-flight LLM cost estimation and pacing before an upstream completion call.
2. A localhost proxy gate tied to persistent local estimated-spend state and a user acknowledgment / local threshold-boost flow.
3. Provider-specific reconstruction of billing-relevant LLM telemetry with explicit incomplete-estimate behavior when required dimensions are unavailable.
4. Request-local callback attribution and serialized single-daemon spend-state updates for concurrent post-response accounting.
5. Ephemeral, atomic in-flight reservation of each admitted request's defensible preflight estimate so concurrent requests cannot consume the same known local headroom.
6. A local append-only turn telemetry ledger that preserves whitelisted token/cost/provenance metadata, explicit missing-field semantics, and per-model history inside a continuing thread without persisting prompt or response text.

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

Let:

* $S_{\text{today}}$ be TokenTotals' locally posted estimated spend;
* $H_{\text{inflight}}$ be the sum of active preflight reservations for requests already admitted but not yet settled; and
* $L_{\text{daily}}$ be the configured local daily threshold.

A new request is admitted only when:

$$S_{\text{today}} + H_{\text{inflight}} + C_{\text{pre}} \leq L_{\text{daily}}$$

The admission check and reservation insertion occur under the same process-local re-entrant lock. Therefore, two concurrent requests cannot both pass against the same known local headroom inside the normal single TokenTotals daemon.

Two rejection cases are intentionally distinguished:

1. If $S_{\text{today}} + C_{\text{pre}} > L_{\text{daily}}$, the request exceeds the threshold even without other active reservations. TokenTotals preserves the existing hard-lock behavior and rejects the request with HTTP `403` before the upstream completion call.
2. If the request would fit against posted spend alone but $S_{\text{today}} + H_{\text{inflight}} + C_{\text{pre}} > L_{\text{daily}}$, the conflict is temporary in-flight contention. TokenTotals returns HTTP `429`, does not send that request upstream, and does not permanently lock the daemon. Headroom can become available after active requests settle or fail.

If TokenTotals cannot obtain a defensible preflight price at all, the current runtime rejects the request with a pricing-unavailable response rather than sending it unmetered.

### 3.3 In-Flight Preflight Reservation Lifecycle

Each admitted request receives a server-owned random reservation identifier. The reservation record contains the request's preflight-estimated cost and thread identifier and is held only in daemon process memory.

The reservation lifecycle is:

1. compute a defensible preflight estimate;
2. atomically check posted spend plus all active reservations plus the new estimate;
3. create an in-memory reservation before invoking LiteLLM;
4. carry the reservation identifier through server-owned request-local LiteLLM callback metadata;
5. on a successful cost callback, persist the observed/derived actual turn cost while still holding the pacing lock, then remove the reservation; or
6. if the upstream call fails before a billable success callback, release the reservation so temporary headroom is not stranded.

Reservations are deliberately **not persisted to `state.json`**. They represent live process work, not settled accounting state. A daemon restart therefore cannot leave phantom reserved dollars on disk.

Settlement is also idempotent for a server reservation identifier inside the running daemon so a duplicated success callback does not double-increment local spend.

### 3.4 Reservation Scope and Remaining Uncertainty

The reservation covers only the cost TokenTotals can defensibly estimate before execution. In the current implementation that is the input-side preflight estimate.

It is therefore possible for a request to reserve $C_{\text{pre}}$, pass admission, and later settle at a larger actual cost because output tokens, reasoning/thinking, hosted tools, service-tier resolution, cache behavior, or other response-dependent dimensions were not knowable at preflight time. If the settled actual spend reaches or exceeds the configured local threshold, TokenTotals marks the local state locked.

Accordingly, in-flight reservation closes the **concurrent reuse of known preflight headroom**. It is not represented as a guarantee that unknown future full-turn charges can never carry settled spend beyond the local threshold.

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

### 6.5 Concurrent Post-Response Accounting

The normal runtime is a single local TokenTotals daemon process. Within that process, post-response accounting is hardened against overlapping completions as follows:

* each forwarded request receives a server-owned TokenTotals thread identifier carried through LiteLLM request-local callback metadata;
* each admitted request also carries its server-owned preflight reservation identifier through that request-local metadata;
* the completion callback reads identifiers attached to its own request rather than a shared process-global “current thread” variable;
* client-supplied `litellm_metadata` is removed before TokenTotals injects its accounting/reservation identifiers, preventing request input from replacing those server-owned values;
* config/state read-modify-write transactions are serialized through a process-local re-entrant lock; and
* same-day spend is accumulated in a per-thread map so out-of-order completions such as `A -> B -> A` retain independent thread totals.

Legacy state containing only an active thread plus `thread_spend_usd` is migrated on the first spend update so the already-recorded same-day active-thread amount is retained.

This design is intentionally scoped to the current one-daemon architecture. It is not represented as a cross-process or distributed transactional store.

### 6.6 Append-Only Local Turn Telemetry Ledger

After a TokenTotals-routed completion settles local accounting, the callback can append one telemetry record to `~/.tokentotals/turns.jsonl`. The server-owned reservation identifier is reused as the durable turn identifier so a duplicated callback cannot append a second history record for the same routed turn.

The runtime writer uses an explicit schema whitelist. It does not serialize arbitrary callback/request dictionaries and therefore does not intentionally persist prompt text, response text, provider API keys, or hidden chain-of-thought/reasoning content. The ledger stores operational/billing telemetry rather than conversation content.

Depending on provider exposure and the ability to derive a field without inventing it, a record can contain:

* requested, canonical, and provider-observed model identities as distinct values;
* provider and pricing-registry verification date;
* input, uncached input, cached input, cache-write/create, output, reasoning/thinking, and tool-input token categories;
* modality token breakdowns and supported server-tool counters;
* provider-reported total tokens, a TokenTotals reconstructed total, and residual/unclassified tokens when the totals do not reconcile;
* timing/latency and requested/observed processing-tier metadata where exposed;
* component costs, total turn estimate, completeness status, and a cost basis identifying a complete provider-registry calculation, LiteLLM response-cost fallback, known list-equivalent fallback, or unavailable total; and
* cumulative local and thread estimated spend after settlement.

Token fields also carry a basis state. `0` is reserved for an actually observed or defensibly derived zero. When a provider does not expose a category, the ledger records that field as unavailable rather than silently treating missing telemetry as zero.

Historical thread summaries are derived from ledger records rather than a second mutable model counter. A single thread can therefore switch among models/providers while retaining one thread identity and simultaneously maintaining independent per-model turn, token, and estimated-cost totals. Summary token categories include both the accumulated value and the number of turns on which that category was actually available, so partial observability is visible.

Cost aggregation in the ledger uses integer picodollar units (`10^-12` USD) before rendering back to dollars. The simpler local state accumulator also retains substantially more internal precision than the four-decimal human-facing display. These choices prevent repeated very small turns from disappearing through display-level rounding.

The ledger file is opened in append mode, flushed, and `fsync`ed for each completed record. Corrupt JSON is surfaced rather than silently skipped. A ledger-write failure is isolated from the already-completed accounting settlement: TokenTotals emits a ledger warning rather than undoing or hiding the cost update.

This is **runtime append-only behavior, not immutable storage**. The JSONL file belongs to the local user and can be edited, moved, or deleted outside TokenTotals. The current ledger is not represented as tamper-evident, cryptographically chained, or a provider-authoritative billing record.

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
