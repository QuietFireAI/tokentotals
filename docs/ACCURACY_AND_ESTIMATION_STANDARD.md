# TokenTotals Accuracy & Estimation Standard

**Status:** normative documentation rule  
**Applies to:** all providers, models, dashboards, receipts, README claims, APIs, reports, and UI copy  
**Principle:** TokenTotals calculates the most accurate independent cost estimate reasonably possible from the telemetry and pricing rules available for a transaction. It is not the provider's invoice and must never imply otherwise.

## Required public wording

When TokenTotals describes its accuracy, the statement must preserve all three ideas below:

> **TokenTotals produces the most accurate independent cost estimate it can from the request/response telemetry available to the user and the provider's published pricing rules. Actual provider billing can differ when a pricing dimension is unavailable, ambiguous, account-specific, promotional, region-specific, time-dependent, or changed by the provider. TokenTotals therefore reports the calculation basis and confidence level instead of presenting an estimate as a provider invoice.**

Do not shorten this into claims such as `exact billing`, `exact spend`, `identical to invoice`, or `100% billing accuracy` unless a future provider-supported reconciliation mechanism actually proves those claims.

## Particulars that can affect accuracy

Documentation must disclose the applicable particulars whenever pricing accuracy is discussed. Not every provider or model uses every dimension, but TokenTotals must account for any dimension that applies.

### Model identity

- requested model name;
- provider-resolved model name;
- model snapshot/version;
- aliases and routing names;
- model substitutions or automatic routing;
- preview/beta versus generally available SKU;
- provider changes to a model behind a stable alias.

### Token and usage telemetry

- input/prompt tokens;
- output/completion tokens;
- cached-input/read tokens;
- cache-write/creation tokens;
- reasoning/thinking token details when separately exposed;
- total-token counters;
- whether detail counters overlap or partition another counter;
- whether usage is reported incrementally or only at completion;
- missing usage on interrupted/failed/streaming responses;
- provider rounding or minimum-billing units.

### Context and request shape

- context-window/input-token thresholds;
- long-context pricing bands;
- maximum requested output;
- actual output generated;
- system/developer/user/tool messages included in metering;
- attachments/files/images/audio/video included in the request;
- provider-specific tokenization and media metering rules.

### Processing/service mode

- Standard/default processing;
- Batch;
- Flex;
- Fast/Priority/low-latency modes;
- reserved/provisioned throughput where applicable;
- automatic service-tier selection;
- the tier requested versus the tier actually reported by the provider.

### Region and data-residency rules

- global versus regional processing;
- geographic uplifts/discounts;
- data-residency options;
- endpoint/region selection;
- account or organization settings that change processing location.

### Caching

- cached-input reads;
- cache writes/creation;
- cache duration classes;
- cache eligibility thresholds;
- automatic versus explicit caching;
- cache-hit telemetry actually returned by the provider;
- provider-specific discounts or surcharges.

### Modalities

- text input/output;
- audio input/output;
- image input/output;
- video generation/input where applicable;
- transcription/translation minutes;
- modality-specific tokens, seconds, pixels, frames, resolutions, or other published units.

### Tools and hosted features

- web-search calls;
- search-content tokens;
- file-search calls;
- code-interpreter/container sessions;
- container size/runtime;
- computer-use or hosted-tool charges when published;
- storage used by hosted tools;
- vector/file indexing charges;
- any provider-hosted tool whose fee is separate from model tokens.

### Storage and time-based meters

- GB-day;
- GB-month;
- GB-minute;
- seconds/minutes/hours of runtime;
- live/realtime session duration;
- training hours;
- inference time where the provider bills by time rather than tokens.

### Fine-tuning and custom-model costs

- training tokens;
- training hours;
- hosted model storage;
- fine-tuned inference input/output rates;
- grader or reinforcement-learning charges;
- account-specific fine-tuning terms.

### Commercial and temporal pricing conditions

- effective date of the price;
- scheduled future price changes;
- temporary promotions;
- free tiers/credits that affect invoice amount but are not intrinsic model cost;
- contract/account-specific negotiated pricing;
- enterprise commitments/reserved capacity;
- volume discounts;
- taxes, currency conversion, and payment-processing effects outside TokenTotals' model-cost calculation;
- provider price changes that occur after TokenTotals' last verified catalog update.

### Failures, retries, and partial work

- failed requests that still incur provider charges;
- retries generated by clients/agents;
- provider-side retries or duplicated transactions when observable;
- partial streaming responses;
- cancelled jobs;
- asynchronous jobs completed after the local transaction view;
- usage that is not returned through the proxied endpoint.

## Confidence labels

TokenTotals must visibly distinguish the following states:

- **PROVIDER_RULE_ESTIMATE** — all material pricing dimensions required for the supported calculation were observed and matched to a verified effective-dated rule.
- **CONSERVATIVE_APPROXIMATION** — one or more dimensions were unavailable or ambiguous, so a documented high-side assumption was used.
- **UNRECONCILED** — the transaction occurred but there is not yet enough trustworthy telemetry to reconcile the reservation with observed usage.
- **UNKNOWN** — TokenTotals has no defensible calculation basis. Do not display a precise dollar total.

A provider-rule estimate is still an independent estimate, not a provider invoice.

## Fallback rule

Missing data must never be converted silently into an apparently exact number.

For budget protection, TokenTotals may use a conservative fallback:

1. exact model known, pricing dimension unknown -> highest verified applicable rate for that model and unit;
2. provider known, model unknown -> highest verified comparable provider rate for that modality/unit;
3. provider/model unknown but comparable supported meter exists -> highest verified comparable supported rate;
4. no defensible comparable rate -> `UNKNOWN`; strict mode blocks egress, conservative mode may reserve only if a documented worst-case basis exists.

Every fallback must record:

- the missing field;
- the fallback rule chosen;
- the source pricing record;
- the assumed rate;
- the resulting reservation/estimate;
- the confidence label.

## Calculation provenance

Every expandable TokenTotals receipt should identify, where applicable:

- provider;
- requested and resolved model;
- endpoint;
- raw provider usage field;
- normalized billing event;
- observed quantity;
- billing unit;
- service tier;
- context band;
- region/data-residency status;
- modality;
- tool/storage/runtime meter;
- base rate;
- every modifier;
- effective rate;
- line-item arithmetic;
- source URL;
- source verification/effective date;
- whether the value is observed, derived, assumed, or unknown;
- confidence status.

## Communication rule

Whenever documentation, marketing copy, UI text, or a technical report makes an accuracy statement, it must make clear that TokenTotals is **as accurate as the available telemetry and published rules allow**, subject to the particulars above. A short UI label may link to this standard, but the underlying documentation must enumerate the relevant dimensions instead of hiding them behind phrases such as `fees may vary`.

The purpose of this disclosure is not to weaken TokenTotals' claim. It is to make the claim auditable: every known variable is either measured, derived under a documented rule, conservatively approximated, or explicitly unknown.
