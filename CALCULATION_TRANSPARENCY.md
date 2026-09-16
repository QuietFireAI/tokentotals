# TokenTotals Calculation Transparency

TokenTotals is designed to be checkable. When it derives a number rather than merely relaying provider telemetry, the arithmetic should be understandable from the documentation and reproducible from the same inputs.

This document describes both:

1. calculations currently used by the runtime; and
2. additional metrics that are already calculable from the telemetry TokenTotals now records but are **not yet surfaced as product features**.

It is not a substitute for a provider invoice, and it does not imply that every provider exposes every billing dimension on every response.

## 1. The telemetry was often already there

LLM providers already expose many useful ingredients through supported APIs, SDKs, and response-usage objects: token counts, cache categories, reasoning/thinking usage, model identity, service tier, tool metadata, latency-adjacent timing, and other billing-relevant fields.

What developers often do **not** receive is one normalized, retained, turn-by-turn, cross-model receipt that combines those ingredients, reconciles them, applies documented pricing mechanics, preserves missing-data semantics, and makes the arithmetic inspectable.

That is the TokenTotals layer.

**The data is often there. The usable receipt usually isn't. TokenTotals makes one.**

TokenTotals does not scrape private endpoints, decrypt traffic, extract hidden model state, or invent fields a provider did not expose. The calculations below use supported telemetry plus versioned public pricing rules.

## 2. Three classes of data

TokenTotals keeps three concepts separate:

- **Observed** — a value exposed by the provider/client response or other supported runtime telemetry.
- **Derived** — arithmetic TokenTotals performs on observed values and versioned pricing rules.
- **Unavailable** — a value TokenTotals cannot defensibly reconstruct. Missing is not converted to zero.

The provider's final invoice and account records remain authoritative.

---

# Calculations currently used by TokenTotals

## 3. Preflight token estimate

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

## 4. Preflight estimated input cost

For a dedicated provider engine, TokenTotals resolves the requested model against the versioned provider registry and applies the provider-specific input rule.

The basic component shape is:

```text
estimated_input_cost = (estimated_input_tokens / 1,000,000) × effective_input_rate_per_million
```

Where a verified provider rule requires a modifier:

```text
effective_input_rate = base_input_rate × verified_modifier
```

For a provider outside the dedicated engines, TokenTotals may use an **exact model key** from the pinned LiteLLM catalog:

```text
estimated_input_cost = estimated_input_tokens × LiteLLM_input_cost_per_token
```

If no defensible preflight price exists, TokenTotals returns pricing unavailable rather than inventing a universal rate.

## 5. Post-response estimated cost components

When response telemetry is available, TokenTotals prices the billing categories exposed for that provider/model. Each known token-priced component follows:

```text
component_cost = (billable_units / 1,000,000) × applicable_rate_per_million
```

For per-request hosted tools or similar unit-priced features:

```text
component_cost = observed_request_count × applicable_per_request_rate
```

Separately modeled categories can include, when applicable and exposed:

- uncached/base input;
- cached input / cache read;
- cache write or cache creation;
- output;
- reasoning/thinking where provider billing semantics require separate handling;
- modality-specific units such as audio;
- hosted/server-tool request charges;
- verified service/processing-tier, geography, speed, long-context, or batch modifiers.

The estimated turn total is:

```text
estimated_turn_cost = Σ(all defensibly priced billing components)
```

TokenTotals labels that result `complete` only when the provider engine has enough telemetry to account for all billing dimensions it knows are required for that turn. Otherwise the estimate remains explicitly incomplete and may use a disclosed fallback basis such as LiteLLM response cost or a known list-equivalent estimate where defensible.

The ledger stores the component map in `pricing_components_usd`, alongside `estimated_cost_usd`, `cost_basis`, `estimate_complete`, and the pricing-registry verification date.

## 6. Cached-input share

TokenTotals does **not** equate cached-token percentage with dollar savings percentage.

When both input and cached-input counts are available:

```text
cached_input_share_pct = (cached_input_tokens / input_tokens) × 100
```

Example:

```text
32,768 cached / 34,521 input × 100 = 94.92%
```

Dollar effect depends on the provider/model's actual cached-input rate and other billing mechanics.

## 7. Uncached input

A common provider shape is:

```text
uncached_input_tokens = input_tokens - cached_input_tokens
```

Where cache-write/create tokens are separately represented inside the input basis:

```text
uncached_input_tokens = input_tokens - cached_input_tokens - cache_write_tokens
```

The ledger records whether the resulting field is observed, derived, or unavailable.

## 8. Reconstructed total tokens

Where normalized input and output are both known:

```text
reconstructed_total_tokens = input_tokens + output_tokens
```

Provider-specific normalization prevents known subcategories such as reasoning/thinking from being double-counted when they are already included in a provider's output total.

## 9. Reconciliation delta and unclassified tokens

When both provider-reported total and reconstructed total exist:

```text
reconciliation_delta_tokens = provider_reported_total_tokens - reconstructed_total_tokens
```

For provider shapes where a positive residual represents unattributed usage:

```text
unclassified_tokens = max(0, reconciliation_delta_tokens)
```

A non-zero residual is preserved rather than silently forcing totals to match.

## 10. Output token wall-clock rate

When output tokens and elapsed callback time are known:

```text
output_tokens_per_wall_second = output_tokens / (latency_ms / 1000)
```

This is a **wall-clock rate**, not pure model generation throughput. Queueing, network, provider processing, transport, and callbacks can contribute to elapsed time.

## 11. Turn-size statistics

For each turn, TokenTotals prefers the provider-reported total token count when available; otherwise it uses the reconstructed total.

```text
sum = Σ(turn_total_tokens)
average = sum / sampled_turn_count
median = standard statistical median
max = largest sampled turn total
```

P95 uses nearest-rank:

```text
rank = ceil(0.95 × sample_count)
p95 = sorted_values[rank - 1]
```

Coverage is reported separately so a partial sample cannot masquerade as complete thread coverage.

## 12. Token-field coverage

For each token category in a thread:

```text
coverage = unavailable, if observed_turns = 0
coverage = complete,    if observed_turns = total_turns
coverage = partial,     otherwise
```

When zero turns expose the field, the displayed sum is withheld rather than rendered as zero.

## 13. Estimated-cost coverage

For a thread or model group:

```text
estimated_cost_usd = Σ(costed_turn_estimates)
```

```text
coverage = unavailable, if costed_turns = 0
coverage = complete,    if costed_turns = total_turns
coverage = partial,     otherwise
```

## 14. Posted local estimated spend

When a completed routed turn settles:

```text
posted_local_estimated_spend = prior_posted_local_estimated_spend + settled_turn_estimate
```

Internal accumulation retains greater precision than the four-decimal human display so micro-cost turns do not disappear through repeated display rounding.

Duplicate success callbacks carrying the same server-owned reservation ID are ignored for settlement.

## 15. In-flight preflight estimate

For currently admitted but unsettled requests:

```text
inflight_preflight_estimate = Σ(active_reservation_estimated_input_cost)
```

Reservations are process-local and ephemeral. They are not persisted as actual spend.

## 16. Combined local estimate

```text
combined_local_estimate = posted_local_estimated_spend + inflight_preflight_estimate
```

This is a local pacing quantity, not a provider balance or credit-line reading.

## 17. Local threshold percentages

For a positive configured local pacing threshold:

```text
posted_threshold_pct = (posted_local_estimated_spend / local_pacing_threshold) × 100
combined_threshold_pct = (combined_local_estimate / local_pacing_threshold) × 100
```

The tray/dashboard traffic light is derived from local threshold state and the configured warning percentage. It does not represent provider-account approval or remaining provider funds.

## 18. Admission check for a new request

Ignoring an already-locked state, TokenTotals first checks whether the request itself would cross the local threshold:

```text
posted_local_estimated_spend + new_preflight_estimate > local_pacing_threshold
```

Then it checks whether active concurrent reservations temporarily consume the available local threshold capacity:

```text
posted_local_estimated_spend
+ existing_inflight_preflight_estimate
+ new_preflight_estimate
> local_pacing_threshold
```

If the second condition is true only because of other active reservations, TokenTotals returns a temporary pacing hold (`429`) rather than permanently locking the daemon.

## 19. Turn Notice comparison

When a positive Turn Notice threshold is configured:

```text
notice_fires when estimated_turn_or_preflight_cost >= turn_notice_threshold_usd
```

Preflight and completed-turn notices remain distinct because preflight is input-side only while the completed event can include response-dependent billing categories.

---

# Metrics already calculable from the current ledger but not yet surfaced

The metrics below require **no new private telemetry source**. They can already be derived from fields TokenTotals stores today, subject to the same observed/derived/unavailable and coverage rules.

They are documented here as **currently calculable, not currently promised product surfaces**. Their inclusion here is not a commitment to add every metric to the dashboard.

## 20. Input composition percentages

When total input and the relevant category are available:

```text
uncached_input_share_pct = (uncached_input_tokens / input_tokens) × 100
cached_input_share_pct   = (cached_input_tokens / input_tokens) × 100
cache_write_share_pct    = (cache_write_tokens / input_tokens) × 100
tool_input_share_pct     = (tool_input_tokens / input_tokens) × 100
```

The categories must use the provider's normalized token basis; percentages should not be added together unless the categories are known to be mutually exclusive for that provider shape.

## 21. Output / reasoning composition

When the provider exposes reasoning/thinking and its relationship to output is known:

```text
reasoning_share_of_output_pct = (reasoning_tokens / output_tokens) × 100
non_reasoning_output_tokens = output_tokens - reasoning_tokens
```

This metric must not be emitted for provider shapes where `output_tokens` and `reasoning_tokens` are not on a compatible basis.

## 22. Input-to-output ratio

```text
input_output_ratio = input_tokens / output_tokens
```

or, expressed in the opposite direction:

```text
output_input_ratio = output_tokens / input_tokens
```

A zero denominator makes the ratio unavailable rather than infinite.

## 23. Unclassified-token share

Where provider total and residual/unclassified tokens are available:

```text
unclassified_share_pct = (unclassified_tokens / provider_reported_total_tokens) × 100
```

This can expose normalization gaps that a single provider total would otherwise hide.

## 24. Reconciliation accuracy of the token anatomy

This is **not billing accuracy**. It measures only how much of a provider-reported token total TokenTotals can classify into known categories.

When provider total is positive:

```text
classified_tokens = provider_reported_total_tokens - unclassified_tokens
classified_token_share_pct = (classified_tokens / provider_reported_total_tokens) × 100
```

Example:

```text
provider total     = 610,000
unclassified       =   5,000
classified         = 605,000
classified share   = 99.18%
```

This must never be relabeled as `99.18% billing accuracy`.

## 25. Turn-to-turn token delta

For adjacent turns with comparable selected totals:

```text
token_delta = current_turn_total_tokens - prior_turn_total_tokens
```

Percentage change:

```text
token_delta_pct = (token_delta / prior_turn_total_tokens) × 100
```

If the prior turn total is zero or unavailable, percentage change is unavailable.

## 26. Turn-to-turn estimated-cost delta

For adjacent costed turns:

```text
cost_delta_usd = current_turn_estimated_cost - prior_turn_estimated_cost
```

```text
cost_delta_pct = (cost_delta_usd / prior_turn_estimated_cost) × 100
```

This should inherit the completeness/basis labels of both turns.

## 27. Cumulative tokens through turn N

```text
cumulative_tokens_N = Σ(selected_turn_total_tokens for turns 1..N)
```

Coverage must accompany the number when one or more turns lack a defensible total.

## 28. Cumulative estimated cost through turn N

```text
cumulative_estimated_cost_N = Σ(costed_turn_estimates for turns 1..N)
```

Again, this is only a full thread estimate when cost coverage is complete.

## 29. Average / median / P95 / max estimated cost per turn

For costed turns:

```text
average_turn_cost = Σ(turn_cost) / costed_turn_count
median_turn_cost  = statistical median(turn_costs)
max_turn_cost     = max(turn_costs)
```

P95 nearest-rank:

```text
rank = ceil(0.95 × costed_turn_count)
p95_turn_cost = sorted_turn_costs[rank - 1]
```

Cost coverage must be displayed alongside these statistics.

## 30. Blended estimated cost per 1K tokens

When both a defensible selected token total and estimated turn cost are available:

```text
blended_estimated_cost_per_1k_tokens =
    (estimated_turn_cost / selected_turn_total_tokens) × 1,000
```

This is a descriptive blended result for that turn. It is **not** a provider list rate because it can combine input, cache, output, reasoning, tool, tier, and other components.

## 31. Estimated cost per 1K input tokens

Where input tokens are positive:

```text
estimated_cost_per_1k_input_tokens =
    (estimated_turn_cost / input_tokens) × 1,000
```

This is also a blended workload measure, not an input-list-price substitute.

## 32. Estimated cost per 1K output tokens

Where output tokens are positive:

```text
estimated_cost_per_1k_output_tokens =
    (estimated_turn_cost / output_tokens) × 1,000
```

Useful for comparing generation-heavy turns, but still a blended workload metric.

## 33. Cache price differential — not claimed savings

When a provider/model has verified base-input and cached-input rates on the same token basis:

```text
cache_rate_differential_usd =
    (cached_input_tokens / 1,000,000)
    × (base_input_rate - cached_input_rate)
```

This describes the **rate differential associated with observed cached tokens**.

It must not automatically be called `savings`, because TokenTotals cannot prove that the counterfactual alternative would have processed exactly those same tokens uncached under otherwise identical conditions.

## 34. Turn share by model

For a mixed-model thread:

```text
model_turn_share_pct = (turns_for_model / total_thread_turns) × 100
```

## 35. Token share by model

Where the relevant totals have compatible coverage:

```text
model_token_share_pct = (tokens_for_model / total_thread_tokens) × 100
```

This can be calculated for all selected tokens or for a specific category such as input, output, cache, or reasoning.

## 36. Estimated-cost share by model

Where cost coverage is comparable:

```text
model_estimated_cost_share_pct =
    (estimated_cost_for_model / total_thread_estimated_cost) × 100
```

A partial denominator must be labeled partial rather than treated as the full thread cost.

## 37. Distinct model/provider count

```text
distinct_model_count = count(unique canonical model identities in thread)
distinct_provider_count = count(unique providers in thread)
```

## 38. Model-switch count

For an ordered thread ledger:

```text
model_switch_count = count(turn i where model_i != model_(i-1))
```

Provider-switch count can be calculated the same way using provider identity.

## 39. Model-switch timeline

For each switch:

```text
switch_event = {
    turn_id,
    timestamp,
    prior_model,
    new_model
}
```

This is a factual event sequence, not a judgment about whether the switch was good or bad.

## 40. Thread elapsed duration

When first and last settled timestamps are present:

```text
thread_elapsed_seconds = last_turn_timestamp - first_turn_timestamp
```

This is wall-clock elapsed span, which can include idle user time.

## 41. Turns per wall-clock hour

```text
turns_per_hour = total_turns / (thread_elapsed_seconds / 3600)
```

Because idle time may be included, this is thread activity density rather than pure model throughput.

## 42. Tokens per wall-clock hour

```text
tokens_per_hour = selected_thread_tokens / (thread_elapsed_seconds / 3600)
```

Coverage and idle-time caveats apply.

## 43. Estimated cost per wall-clock hour

```text
estimated_cost_per_hour =
    thread_estimated_cost / (thread_elapsed_seconds / 3600)
```

This is **retrospective burn rate**, not permission to spend and not a prediction of future provider charges.

TokenTotals should not turn this metric into `runway` or `money remaining` without a separately justified future-looking model.

## 44. Average / median / P95 latency

For turns with latency observations:

```text
average_latency_ms = Σ(latency_ms) / latency_observed_turns
median_latency_ms  = statistical median(latency_ms)
p95_latency_ms     = nearest-rank P95(latency_ms)
max_latency_ms     = max(latency_ms)
```

Latency coverage should accompany the result.

## 45. Thread output-token wall-clock rate statistics

For turns where `output_tokens_per_wall_second` is calculable:

```text
average_output_rate = average(turn_output_rates)
median_output_rate  = median(turn_output_rates)
p95_output_rate     = nearest-rank P95(turn_output_rates)
max_output_rate     = max(turn_output_rates)
```

These remain wall-clock rates, not pure provider generation-speed measurements.

## 46. Category totals by provider/model

For any normalized token category `C`:

```text
category_total_for_model = Σ(C on turns for that model)
category_total_for_provider = Σ(C on turns for that provider)
```

Examples include:

- input;
- uncached input;
- cached input;
- cache write/create;
- output;
- reasoning/thinking;
- tool input;
- unclassified/residual tokens.

Each sum retains its own observed-turn count and coverage state.

## 47. Category mix across a thread

When categories use a compatible denominator:

```text
category_share_pct = (category_tokens / selected_thread_token_basis) × 100
```

This can describe how much of a thread's observable token activity was input, output, cached input, reasoning, tool input, or residual/unclassified usage.

The denominator must be explicitly named. TokenTotals should never present a percentage without making that basis clear.

## 48. Largest observed turn

```text
largest_turn = argmax(selected_turn_total_tokens)
```

The result can include its turn ID, timestamp, model/provider, token anatomy, latency, and estimated cost basis without storing prompt/response content.

## 49. Largest estimated-cost turn

Among costed turns:

```text
largest_cost_turn = argmax(estimated_turn_cost)
```

Cost completeness/basis remains attached to that turn.

## 50. Above-local-reminder count

Given a user-selected Turn Notice threshold:

```text
notice_eligible_turn_count =
    count(costed turns where estimated_turn_cost >= turn_notice_threshold_usd)
```

This is an event count, not a budget metric.

## 51. Complete / incomplete / unavailable estimate counts

```text
complete_estimate_count   = count(turns with complete provider calculation)
incomplete_estimate_count = count(turns with known but incomplete/fallback estimate)
unavailable_estimate_count = count(turns with no defensible cost estimate)
```

Percentages can be derived from total turns:

```text
complete_estimate_share_pct =
    (complete_estimate_count / total_turns) × 100
```

This is an estimate-coverage statistic, not invoice-accuracy percentage.

## 52. Cost-basis distribution

For the ledger's explicit `cost_basis` labels:

```text
basis_count[basis] = count(turns carrying that cost_basis)
```

Potential basis categories include complete provider-registry calculation, LiteLLM response-cost fallback, known list-equivalent, or unavailable/no defensible cost.

A thread can therefore show **where its estimates came from**, not merely a dollar total.

## 53. Registry verification-age indicator

Given a ledger turn timestamp and its pricing-registry verification date:

```text
registry_age_days = turn_date - registry_verified_date
```

This does not prove a price changed. It simply exposes how old the verification basis was when the calculation was made.

## 54. Per-turn component share of estimated cost

For a complete costed turn and component `X`:

```text
component_cost_share_pct =
    (component_cost_X / estimated_turn_cost) × 100
```

Examples can include input, cached input, output, reasoning-related output treatment, hosted tools, or other provider-specific components.

This can make visible which billing dimension actually dominated a turn.

---

# Metrics intentionally not claimed yet

## 55. Context-window occupancy

TokenTotals does not currently claim:

```text
context_occupancy_pct = current_context_tokens / model_context_limit × 100
```

because the repo does not yet have one defensible normalized source for both current effective context and applicable model limit across all supported providers.

Input-token count is **not** automatically equivalent to live context occupancy.

## 56. Provider account balance / credits remaining

Not calculated. TokenTotals does not know enough about provider subscriptions, prepaid credits, negotiated contracts, invoices, taxes, or account adjustments to assert authoritative remaining funds.

## 57. Financial runway / safe amount for the next turn

Not claimed. A local threshold does not prove how much the next turn will cost, and final output/tool/reasoning charges can exceed the input-side preflight estimate.

## 58. Invoice accuracy percentage

Not claimed from telemetry alone.

A statement such as `97% accurate` would require empirical comparison against authoritative provider billing records over a defined workload/population. Token classification coverage is not billing accuracy.

## 59. Cache savings percentage

Not inferred from cache share.

TokenTotals may calculate the observed cache **rate differential** when the required pricing basis is known, but it does not claim a counterfactual savings percentage without evidence that the alternative workload would otherwise have been identical.

## 60. Model quality, equivalence, or recommendation

Not inferred from token or cost telemetry. Those questions belong, if developed, in the separate opt-in Community Labs counterfactual track with explicit assumptions and evidence.

---

# Provider-specific arithmetic remains provider-specific

## 61. Why one universal token equation is not enough

Different providers and models can apply different rules for:

- cached reads;
- cache creation/write durations;
- thinking/reasoning inclusion;
- service/processing tiers;
- long context;
- geography;
- batch/flex/priority/fast processing;
- audio/image/video modalities;
- search/maps grounding;
- hosted tools and per-request charges;
- promotional pricing windows.

TokenTotals therefore normalizes the presentation layer while leaving provider billing mechanics inside the provider-specific calculators and registries.

## 62. Where to verify the rules

Machine-readable pricing rules:

- `pricing/openai_registry.json`
- `pricing/anthropic_registry.json`
- `pricing/google_registry.json`

Provider calculators:

- `openai_pricing.py`
- `anthropic_pricing.py`
- `google_pricing.py`

Telemetry/presentation arithmetic:

- `config_manager.py`
- `turn_ledger.py`
- `telemetry_view.py`
- `proxy_server.py`

Community corrections and proposed math changes:

- `CONTRIBUTING.md`

Verification history:

- `archive/verification-receipts/`

That split is intentional: provider billing mechanics remain provider-specific, thread/turn arithmetic stays inspectable, and historical evidence remains preserved even when a later review improves the math.
