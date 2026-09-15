# TokenTotals Calculation Transparency

TokenTotals is designed to be checkable. When it derives a number rather than merely relaying provider telemetry, the arithmetic should be understandable from the documentation and reproducible from the same inputs.

This document describes the calculations currently used by the runtime. It is not a substitute for the provider's invoice, and it does not imply that every provider exposes every billing dimension on every response.

## 1. Three classes of data

TokenTotals keeps three concepts separate:

- **Observed** — a value exposed by the provider/client response or other supported runtime telemetry.
- **Derived** — arithmetic TokenTotals performs on observed values and versioned pricing rules.
- **Unavailable** — a value TokenTotals cannot defensibly reconstruct. Missing is not converted to zero.

The provider's final invoice and account records remain authoritative.

## 2. Preflight token estimate

Before a routed request is sent upstream, TokenTotals needs a defensible input-side estimate for local pacing.

Primary path:

```text
estimated_input_tokens = LiteLLM token_counter(model, serialized_messages)
```

If that tokenizer path is unavailable, TokenTotals uses a deliberately labeled local heuristic:

```text
estimated_input_tokens = max(1, character_count(serialized_messages) // 4)
```

That fallback is a token-volume estimate only. It is not presented as observed provider usage.

## 3. Preflight estimated input cost

For a dedicated provider engine, TokenTotals resolves the requested model against the versioned provider registry and applies the provider-specific input rule.

The basic component shape is:

```text
estimated_input_cost = (estimated_input_tokens / 1,000,000) × effective_input_rate_per_million
```

Where a verified provider rule requires a modifier, the effective rate incorporates it. For example:

```text
effective_input_rate = base_input_rate × verified_modifier
```

For a provider outside the dedicated engines, TokenTotals may use an **exact model key** from the pinned LiteLLM catalog:

```text
estimated_input_cost = estimated_input_tokens × LiteLLM_input_cost_per_token
```

If no defensible preflight price exists, TokenTotals returns pricing unavailable rather than inventing a universal rate.

## 4. Post-response estimated cost components

When response telemetry is available, TokenTotals prices the billing categories exposed for that provider/model. Each known component follows the same auditable pattern:

```text
component_cost = (billable_units / 1,000,000) × applicable_rate_per_million
```

For per-request hosted tools or similar unit-priced features:

```text
component_cost = observed_request_count × applicable_per_request_rate
```

Examples of separately modeled component categories, when applicable and exposed, include:

- uncached/base input;
- cached input / cache read;
- cache write or cache creation;
- output;
- reasoning/thinking where the provider bills it separately rather than already including it in output;
- modality-specific units such as audio where supported by the provider rule;
- hosted/server-tool request charges where the provider exposes enough telemetry to price them;
- verified service/processing-tier, geography, speed, long-context, or batch modifiers where the provider rule requires them.

The estimated turn total is:

```text
estimated_turn_cost = sum(all defensibly priced billing components)
```

TokenTotals only labels that result `complete` when the provider engine has enough telemetry to account for all billing dimensions it knows are required for that turn. Otherwise the estimate remains explicitly incomplete and may use a disclosed fallback basis such as LiteLLM response cost or a known list-equivalent estimate where defensible.

The runtime stores the component map used for the turn in `pricing_components_usd`, alongside `estimated_cost_usd`, `cost_basis`, `estimate_complete`, and the pricing-registry verification date.

## 5. Cached-input share

TokenTotals does **not** equate cached-token percentage with dollar savings percentage.

When both input and cached-input counts are available:

```text
cached_input_share_pct = (cached_input_tokens / input_tokens) × 100
```

Example:

```text
32,768 cached / 34,521 input × 100 = 94.92% cached-input share
```

Dollar effect depends on the provider/model's actual cached-input rate and other billing mechanics; it is calculated through the pricing engine, not inferred from the token percentage.

## 6. Uncached input

Where the provider exposes enough categories to derive it, TokenTotals uses the provider-appropriate subtraction. A common form is:

```text
uncached_input_tokens = input_tokens - cached_input_tokens
```

For providers/models where cache-write/create tokens are separately represented inside the input basis, the reconstruction can instead be:

```text
uncached_input_tokens = input_tokens - cached_input_tokens - cache_write_tokens
```

The ledger records whether the resulting field is observed, derived, or unavailable.

## 7. Reconstructed total tokens

Where input and output are both known:

```text
reconstructed_total_tokens = input_tokens + output_tokens
```

Provider-specific normalization prevents known subcategories such as reasoning/thinking from being double-counted when they are already included in a provider's output total.

## 8. Reconciliation delta and unclassified tokens

When both the provider's reported total and TokenTotals' reconstructed total exist:

```text
reconciliation_delta_tokens = provider_reported_total_tokens - reconstructed_total_tokens
```

For provider shapes where a positive residual represents unattributed usage:

```text
unclassified_tokens = max(0, reconciliation_delta_tokens)
```

A non-zero residual is evidence that a category may be missing from normalized telemetry. TokenTotals preserves that discrepancy rather than silently forcing the totals to match.

## 9. Output token rate

The presentation layer may show a wall-clock output rate when output tokens and callback elapsed time are known:

```text
output_tokens_per_wall_second = output_tokens / (latency_ms / 1000)
```

This is explicitly a **wall-clock rate**, not pure model generation throughput. Network, queueing, provider processing, callbacks, and transport can all contribute to elapsed time.

## 10. Turn-size statistics

For each turn, TokenTotals selects the provider-reported total token count when available; otherwise it uses the TokenTotals reconstructed total.

For the resulting sampled turn totals:

```text
sum = Σ(turn_total_tokens)
average = sum / sampled_turn_count
median = standard statistical median
max = largest sampled turn total
```

P95 uses the nearest-rank method:

```text
rank = ceil(0.95 × sample_count)
p95 = sorted_values[rank - 1]
```

Coverage is reported separately so a partial sample cannot masquerade as complete thread coverage.

## 11. Token-field coverage

For each token category in a thread:

```text
coverage = unavailable, if observed_turns = 0
coverage = complete,    if observed_turns = total_turns
coverage = partial,     otherwise
```

The displayed sum is withheld (`null`/Unavailable) when zero turns expose the field. This is how TokenTotals avoids turning missing telemetry into a fake zero.

## 12. Estimated-cost coverage

For a thread or model group:

```text
estimated_cost_usd = Σ(costed turn estimates)
```

Coverage is:

```text
unavailable  if costed_turns = 0
complete     if costed_turns = total_turns
partial      otherwise
```

A partial cost total is therefore explicitly labeled partial rather than presented as the full cost of the thread.

## 13. Posted local estimated spend

When a completed routed turn settles:

```text
posted_local_estimated_spend = prior_posted_local_estimated_spend + settled_turn_estimate
```

The active thread's local estimate is updated the same way for that thread.

Internal local-spend accumulation keeps more precision than the four-decimal human display so repeated micro-cost turns are not erased by presentation rounding.

Duplicate success callbacks carrying the same server-owned reservation ID are ignored for settlement so the same turn is not posted twice.

## 14. In-flight preflight estimate

For currently admitted but unsettled requests:

```text
inflight_preflight_estimate = Σ(active reservation estimated_input_cost)
```

Reservations are process-local and ephemeral. They are not persisted as actual spend.

## 15. Combined local estimate

The local pacing display combines settled local estimates with active preflight reservations:

```text
combined_local_estimate = posted_local_estimated_spend + inflight_preflight_estimate
```

This number is a local pacing quantity, not a provider balance or credit-line reading.

## 16. Local threshold percentages

For a positive configured local pacing threshold:

```text
posted_threshold_pct = (posted_local_estimated_spend / local_pacing_threshold) × 100
combined_threshold_pct = (combined_local_estimate / local_pacing_threshold) × 100
```

The tray/dashboard traffic light is derived from local threshold state and the configured warning percentage. It does not represent provider-account approval or remaining provider funds.

## 17. Admission check for a new request

Ignoring an already-locked state, a new request is checked in two stages.

First, whether the request itself would cross the configured local threshold:

```text
posted_local_estimated_spend + new_preflight_estimate > local_pacing_threshold
```

If true, the local pacing state locks and that routed request is not sent upstream.

Second, whether concurrent in-flight reservations temporarily consume the remaining local threshold capacity:

```text
posted_local_estimated_spend
+ existing_inflight_preflight_estimate
+ new_preflight_estimate
> local_pacing_threshold
```

If true only because of other active reservations, TokenTotals returns a temporary pacing hold (`429`) rather than permanently locking the daemon.

## 18. Turn Notice comparison

When a positive Turn Notice threshold is configured:

```text
notice_fires when estimated_turn_or_preflight_cost >= turn_notice_threshold_usd
```

Preflight and completed-turn notices remain distinct because preflight is input-side only while the completed event can include response-dependent billing categories.

## 19. What TokenTotals does not calculate

TokenTotals does not fabricate:

- authoritative provider account balance or credits remaining;
- taxes, negotiated discounts, private contract pricing, or provider-side adjustments unless explicitly modeled from legitimate telemetry/rules;
- context-window occupancy when no defensible normalized current-context and model-limit source exists;
- a dollar-savings percentage merely from cache-token percentage;
- model quality/equivalence from price;
- missing thinking, cache, tool, modality, or token categories as zero.

## 20. Where to verify the rules

The machine-readable pricing rules live in:

- `pricing/openai_registry.json`
- `pricing/anthropic_registry.json`
- `pricing/google_registry.json`

The provider calculators that apply those rules are:

- `openai_pricing.py`
- `anthropic_pricing.py`
- `google_pricing.py`

The presentation arithmetic described above is implemented primarily in:

- `config_manager.py`
- `turn_ledger.py`
- `telemetry_view.py`
- `proxy_server.py`

That split is intentional: provider billing mechanics remain provider-specific, while the thread/turn presentation math stays explicit and inspectable.
