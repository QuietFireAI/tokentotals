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

**Status:** Next engineering item.

Persist a compact factual/derived telemetry record for each proxied turn without storing prompt or response content. The ledger is the substrate for TokenTotals' historical token totals, mixed-model sessions, Turn Notices, exports, and later Community Labs research.

Required record categories include, when legitimately exposed or defensibly derived:

- timestamp / local turn identifier / request identifier / thread identifier;
- requested model, canonical registry model, and provider-observed/applied model kept as distinct fields where those values differ;
- provider and pricing-registry verification date;
- input/prompt tokens;
- uncached input tokens;
- cached input tokens;
- cache-write/cache-create tokens where applicable;
- output tokens;
- reasoning/thinking tokens when exposed;
- tool-use input tokens and supported server-tool invocation counts where exposed;
- modality-specific token categories when exposed;
- provider-reported total tokens when available;
- TokenTotals reconstructed token total;
- unclassified/residual tokens when provider totals do not reconcile with identified categories;
- requested and observed/applied service or processing tier where available;
- context load and documented model context limit where defensibly available;
- latency and, where timing data permits, true time-based output throughput;
- component cost estimates and total turn estimate;
- estimate status/basis (`complete`, `incomplete`, known list-equivalent, LiteLLM fallback, etc.);
- cumulative factual thread token totals and local estimated spend after the turn.

**Mixed-model thread accounting is mandatory.** The same thread must preserve independent totals by model/provider so a session can truthfully report, for example, how many turns and observed tokens were handled by each model without treating a model switch as a new thread.

Missing telemetry must never be silently converted to observed zero. `0` means zero was actually observed or defensibly derived; otherwise the field is unavailable/unknown or omitted with an explicit status.

The ledger must remain telemetry-only: no prompt text, response text, hidden reasoning, credential material, DOM scraping, private endpoint interception, or undocumented provider-state extraction.

Internal cost accumulation should retain substantially more precision than the four-decimal human-facing display so repeated sub-cent turns are not lost through per-turn display rounding.

### 3. Turn/thread telemetry presentation and Turn Notice

**Status:** Planned immediately after the ledger substrate.

Use the ledger to expose the token and cost metrics developers can inspect while a session is still running. Prefer factual/derived labels over ambiguous financial or capability language.

Priority turn metrics include:

- requested/observed model and provider;
- input, uncached input, cached input, cache-write, output, reasoning/thinking, tool-use, and modality categories when exposed;
- provider-reported total tokens;
- TokenTotals reconstructed total tokens;
- unclassified/residual token count when totals do not reconcile;
- cache share of observed input, without equating token share to dollar savings;
- input/output and reasoning shares where meaningful;
- context occupancy against a documented model context limit;
- latency and true output tokens/second where measurable;
- estimated turn cost, cost components, pricing basis, registry verification date, and complete/incomplete estimate status.

Priority historical/thread metrics include:

- total turns and total observed/reconstructed tokens;
- totals by model/provider inside the same thread;
- model-switch timeline;
- input / cached / uncached / cache-write / output / reasoning / tool / modality totals;
- average, median, and P95 tokens per turn;
- largest token turn and most expensive estimated turn;
- context-growth history where meaningful;
- cumulative local estimated thread cost with its estimate basis preserved.

**Turn Notice** is the generic notification event name. A configurable Turn Notice may fire when an individual preflight or completed-turn estimate crosses a user-selected reminder value. The notice must say what was estimated/observed and why it fired; it must not imply provider-account clearance or a guaranteed maximum cost for the next action.

The configured dollar threshold is a **local Reminder Threshold**, not an upstream provider balance, credit limit, spending allowance, or statement such as `you have $X left`. Launch-facing copy should avoid `remaining budget`, `available financial headroom`, or `runway` language that could be interpreted by a human or autonomous agent as financial permission for the next turn.

### 4. Public wording cleanup

**Status:** Small cleanup item.

Reconcile top-level presentation language with the final product boundaries:

- replace remaining `zero-egress` shorthand with the accurate local-control-plane/upstream-egress description;
- replace launch-facing `budget`, `remaining`, `headroom`, and similar financial-clearance wording with `local estimated spend`, `Reminder Threshold`, `threshold state`, and `Turn Notice` where appropriate;
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

The repository's verification receipts under `archive/verification-receipts/` are the evidence source for completed work, including provider-specific pricing engines, removal of the legacy pricing sync and machine-specific fallback, runtime model-catalog hardening, retirement of automatic model substitution, public pricing-document reconciliation, dashboard truthfulness, concurrent post-response accounting, and in-flight preflight reservation.