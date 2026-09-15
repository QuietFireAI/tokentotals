# TokenTotals Roadmap

This roadmap separates launch-critical engineering from post-drop experiments. TokenTotals' core product remains measurement, pricing reconstruction, local reminders/pacing, provenance, and locally stored evidence. Advisory model-selection behavior is intentionally outside the core launch promise.

## Launch-critical remaining work

### 1. In-flight preflight reservation

**Status:** Complete and verified.

TokenTotals now atomically reserves each admitted request's defensible preflight estimate inside the normal single local daemon before that request is sent upstream. Active reservations participate in admission decisions, successful turns reconcile the reservation with post-response estimated cost, and failed upstream calls release the reservation.

The reservation is deliberately limited to what can be estimated before execution. It does not claim to predict unknown final output/tool/reasoning charges or provider-account balances.

Verification receipt:

- `archive/verification-receipts/2026-09-15_inflight-budget-reservation-recheck.md`
- final acceptance: 107/107 tests passed on GitHub Actions run `35029757839`.

### 2. Append-only local turn telemetry ledger

**Status:** Complete and verified.

Completed TokenTotals-routed turns now write a whitelisted telemetry record to the local runtime append-only JSONL ledger at `~/.tokentotals/turns.jsonl`. The server-owned reservation identifier is reused as the stable turn identifier, giving the live callback and ledger the same idempotency boundary.

Implemented record categories include, when legitimately exposed or defensibly derived:

- start/completion timestamp, turn ID, and thread ID;
- requested model, canonical registry model, and provider-observed model as distinct fields;
- provider and pricing-registry verification date;
- input/prompt, uncached input, cached input, cache-write/create, output, reasoning/thinking, and tool-input token categories;
- modality-specific token categories and supported server-tool counters when exposed;
- provider-reported total tokens;
- TokenTotals reconstructed token total;
- unclassified/residual and reconciliation-delta tokens when provider totals do not reconcile with identified categories;
- requested and observed/applied service or processing tier where exposed;
- latency;
- provider calculation components, total estimated turn cost, completeness, and explicit cost basis;
- cumulative local/thread estimated spend after settlement.

**Mixed-model thread accounting is implemented and tested.** One continuing thread preserves independent model/provider turn, token, and estimated-cost totals without resetting when the caller changes models.

**Missing telemetry is not silently converted to observed zero.** Each normalized token field carries an `observed`, `derived`, or `unavailable` basis. An explicit provider `0` remains zero; an absent category remains unavailable. Thread summaries also retain an `observed_turns` count for each category so a partial sum cannot masquerade as full coverage.

The ledger writer accepts only its documented schema. Prompt text, response text, arbitrary callback/request fields, API keys, and hidden reasoning content are not written. The runtime file is append-only in TokenTotals' write path but is an ordinary local-user file, not immutable or tamper-evident storage.

Internal local-spend accumulation was also raised above four-decimal presentation precision, and a 1,000-micro-turn regression proves sub-cent turns are not erased. Ledger cost aggregation uses integer picodollar units before rendering back to dollars.

Context-window occupancy is not fabricated in the ledger. The current repo does not yet have a defensible normalized context-limit/current-context source across the supported providers; those fields remain unavailable until such a source is explicitly modeled and tested.

Verification receipt:

- `archive/verification-receipts/2026-09-15_turn-telemetry-ledger-recheck.md`
- documentation/runtime acceptance: 127/127 tests passed on GitHub Actions run `35032681955`.

### 3. Turn/thread telemetry presentation and Turn Notice

**Status:** Complete and verified.

TokenTotals now exposes a privacy-safe presentation layer derived from the append-only turn ledger. The local API and dashboard preserve data coverage rather than presenting missing fields as zero.

Implemented turn/thread presentation includes, when available:

- requested/canonical/observed model identity and provider;
- input, uncached input, cached input, cache-write/create, output, reasoning/thinking, tool-use, provider-total, reconstructed-total, and residual/unclassified token categories;
- observed / derived / unavailable basis for token values;
- turn cost, cost basis, pricing-registry verification date, and complete/incomplete estimate state;
- per-field thread coverage, local estimated-cost coverage, average/median/P95 turn-token size, latency, and wall-clock output token rate;
- observed cached-input share without equating token share to dollar savings; and
- independent totals by model/provider inside one continuing mixed-model thread.

The presentation endpoint is:

- `GET /api/telemetry/thread?thread_id=<id>`

It returns the normalized presentation object rather than raw JSONL. Unknown threads, blank identifiers, and ledger corruption have explicit HTTP behavior.

**Turn Notice is implemented as an opt-in derived notification event, not accounting state.** The configuration key `turn_notice_threshold_usd` defaults to `null`/disabled. When the user selects a positive local per-turn reminder value, TokenTotals can emit separate preflight and completed-turn notices. Preflight notices explicitly state that the estimate is input-side and final turn cost can differ; completed notices preserve the settled cost basis/completeness and state that provider account records remain authoritative.

Turn Notice is available through:

- `GET /api/turn-notice`
- `POST /api/turn-notice/config`
- the localhost dashboard; and
- the desktop tray notification surface in the normal same-process desktop runtime.

The tray deduplicates by event ID and consumes stale events while notices are disabled so re-enabling does not resurrect an old notification. The local lock popup also now states the real boundary: it pauses new requests routed through this TokenTotals proxy; direct requests outside TokenTotals, already in-flight provider work, and provider-account billing remain outside that local lock.

Context occupancy remains unavailable rather than fabricated until a defensible normalized source is modeled and tested.

Verification receipts:

- `archive/verification-receipts/2026-09-15_thread-telemetry-api-recheck.md`
- `archive/verification-receipts/2026-09-15_turn-notice-recheck.md`
- final runtime/dashboard/tray acceptance: **161/161 tests passed** on GitHub Actions run `35035438788`, job `104603395283`.
- the receipt preserves the earlier dashboard acceptance failure where 155/157 passed and two stale assertions were repaired without changing working runtime behavior.

### 4. Public wording cleanup

**Status:** Next engineering item.

Reconcile top-level presentation language with the final product boundaries:

- replace remaining `zero-egress` shorthand with the accurate local-control-plane/upstream-egress description;
- replace launch-facing `budget`, `remaining`, `headroom`, and similar financial-clearance wording with `local estimated spend`, `Reminder Threshold`, `threshold state`, and `Turn Notice` where appropriate;
- preserve backward-compatible internal/API field names only where changing them would unnecessarily break existing clients, while keeping launch-facing copy neutral; and
- preserve the fact that TokenTotals does not know the user's provider balance, subscription/plan credits, negotiated pricing, or authoritative remaining account funds.

The accurate network boundary is: TokenTotals' control plane and state are local/loopback and it does not require a TokenTotals-operated telemetry SaaS, while permitted requests still egress to the selected upstream model provider.

### 5. Final release reconciliation and proof pass

**Status:** Required before drop.

After the remaining runtime work:

- rerun the complete regression suite on a clean runner;
- verify OpenAI, Anthropic, and Google/Gemini provider registries/calculators against their then-current official public documentation;
- recheck README, whitepaper, dashboard, model catalog, pricing mechanics matrix, configuration, runtime behavior, ledger schema, and Turn Notice copy for drift;
- review build/release packaging and clean-install startup behavior;
- preserve final verification receipts, including unfavorable findings and repaired failures rather than sanitizing history;
- do not claim invoice-exact billing, provider-account entitlement, or remaining provider funds.

## Post-drop / Community Labs

### Community Labs: Experimental Cost Counterfactuals

**Status:** Deliberately not launch-critical. Opt-in experimental/community track.

Purpose: let the community help research and pressure-test cost counterfactuals without turning TokenTotals' factual core meter into a model-recommendation engine.

Principles:

- advisory/counterfactual only; never silently switch a model or provider;
- downstream from the factual turn ledger, never mixed into actual spend accounting;
- clearly separate observed facts, TokenTotals-derived arithmetic, and advisory assumptions;
- prefer language such as `lower-cost models worth evaluating under these declared constraints` over `use this model` or `equivalent model`;
- require explicit compatibility constraints (tools, modalities, context, structured output, credentials/provider access, latency/reasoning requirements, etc.) before presenting comparisons;
- expose assumptions, pricing basis, confidence/uncertainty, and the fact that quality/equivalence is not proven by price;
- no scraping, private endpoint interception, hidden-state extraction, or other unsupported telemetry acquisition;
- invite community benchmarks, task-class definitions, compatibility evidence, failure cases, and peer review before any stronger delivery claim is considered.

Potential future surfaces:

- an opt-in `Community Labs` tab/panel;
- counterfactual reports over historical ledger data;
- community-submitted benchmark/compatibility profiles with provenance;
- exportable evidence so developers can test candidate substitutions themselves.

This track is intentionally held back until the delivery methodology is strong enough to avoid conflating arithmetic with advice, capability judgments, or financial guarantees.

## Completed hardening milestones

The repository's verification receipts under `archive/verification-receipts/` are the evidence source for completed work, including provider-specific pricing engines, removal of the legacy pricing sync and machine-specific fallback, runtime model-catalog hardening, retirement of automatic model substitution, public pricing-document reconciliation, dashboard truthfulness, concurrent post-response accounting, in-flight preflight reservation, high-precision local spend accumulation, the append-only local turn telemetry ledger, thread telemetry presentation API, and opt-in Turn Notice dashboard/tray presentation.