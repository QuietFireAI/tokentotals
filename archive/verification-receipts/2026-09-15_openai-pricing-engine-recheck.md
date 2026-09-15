# OpenAI Pricing Engine Recheck Receipt

**Date:** 2026-09-15  
**Repository:** `QuietFireAI/tokentotals`  
**Scope:** OpenAI pricing source-of-truth, telemetry handling, estimation boundary, and public wording  
**Disposition:** Accepted for this scope with explicit limitations; not represented as an invoice mirror

## Governing accuracy rule

TokenTotals is a **best-effort cost-estimation and pacing system**. It is not an upstream billing mirror and must never imply that it reproduces a provider invoice exactly.

The target is to get as close as reasonably possible using the billing-relevant information available at calculation time:

- observed API usage telemetry;
- resolved model identity;
- provider-published pricing references;
- cache and cache-write information when exposed;
- output and reasoning usage when exposed;
- service/processing tier when it can be resolved;
- context-length rules and multipliers when known;
- hosted-tool or other separately priced activity when detectable;
- other provider-specific billing mechanics represented by the local registry.

AI pricing is increasingly cloud-like and AWS-like rather than a single static token rate. Account-specific pricing, negotiated contracts, credits, taxes, regional rules, delayed or omitted telemetry, promotional windows, and provider-side adjustments can cause a local estimate to differ from the final invoice.

The arithmetic can be exact for known inputs. **The completeness of the billing inputs cannot be assumed.** The provider invoice and account records remain authoritative.

## Original failure path

At the start of this audit item:

- `MODEL_COMPARISON_MATRIX.md` described costs as normalized against official developer API pricing registries.
- `pricing_sync.py` actually pulled a LiteLLM public model-price registry.
- `proxy_server.py` did not use that synchronized file as its OpenAI source of truth.
- `proxy_server.py` pointed to a machine-specific external pricing-engine path.
- If that import failed, hard-coded GPT-4o-like fallback rates could be used.
- The fallback represented input cost only.
- Public wording included a claim that pricing was audited live directly from provider documentation.
- The README further claimed API responses contained everything required to calculate exact spend and reduced the billing model to token count multiplied by one published rate.

Those statements and paths were too strong for a pricing environment with multiple token categories, processing tiers, context multipliers, hosted tools, promotional pricing, and account-specific conditions.

## Implemented repair

### 1. Versioned OpenAI reference registry

Added `pricing/openai_registry.json`.

The registry is dated and versioned. It contains model aliases, token-category rates, applicable long-context rules, supported processing-tier multipliers, source metadata, and pricing caveats. It explicitly treats pricing as reference data that requires re-verification over time.

Unknown models do not receive an invented price.

### 2. Telemetry-driven OpenAI calculator

Added `openai_pricing.py`.

The calculator normalizes both Responses-style and Chat-Completions-style usage fields and separates, when available:

- uncached input;
- cached input;
- cache-write input;
- output;
- reasoning-token telemetry;
- audio-token telemetry;
- long-context rules;
- service-tier handling;
- hosted-tool activity.

Reasoning tokens are observed but are not charged a second time when they are already part of billed output usage.

### 3. Refusal to manufacture precision

The calculator returns an incomplete result rather than asserting a complete all-in total when material pricing information is unresolved, including:

- unknown OpenAI model;
- unsupported or unverified service tier;
- unresolved `auto` tier where the response does not disclose the actual resolved tier;
- text registry receiving audio-token usage;
- reported cache-write usage without a verified cache-write rate;
- hosted OpenAI tool activity that may carry charges beyond model-token pricing;
- inconsistent usage telemetry where cached plus cache-write input exceeds total input.

### 4. Proxy integration

`proxy_server.py` now routes supported OpenAI response accounting through the repo-contained OpenAI calculator first. LiteLLM `response_cost` remains a fallback when the verified local calculator cannot produce a complete total.

Non-OpenAI pricing remains on the legacy path pending separate provider-specific diagnosis. This receipt does **not** certify Anthropic or Google pricing.

### 5. Public wording corrected

Updated:

- `README.md`
- `MODEL_COMPARISON_MATRIX.md`
- dashboard pricing wording in `proxy_server.py`

The public description now states that TokenTotals provides best-effort estimates from available telemetry and versioned pricing rules. Static comparison tables are labeled as dated examples rather than permanent or complete pricing truth.

The README now explicitly notes AWS-like/cloud-like pricing dimensions such as caching, cache writes, processing tiers, long-context rules, hosted tools, batch modes, account-specific rates, negotiated discounts, credits, taxes, missing telemetry, and pricing changes.

## Focused regression evidence

A focused local unit suite was run against the OpenAI pricing module/registry logic after the final hardening pass.

**Result: 13 tests run / 13 passed.**

Covered cases:

1. Standard GPT-5.6 Sol calculation with cached input and reasoning telemetry.
2. GPT-6 Astra cache-write accounting.
3. Long-context multiplier application.
4. Fast-tier multiplier application.
5. `auto` is not treated as a fixed pricing multiplier.
6. Unknown models do not receive guessed totals.
7. Chat Completions usage-shape normalization.
8. Unsupported service tier refuses an all-in total.
9. Audio usage marks the text-only result incomplete.
10. Unresolved response tier for `auto` refuses an all-in total.
11. Explicit default tier remains calculable when otherwise complete.
12. Detected hosted-tool activity refuses a token-only all-in total.
13. Request-side hosted-tool hint refuses a token-only all-in total.

## Important limitations still open

This receipt does **not** prove invoice parity and should never be cited as doing so.

The following remain outside this completed item:

- live end-to-end reconciliation against an actual OpenAI invoice/account ledger;
- complete per-tool pricing for every hosted OpenAI feature;
- Batch API all-in accounting;
- contract/enterprise/private pricing;
- credits, taxes, regional adjustments, or account-specific discounts;
- Anthropic provider-specific pricing engine;
- Google provider-specific pricing engine;
- any provider pricing change after the registry verification date.

Those should be diagnosed and implemented as separate items under the same rule: diagnose first, make the smallest defensible change, test/recheck, preserve the receipt, then continue.

## Audit conclusion

The OpenAI path is materially safer than the starting state because it no longer assumes that one token rate or one third-party catalog is equivalent to the provider's final billing model. It now prefers observed telemetry plus versioned provider rules, and it deliberately declines false precision when a billing-relevant dimension is missing.

**Accepted wording:** best-effort estimate / local cost meter / pacing telemetry.  
**Rejected wording:** exact spend / billing mirror / invoice replica / complete permanent price truth.
