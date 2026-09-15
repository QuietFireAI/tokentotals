# Turn Telemetry Ledger Recheck Receipt

Date: 2026-09-15
Repository: `QuietFireAI/tokentotals`

## Scope

This receipt records the diagnosis, precision prerequisite, implementation, integration, documentation, unfavorable evidence, and acceptance testing for TokenTotals' local append-only turn telemetry ledger.

The goal was not to create another conversation transcript. The ledger is a local factual/derived telemetry substrate for per-turn token economics and historical thread summaries, including threads that change models mid-conversation.

Core requirements were:

- preserve billing/operational telemetry TokenTotals legitimately observes or defensibly derives;
- never silently convert missing telemetry into observed zero;
- keep requested, canonical, and provider-observed model identities distinct;
- preserve provider-reported totals and explicit residual/unclassified tokens where reconciliation is incomplete;
- preserve separate totals by model/provider inside one continuing thread;
- store cost basis/completeness instead of a bare dollar number;
- avoid prompt text, response text, API keys, hidden reasoning content, scraping, private endpoint interception, or undocumented provider-state extraction; and
- keep the file locally owned and runtime append-only without falsely claiming immutable/tamper-evident storage.

## Precision prerequisite

During ledger design, the existing local spend accumulator was found to round every completed turn to four decimal places before adding it to the cumulative state. This could erase repeated micro-cost turns; for example, repeated `$0.00004` turns could each round to `$0.0000` before accumulation.

Commit `c335a0b56bebd13fe8afae8a4e14571895d2d2a6` (`fix: retain high precision in local spend accumulation`) raised internal local money precision above the four-decimal human-facing display.

Commit `b063d95a045a60894ec04ac1f065f43042615a38` added regression coverage proving:

- 1,000 turns at `$0.00004` accumulate to `$0.0400` rather than disappearing; and
- a value such as `$0.0000412345` survives internal accumulation while the dashboard remains free to render four decimal places.

GitHub Actions run `35031456051`, job `104590677240`, passed the clean install, compile, proxy import, and **109/109 tests**.

## Ledger substrate

Commit `87c03695a3ca2f048ef04bc707160a5325f6b9df` (`feat: add append-only turn telemetry ledger`) introduced `turn_ledger.py`.

The runtime ledger path is:

`~/.tokentotals/turns.jsonl`

The writer uses an explicit schema whitelist rather than serializing arbitrary callback/request objects. The schema can preserve, when exposed or defensibly derived:

- schema/turn/thread identity;
- start/completion timestamps and latency;
- provider;
- requested, canonical, and provider-observed model identities;
- registry verification date;
- requested and observed processing/service tier where available;
- input, uncached input, cached input, cache-write/create, output, reasoning/thinking, and tool-input token categories;
- provider-reported total, TokenTotals reconstructed total, residual/unclassified tokens, and reconciliation delta;
- modality token buckets and supported server-tool counters;
- pricing components, total turn estimate, estimate completeness, and cost basis;
- cumulative local/thread estimated spend and completed-turn count after settlement.

Each normalized token category also carries a basis state of `observed`, `derived`, or `unavailable`.

### Missing does not mean zero

A calculator may internally default an absent optional category to zero for arithmetic. That does not prove the provider reported zero.

Commit `c52f00dc69a859da9daf5d77e749b26c9581179a` (`fix: preserve observed versus unavailable ledger fields`) tightened the ledger mapper so:

- an explicit provider `0` remains an observed zero;
- a missing category remains `null` / `unavailable`;
- derived values are labeled as derived rather than provider-observed; and
- provider-specific normalized calculator defaults are not blindly copied into history as observed telemetry.

Ledger historical cost summation uses integer picodollar units (`10^-12` USD) before conversion back to dollars so the history does not lose the precision already present in provider component calculations.

## Provider token anatomy

The ledger reuses the already-tested provider calculator normalization rather than creating an independent billing parser.

### OpenAI

The ledger distinguishes input, cached input, cache-write, derived uncached input, output, reasoning, provider total, reconstructed total, and supported modality detail when those fields are exposed. Reasoning is not added a second time to provider output totals when it is already contained in output accounting.

### Anthropic

The ledger preserves base/uncached input, cache creation, cache read, total reconstructed input, output, thinking when exposed, and supported server-tool request counters. Thinking is not double-counted above output.

### Google / Gemini

The ledger preserves prompt/cached/uncached input, tool-use prompt tokens, candidate output, thinking, modality maps, provider total, and the calculator's explicit `unattributed_tokens` residual. A provider total that does not reconcile with identified categories is therefore visible rather than silently forced to zero.

## Standalone ledger behavior

Commit `a377fe647b53556972f7c87c0f976f15e9f3a276` added nine focused tests covering:

1. OpenAI cache/write/reasoning token anatomy without reasoning double-counting;
2. Anthropic cache/thinking categories;
3. Google residual/unclassified tokens;
4. missing optional telemetry remaining unavailable;
5. explicit provider zero remaining an observed zero;
6. append-only/idempotent writes plus schema stripping of prompt/response/API-key fields;
7. corruption being surfaced rather than silently skipped;
8. picodollar historical cost aggregation; and
9. one continuing thread preserving independent totals for multiple models/providers.

The mixed-model regression explicitly verifies that the same thread can contain multiple model identities while maintaining independent model turn/token/cost totals. Summary token fields retain an `observed_turns` count so a partial category sum cannot masquerade as complete coverage.

GitHub Actions run `35032005191`, job `104592407656`, passed clean install, compile, proxy import, and **118/118 tests**.

## Live callback integration

Commit `2b5d9e9c79702b49ae4a672166062689728a4ee9` (`feat: persist settled turn telemetry from live callbacks`) integrated the ledger with the existing LiteLLM success callback.

The sequence is deliberately:

1. reconstruct/choose the defensible post-response local cost estimate;
2. settle local accounting and reconcile the in-flight reservation;
3. build the whitelisted telemetry record; and
4. append the record to the local ledger.

Ledger I/O is isolated from already-settled accounting. If the file append fails, TokenTotals emits a `TokenTotals Ledger Warning`; it does not undo or conceal the local cost settlement.

Only callbacks carrying TokenTotals' stable server-owned reservation ID are persisted as durable turns. That ID becomes the ledger `turn_id`, which gives both accounting and ledger history the same duplicate-callback identity boundary.

The live callback labels the dollar basis as one of the following current paths:

- `provider_registry_complete` — provider calculator fully reconstructed the modeled public pricing dimensions;
- `litellm_response_cost_fallback` — a nonzero LiteLLM response-cost fallback was required;
- `known_list_equivalent` — a supported incomplete provider calculation had a defensible known list-equivalent amount when LiteLLM supplied no response cost; or
- `unavailable` — no defensible post-response dollar amount existed.

When the dollar amount is unavailable, the ledger records `estimated_cost_usd: null` rather than claiming an observed `$0`. The legacy cumulative local arithmetic still has no numeric amount to add for that turn; future presentation must preserve the ledger's coverage/completeness signal rather than implying that an incomplete aggregate is provider-authoritative.

Commit `a03f73b9114f47ad865a5e12cc522e1cdb89232c` added seven live-settlement tests proving:

- complete provider settlement and ledger append;
- LiteLLM fallback labeling;
- known list-equivalent labeling;
- unavailable cost remaining unknown rather than fake zero;
- duplicate callback idempotency for both state and history;
- simulated ledger disk failure does not undo accounting settlement; and
- callback prompt/API-key-like fields do not leak into the whitelisted ledger.

GitHub Actions run `35032471619`, job `104593902213`, passed clean install, compile, proxy import, and **125/125 tests**.

## Public documentation

Commit `85c9dabc46a5d8da035f40237c4c5681b7b5e33f` added the local turn-ledger behavior and privacy/missing-data boundaries to `README.md`.

Commit `9f32c3389d64c6d2c450f8b78f6ae75c48d7b70f` advanced `TokenTotals_Security_Whitepaper.md` to **2.8-DEFENSIVE-SPEC** and documents:

- schema-whitelisted local telemetry;
- stable turn identity/idempotency;
- missing-vs-zero semantics;
- residual/unclassified token accounting;
- mixed-model history inside one thread;
- integer picodollar historical cost aggregation;
- ledger-write failure isolation; and
- runtime append-only behavior without an immutability/tamper-evidence claim.

Commit `e2290c6dfbc3670de34cfec9f2cc0e669e5dd24e` added public-document regression guards.

Documentation/runtime acceptance run `35032681955`, job `104594571836`, passed clean install, compile, live proxy import, and **127/127 tests** in `0.961s`.

Commit `ba2a58c4683057dccaabc2ab37deffe0926caa72` then advanced `ROADMAP.md`, marking the ledger complete and making Turn/thread telemetry presentation plus **Turn Notice** the next launch-critical engineering item.

## Unfavorable / failed evidence preserved

### GitHub contents write rejected with HTTP 409

During the first correction pass on `turn_ledger.py`, the GitHub contents update was attempted with a commit SHA where the API required the file's current blob SHA. GitHub correctly rejected the write with HTTP `409` (`sha does not match`).

No repository content changed in that failed attempt. The current blob SHA was refetched and the same intended correction was then applied successfully in commit `c52f00dc69a859da9daf5d77e749b26c9581179a`.

This tooling error is retained here rather than omitted from the evidence trail.

## Explicit boundaries

This receipt does **not** claim:

- that `turns.jsonl` is immutable, tamper-evident, cryptographically chained, or provider-authoritative;
- that missing provider telemetry is zero;
- that TokenTotals can recover hidden/private provider billing dimensions;
- that a locally estimated total equals the provider's final invoice;
- that context-window occupancy is currently available across supported providers; the current repo lacks a defensible normalized context-limit/current-context source, so the ledger does not fabricate one;
- that an unavailable post-response cost contributes a known dollar amount to cumulative arithmetic; or
- that model price implies capability equivalence or authorizes automatic substitution.

The ledger is a local telemetry evidence substrate. It records what TokenTotals can legitimately observe or defensibly derive, keeps uncertainty explicit, and supplies the factual history required for the next work item: Turn/thread presentation and Turn Notice.