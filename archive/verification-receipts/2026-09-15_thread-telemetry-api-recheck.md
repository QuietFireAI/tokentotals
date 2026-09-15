# Thread Telemetry Presentation API Recheck Receipt

Date: 2026-09-15  
Repository: `QuietFireAI/tokentotals`

## Scope

This receipt covers the first presentation layer built on top of the verified append-only turn telemetry ledger. The goal was to expose a privacy-safe, developer-facing thread telemetry object without returning raw ledger records and without introducing dashboard or Turn Notice behavior in the same change.

## Presentation semantics

Commit `96019b2c5e4055b8bc4ff64d6ce8a1504e1f3478` introduced `telemetry_view.py`.

The presentation layer derives a compact view from the local turn ledger and preserves uncertainty rather than converting missing telemetry into zero. It includes:

- latest completed turn identity, model/provider identity, token categories, token basis, cost basis, estimate completeness, pricing registry verification date, modality/tool details, and notes;
- cache share only when both input and cached-input token values are available;
- output tokens divided by callback wall-clock elapsed time only when both output tokens and latency are available, explicitly labeled as wall-clock rate rather than pure model generation throughput;
- thread-wide token totals with `observed_turns`, `total_turns`, and `complete` / `partial` / `unavailable` coverage for each token category;
- estimated thread cost with `costed_turns`, `total_turns`, and coverage;
- average, median, P95 nearest-rank, maximum, and sum of turn token totals using provider-reported totals first and TokenTotals reconstructed totals only as a fallback;
- independent model/provider totals inside one continuing mixed-model thread; and
- context-window status explicitly marked unavailable because the current runtime does not yet have a defensible normalized current-context plus model-limit source across supported providers.

Commit `303219922164fd730df10e3396eb4b543f1cd4b1` added seven focused semantic tests. GitHub Actions run `35033022819`, job `104595667483`, passed clean install, compile, live proxy import, and **134/134 tests**.

## HTTP endpoint

Commit `f7556955460f01247ced16816fa70ee4e11c5199` wired the proven presentation object into the local FastAPI runtime:

`GET /api/telemetry/thread?thread_id=<id>`

The endpoint:

- requires a non-empty thread identifier;
- returns the tested presentation object rather than raw JSONL ledger records;
- returns HTTP `404` when no telemetry exists for the requested thread;
- returns HTTP `400` for a blank thread identifier;
- leaves FastAPI's normal HTTP `422` validation for a missing required query parameter; and
- surfaces `LedgerCorruptionError` as HTTP `500` instead of silently skipping malformed evidence.

The endpoint does not expose prompts, responses, credential material, hidden reasoning content, or raw arbitrary callback/request structures.

The commit diff was rechecked after the contents write and contained only the `telemetry_view` import plus the new endpoint.

Commit `b33e3b2d3469823b76d17073036db6b205cae0d3` added five endpoint-contract tests covering success, missing query parameter, blank ID, unknown thread, and corrupt-ledger behavior.

GitHub Actions run `35034037613`, job `104598898255`, passed clean install, compile, live proxy import, and **139/139 tests** in `0.754s`.

## Explicit boundaries

This layer does **not** claim:

- raw provider account balance or remaining funds;
- context occupancy where a defensible source is unavailable;
- complete dollar coverage when some turns could not be priced defensibly;
- that cache-token percentage equals dollar savings percentage;
- that callback wall-clock output tokens/second is pure model generation throughput;
- immutable or provider-authoritative ledger history; or
- model capability equivalence or permission to switch models automatically.

The presentation API is now the factual substrate for the next work item: Turn Notice behavior and dashboard rendering.