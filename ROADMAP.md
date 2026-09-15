# TokenTotals Roadmap

This roadmap separates launch-critical engineering from post-drop experiments. TokenTotals' core product remains measurement, pricing reconstruction, pacing, provenance, and locally stored evidence. Advisory model-selection behavior is intentionally outside the core launch promise.

## Launch-critical remaining work

### 1. In-flight budget reservation

**Status:** Next engineering item.

Current post-response accounting is concurrency-safe inside the normal single TokenTotals daemon, but simultaneous requests can still perform preflight checks against the same unreserved remaining headroom before either request posts its eventual response cost.

Required outcome:

- reserve each accepted request's defensible preflight estimate before sending it upstream;
- include outstanding reservations in subsequent pacing decisions;
- release or reconcile the reservation when the request completes or fails;
- prevent abandoned reservations from permanently consuming local headroom;
- preserve the distinction between preflight estimate and final post-response cost;
- add negative/concurrency regressions and a verification receipt.

### 2. Append-only local turn ledger

**Status:** Planned core telemetry work.

Persist a compact economic/operational record for each proxied turn without storing prompt or response content.

Candidate record fields:

- timestamp / local turn identifier / thread identifier;
- requested and canonical model identifiers;
- provider and pricing-registry verification date;
- observed input, cached input, uncached input, output, reasoning/thinking, tool and modality token categories when legitimately exposed;
- requested and observed service/processing tier where available;
- latency;
- component cost estimates and total turn estimate;
- estimate status/basis (complete, incomplete, known list-equivalent, LiteLLM fallback, etc.);
- cumulative thread and daily estimated spend after the turn.

The ledger must remain telemetry-only: no prompt text, response text, hidden reasoning, credential material, DOM scraping, private endpoint interception, or undocumented provider-state extraction.

### 3. Turn/thread telemetry presentation

**Status:** Planned after the ledger substrate.

Use the ledger to expose the metrics developers can act on while a session is still running. Prefer factual/derived labels over ambiguous marketing language.

Priority metrics include:

- turn cost and cumulative thread spend;
- model/provider used on each turn and model-switch history;
- input / cached / uncached / output / reasoning-thinking / tool token categories when observed;
- cache share and, only when defensibly calculable, modeled cache-dollar effect;
- context occupancy against the documented model context limit;
- average/median/P95 turn cost and most expensive turns;
- tokens per turn (workload size), plus true time-based burn metrics such as dollars/minute or tokens/minute where meaningful;
- remaining local budget and estimated runway, clearly labeled as a projection;
- pricing basis, registry verification date, and complete/incomplete estimate status.

### 4. Public wording cleanup

**Status:** Small cleanup item.

Remove or qualify remaining `zero-egress` shorthand in top-level presentation surfaces such as the README badge and GitHub repository description. The accurate boundary is: TokenTotals' control plane and state are local/loopback and it does not require a TokenTotals-operated telemetry SaaS, while permitted requests still egress to the selected upstream model provider.

### 5. Final release reconciliation and proof pass

**Status:** Required before drop.

After the remaining runtime work:

- rerun the complete regression suite on a clean runner;
- verify OpenAI, Anthropic, and Google/Gemini provider registries/calculators against their then-current official public documentation;
- recheck README, whitepaper, dashboard, model catalog, pricing mechanics matrix, configuration, and runtime behavior for drift;
- review build/release packaging and clean-install startup behavior;
- preserve final verification receipts, including unfavorable findings and repaired failures rather than sanitizing history;
- do not claim invoice-exact billing or provider-account entitlement.

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
- counterfactual spend reports over historical ledger data;
- community-submitted benchmark/compatibility profiles with provenance;
- exportable evidence so developers can test candidate substitutions themselves.

This track is intentionally held back until the delivery methodology is strong enough to avoid conflating arithmetic with advice, capability judgments, or financial guarantees.

## Completed hardening milestones

The repository's verification receipts under `archive/verification-receipts/` are the evidence source for completed work, including provider-specific pricing engines, removal of the legacy pricing sync and machine-specific fallback, runtime model-catalog hardening, retirement of automatic model substitution, public pricing-document reconciliation, dashboard truthfulness, and concurrent post-response accounting.
