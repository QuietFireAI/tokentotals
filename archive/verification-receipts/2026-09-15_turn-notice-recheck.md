# Turn Notice and Telemetry Presentation Recheck Receipt

Date: 2026-09-15  
Repository: `QuietFireAI/tokentotals`

## Scope

This receipt records the implementation and verification of TokenTotals' launch-facing turn/thread telemetry presentation and opt-in **Turn Notice** behavior built on top of the already-verified append-only local turn ledger.

The design goal was to expose factual/derived per-turn economics without creating a second accounting truth source and without implying provider-account balance, spending authorization, invoice exactness, or hidden telemetry access.

## Presentation substrate

Commit `96019b2c5e4055b8bc4ff64d6ce8a1504e1f3478` introduced `telemetry_view.py`.

The presentation layer derives a privacy-safe view from ledger records and preserves uncertainty:

- latest completed turn model/provider identity;
- input, cached input, uncached input, cache-write/create, output, reasoning/thinking, tool-input, provider-total, reconstructed-total, and residual/unclassified token categories when available;
- explicit observed / derived / unavailable token basis;
- per-field thread coverage using observed-turn counts;
- local estimated cost with costed-turn coverage;
- average, median, nearest-rank P95, maximum, and sum of defensible turn-token totals;
- cache share only when both needed values are available, without equating token share to dollar savings;
- callback wall-clock output tokens/second only when output tokens and timing are available, explicitly not represented as pure model generation throughput; and
- independent totals by model/provider inside the same continuing thread.

Context occupancy remains explicitly unavailable because the current runtime does not yet have a defensible normalized current-context plus model-limit source across supported providers.

Commit `303219922164fd730df10e3396eb4b543f1cd4b1` added semantic tests. GitHub Actions run `35033022819`, job `104595667483`, passed **134/134 tests**.

## Thread telemetry API

Commit `f7556955460f01247ced16816fa70ee4e11c5199` exposed:

`GET /api/telemetry/thread?thread_id=<id>`

The endpoint returns the tested presentation object rather than raw JSONL. Blank IDs are rejected, unknown threads return `404`, and ledger corruption is surfaced rather than silently skipped.

Commit `b33e3b2d3469823b76d17073036db6b205cae0d3` added endpoint contract tests. GitHub Actions run `35034037613`, job `104598898255`, passed **139/139 tests**.

A separate receipt also records that layer:

- `archive/verification-receipts/2026-09-15_thread-telemetry-api-recheck.md`

## Turn Notice event engine

Commit `d269a12f46d5b07f4b5deabe5e3a7e0d902405f6` introduced `turn_notice.py`.

Turn Notice is deliberately a **derived process-local notification event**, not accounting state. It is downstream from the same preflight/settled estimates used by the core meter.

Current semantics:

- disabled when no positive reminder threshold is configured;
- fires when the relevant local per-turn estimate is greater than or equal to the configured reminder value;
- distinct `preflight` and `completed` stages;
- stable event IDs based on TokenTotals' server-owned turn/reservation identity plus stage;
- process-local duplicate-event suppression;
- latest global and per-thread event views;
- preflight wording explicitly states the estimate is input-side and final cost can differ; and
- completed wording explicitly states provider account records remain authoritative.

Commit `95cace346df39c8481eb1941b102bf22e9922424` added event-semantics tests. GitHub Actions run `35034224758`, job `104599488366`, passed **145/145 tests**.

## Opt-in configuration

Commit `9943f81250db0301bf646add9e770f6732a53f57` added the config default:

`turn_notice_threshold_usd: null`

`null` means disabled. New installs and legacy configs missing the key both resolve to disabled until the user explicitly selects a positive per-turn reminder value.

GitHub Actions run `35034413844`, job `104600106487`, passed **147/147 tests**.

## Live lifecycle integration

Commit `f7d92e17cd2145423ba19f771d30f99445bfcd9e` wired Turn Notice into the existing request lifecycle without rewriting pricing or reservation logic.

### Preflight stage

A preflight Turn Notice is evaluated only **after** the preflight estimate has passed the local pacing admission check and its reservation is accepted. Blocked, unpriced, or rejected requests do not create a Turn Notice.

### Completed stage

A completed Turn Notice is evaluated after local cost settlement when a defensible settled estimate exists. It carries the same cost-basis/completeness information used by accounting.

Turn Notice publication is isolated from ledger I/O. A simulated ledger `disk full` error after accounting settlement does not suppress the already-derived completed notice.

The runtime also exposes:

`GET /api/turn-notice`

with optional thread scope.

Commit `fb012f2f94c6a8abb0bcd34089d11f327c1692b4` added five live integration tests. GitHub Actions run `35034717535`, job `104601095732`, passed **152/152 tests**.

## Dashboard presentation

Commit `dd98c00ab208aaa500859106804242176d3c3300` added the dashboard Turn Notice and telemetry surfaces.

The dashboard now consumes the presentation APIs rather than raw ledger files and displays, when available:

- posted local estimate and combined local estimate including in-flight preflight estimate;
- local pacing threshold state using neutral threshold language;
- opt-in Turn Notice reminder configuration and latest notice;
- latest-turn token anatomy and basis;
- turn cost, cost basis, completeness, and pricing-registry verification date;
- latency and wall-clock output token rate;
- thread turn/cost coverage and token-size statistics;
- observed cache-input share with an explicit warning that token share is not dollar savings; and
- separate model/provider totals inside one mixed-model thread.

`/api/status` gained neutral presentation aliases such as `posted_estimated_spend_usd`, `combined_local_estimate_usd`, and `pacing_threshold_usd`. Legacy `budget_*` JSON names remain temporarily for backward compatibility; the dashboard does not use them as launch-facing wording.

The dashboard also gained:

`POST /api/turn-notice/config`

A positive JSON number enables the reminder threshold; `null` disables it. Invalid, non-positive, boolean, or string values are rejected.

Dashboard wording guards require the rendered UI to avoid `Available headroom`, `IN BUDGET`, or `you have $...` financial-clearance language.

### Preserved failed acceptance run

The first dashboard acceptance run, GitHub Actions run `35035112006`, job `104602374332`, **failed with 155/157 tests passing**.

Two failures were diagnosed as stale test assumptions rather than runtime defects:

1. A test expected a merely reserved in-flight thread to replace the last settled `active_thread_id`. The runtime correctly retained the last settled thread until a completion was posted.
2. A static precision test searched for the literal JavaScript string `toFixed(4)`. The dashboard formatter had been refactored to `function usd(value, digits=4)` and `toFixed(digits)`, preserving the same four-decimal default behavior.

No runtime code was changed to repair those failures. The assertions were corrected in commits `5e0090876586c22dcf8f53e6a8b5955366ebbc75` and `1478f8456e25875c0d8c9536daa863fc9a06e701`.

The corrected dashboard acceptance run `35035237349`, job `104602765622`, passed **157/157 tests**.

## Tray Turn Notice and lock wording

Commit `aadc377002fd26070a1cc5501551a7bc62379092` connected the Windows tray monitor to the same process-local Turn Notice event stream already used by the runtime.

The tray:

- reads the shared latest Turn Notice rather than creating a second store;
- only notifies while the opt-in threshold is enabled;
- deduplicates notifications by event ID;
- consumes an event while notices are disabled so re-enabling does not resurrect a stale notification; and
- records the event as consumed even if the OS notification backend raises, preventing a two-second retry storm.

Because `app_gui.py` and the imported FastAPI app run in the same Python process in the desktop runtime, they share the same `turn_notice` module state directly.

The same commit removed an existing GUI overclaim that had stated all outgoing calls were hard-frozen and the user's credit card would not be billed. The lock popup now states the actual boundary: new requests routed through this TokenTotals proxy are paused while its local pacing lock is active, while requests outside TokenTotals, already in-flight provider work, and provider-account billing remain outside that local lock.

Commit `893a01595c4e4571d13dece004765cda776dc85e` added four Linux-safe source/AST guards for the Windows tray behavior and wording.

Final GitHub Actions run `35035438788`, job `104603395283`, passed clean dependency install, Python compile, live proxy import, and **161/161 tests** in `0.745s`.

## Expected warning evidence

The passing runs intentionally include warning-path evidence exercised by tests, including:

- provider telemetry that cannot be fully priced from a dedicated registry and falls back only when a defensible fallback exists;
- known list-equivalent incomplete estimates;
- simulated `TokenTotals Ledger Warning: Turn ledger append failed: disk full` cases proving accounting/Turn Notice isolation; and
- GitHub runner deprecation warnings for Node 20-targeting `actions/checkout@v4` and `actions/setup-python@v5`, which the current runner forces onto Node 24.

The Starlette TestClient/httpx deprecation warning also remains a maintenance warning, not a failing test.

## Explicit boundaries

This work does **not** claim:

- provider account balance, remaining funds, credit, or spending authorization;
- invoice-exact local cost;
- that a preflight input-side estimate is a maximum full-turn cost;
- that cache-token percentage equals dollar savings percentage;
- that wall-clock output tokens/second isolates pure provider generation throughput;
- that context occupancy is available where it is not defensibly observed;
- that Turn Notice events are durable accounting records;
- that the local pacing lock controls direct calls outside TokenTotals or provider-account billing;
- cross-process/distributed atomicity; or
- model capability equivalence or automatic substitution.

The verified launch-facing path is now: provider/request telemetry -> provider-specific cost reconstruction -> settled append-only turn ledger -> truthful thread/turn presentation -> optional Turn Notice -> dashboard/tray surfaces.