# OpenAI Billing Contract for TokenTotals

**Status:** reference design for implementation  
**Provider:** OpenAI  
**Verified:** 2026-09-14  
**Primary pricing source:** https://developers.openai.com/api/docs/pricing  
**API reference source:** https://developers.openai.com/api/reference/resources/responses

## 1. Governing rule

TokenTotals does not invent OpenAI prices. It observes the user's own request/response telemetry, maps that telemetry into canonical billable events, and applies a dated OpenAI pricing rule.

Every displayed total must be reproducible from:

1. observed request/response fields;
2. a versioned pricing/rule record;
3. explicit arithmetic;
4. a confidence/status label.

If a field required for an exact provider-rule estimate is unavailable, TokenTotals must preserve the uncertainty. It may reserve a conservative amount for safety, but it must label that amount as an approximation.

## 2. Transaction identity fields

Capture these whenever they are available without modifying the upstream transaction:

- `provider`: `openai`
- `endpoint`
- `request_id` / response id
- `requested_model`
- `resolved_model` from the response
- `model_snapshot` when the provider returns one
- `service_tier_requested`
- `service_tier_actual`
- `regional_processing`: known / false / unknown
- `request_started_at`
- `response_completed_at`
- `streaming`
- `response_status`

`service_tier_actual` controls post-response pricing when OpenAI returns it. The request value is retained only as provenance because OpenAI documents that the response tier can differ from the requested tier.

## 3. Token telemetry

For the Responses API, preserve the raw usage object before normalization.

Canonical fields currently include:

- `input_tokens`
- `input_tokens_details.cached_tokens`
- `input_tokens_details.cache_write_tokens`
- `output_tokens`
- `output_tokens_details.reasoning_tokens`
- `total_tokens`

TokenTotals stores `reasoning_tokens` as explanatory telemetry. It must not add reasoning tokens on top of `output_tokens` unless OpenAI documentation for a future model explicitly establishes that they are separately billable. The API represents reasoning tokens as an output-token detail/breakdown.

### Input partition rule

The adapter should normalize input into billable events such as:

- `TEXT_INPUT_UNCACHED`
- `TEXT_INPUT_CACHED_READ`
- `TEXT_CACHE_WRITE`

Before using `input_tokens - cached_tokens - cache_write_tokens` as the uncached quantity, tests must establish that the detail fields are a non-overlapping partition for the applicable endpoint/model. If that invariant is not established, TokenTotals must not silently subtract overlapping counters. The raw provider fields remain authoritative evidence.

## 4. Current flagship text pricing dimensions

OpenAI's current flagship tables distinguish:

- model;
- short versus long context;
- Standard, Batch, Flex, and Fast processing;
- uncached input;
- cached input;
- cache writes;
- output;
- regional processing uplift where applicable.

For the current GPT-6 Astra / GPT-5.6 family, the pricing page shows Batch and Flex at 50% of Standard and Fast at 2x the applicable Standard rate. These relationships are **not** hard-coded as universal OpenAI laws. The model/rate record stores the actual published prices and effective dates so future models can differ.

Current long-context-capable flagship models use a threshold rule at more than 272,000 input tokens. The applicable model record defines the threshold and the resulting rate band. TokenTotals must not assume every OpenAI model has the same threshold or multiplier.

Regional processing for eligible models released on or after 2026-03-05 currently carries a 10% uplift. That modifier applies only when the transaction is known to use an eligible regional-processing endpoint/rule. Unknown region state is not silently treated as regional or non-regional in an exact estimate.

## 5. Service tier handling

Canonical tier values:

- `standard`
- `batch`
- `flex`
- `fast`
- `ultrafast`
- `unknown`

OpenAI currently accepts `priority` as an alias for Fast mode, while responses report `priority` for Fast/priority requests. The adapter normalizes that response value to the internal `fast` billing tier while retaining the raw value for audit.

A model manifest must explicitly state which service tiers it supports and provide rates for each supported tier. Unsupported combinations are not inferred.

## 6. Context-band handling

Each model manifest can declare zero or more context bands. Example shape:

```json
{
  "bands": [
    {"name": "short", "max_input_tokens": 272000},
    {"name": "long", "min_input_tokens": 272001}
  ]
}
```

The band is selected from observed input usage post-response and from conservative pre-flight token estimation before egress.

## 7. Multimodal billable events

OpenAI pricing includes models where text, audio, and image tokens have distinct rates. The canonical event vocabulary therefore includes:

- `TEXT_INPUT`
- `TEXT_CACHED_INPUT`
- `TEXT_CACHE_WRITE`
- `TEXT_OUTPUT`
- `AUDIO_INPUT`
- `AUDIO_CACHED_INPUT`
- `AUDIO_OUTPUT`
- `IMAGE_INPUT`
- `IMAGE_CACHED_INPUT`
- `IMAGE_OUTPUT`

The provider adapter maps endpoint-specific usage telemetry into these events only when the corresponding quantity is actually available. It must not convert media into guessed token counts when the provider exposes a better documented meter.

## 8. Non-token meters

The OpenAI pricing page also contains billable units that are not ordinary text tokens. TokenTotals needs first-class events for them rather than forcing them into token math.

Current categories include:

- GPT-Live session time (`seconds` / published per-minute rate);
- video generation (`seconds`, model and resolution dependent);
- transcription/translation (`minutes` where pricing is published per minute);
- web search (`calls`, with search-content tokens treated separately according to the applicable rule);
- file search (`calls`);
- file-search storage (`GB-day`);
- hosted containers / Code Interpreter (`container size` + billable session/runtime rule);
- Agent Kit upload storage (`GB-day`);
- fine-tuning training (`hours`) plus inference-token charges.

Canonical units must remain explicit: `tokens`, `calls`, `seconds`, `minutes`, `GB-day`, `GB-minute`, `hours`, or another documented provider meter. Never convert one unit into another merely to fit the calculator.

## 9. Tool charging

Tool cost is a separate ledger component from model-token cost.

A transaction receipt can therefore contain both:

```text
MODEL COMPUTE
  text input
  cached input
  cache writes
  output

TOOLS
  web search calls
  web-search content tokens
  file-search calls
  container runtime

STORAGE
  file-search GB-day
```

This prevents tool fees from being hidden inside a fake per-token rate.

## 10. Pricing record structure

Each OpenAI rate record should be effective-dated and auditable. Minimum dimensions:

```text
provider
model_id
model_alias_or_snapshot
endpoint_family
service_tier
context_band
modality
billing_event
unit
rate_usd
regional_modifier
valid_from
valid_until
source_url
source_checked_at
source_hash_or_change_id
status
```

The database may contain many records for one model. That is intentional. One model can have multiple rates because the billing mode, context band, modality, region, or date can change.

## 11. Calculation

After normalization, the calculator is deliberately generic:

```text
line_cost = observed_quantity × effective_rate
transaction_cost = sum(line_cost for all billable events)
```

Modifiers are resolved into the effective rate before multiplication. The receipt retains both the base rate and every modifier used.

## 12. Safety reservation versus post-response estimate

### Pre-flight

Use request-known facts plus a conservative token/output bound. If the exact billing rule cannot be identified:

1. exact model + uncertain mode -> highest applicable verified rate for that model;
2. provider known + model unknown -> highest relevant verified OpenAI rate for that modality/unit;
3. no defensible comparable rate -> block in strict mode, or reserve a clearly labeled worst-case approximation in conservative mode.

### Post-response

Reconcile the reservation using actual response telemetry and the actual returned service tier/model when available. Release unused reservation headroom.

## 13. Confidence labels

Every receipt gets one of:

- `PROVIDER_RULE_ESTIMATE` — all required usage fields and pricing dimensions were observed and matched to a verified rate record;
- `CONSERVATIVE_APPROXIMATION` — one or more pricing dimensions were missing and a documented high-side fallback was used;
- `UNRECONCILED` — a stream/request completed without enough telemetry to reconcile;
- `UNKNOWN` — no defensible rate exists; do not display a precise dollar amount.

Even `PROVIDER_RULE_ESTIMATE` is not represented as the provider's final invoice. TokenTotals is an independent calculator.

## 14. Receipt requirement

Every displayed transaction total must be expandable into line items containing:

- observed quantity;
- unit;
- canonical billing event;
- raw provider field that produced it;
- model and actual service tier;
- context band;
- base rate;
- applied modifier(s);
- line cost;
- source URL;
- source verification date;
- confidence label.

## 15. Update policy

The OpenAI source checker runs daily, but a daily check does not mean a daily production price change.

- no source change -> record successful check, no new rate version;
- source change -> parse into a candidate version;
- validation passes -> produce a human/audit diff;
- candidate is promoted only after schema/rule validation;
- parser failure -> retain the last verified catalog and mark pricing freshness degraded;
- never replace a known verified price with an invented default.

## 16. Current implementation target

The first executable OpenAI adapter should support, in order:

1. Responses API text/reasoning usage;
2. Standard / Batch / Flex / Fast service tiers;
3. short/long-context pricing;
4. regional-processing uplift;
5. cache reads and cache writes;
6. web-search and file-search call fees;
7. Realtime text/audio/image token meters;
8. remaining non-token tools/storage/media meters.

Each stage requires fixtures from documented OpenAI response shapes plus negative tests for missing/ambiguous fields before it is called supported.
