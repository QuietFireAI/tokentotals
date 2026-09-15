# TokenTotals Forensic Integrity Report

**Repository reviewed:** `QuietFireAI/tokentotals`  
**Baseline:** `main` at start of 2026-09-14 review  
**Repair branch:** `sol/forensic-hardening`  
**Purpose:** Separate code-integrity findings from ordinary bugs. This report does **not** infer intent. “Fabricated” below means a value/behavior was presented as telemetry or verified behavior without being produced by the implementation.

## Classification

- **CONFIRMED DEFECT** — reproducible implementation fault.
- **FABRICATED / PLACEHOLDER TELEMETRY** — displayed numbers are hard-coded rather than measured.
- **UNSUPPORTED CLAIM** — documentation promises behavior not present in the baseline implementation.
- **STUB / FALLBACK** — substitute logic masks a missing dependency or implementation.
- **STALE DATA** — published data no longer matches the cited authority.
- **CONFIRMED IMPLEMENTED** — claim materially exists in code.

## Findings

### IR-001 — Developer-machine pricing path — CONFIRMED DEFECT

Baseline `proxy_server.py` inserted this absolute path into `sys.path`:

```text
C:\Users\Command Center\.gemini\config\plugins\token-cost-estimator\scripts
```

Baseline `build.ps1` repeated the same path through PyInstaller `--paths`.

**Impact:** clean installations did not use the same pricing implementation as the developer machine.

**Repair:** removed both machine-specific paths. Pricing now lives in this repository (`pricing_engine.py` + `pricing_catalog.json`).

### IR-002 — Silent invented fallback pricing — STUB / INTEGRITY DEFECT

If the private pricing module import failed, baseline code silently substituted:

- input: `$2.50 / 1M`
- output: `$10.00 / 1M`
- token estimate: `len(text) // 4`

The fallback `calculate_cost()` returned only `input_cost_usd`, while other code attempted to read `total_cost_usd` and could fall through to a hard-coded `$0.001` value.

**Impact:** believable dollar totals could be produced without a verified price source.

**Repair:** unknown models now fail closed with HTTP 422. There is no generic dollar fallback.

### IR-003 — Pricing “sync” was disconnected from runtime meter — CONFIRMED DEFECT

Baseline `pricing_sync.py` downloaded LiteLLM's community model-price registry into `~/.tokentotals/model_prices.json`. Baseline `proxy_server.py` did not use that file for its pre-flight pricing calculation; it used the private plugin/fallback path instead.

**Impact:** a successful “sync” did not prove the meter was using the synchronized prices.

**Repair:** OpenAI is now the first provider with a connected official-source synchronization path. `openai_pricing_sync.py` checks the supported OpenAI model documentation on `developers.openai.com`, parses a complete candidate snapshot, validates it, and writes candidate/status/history separately from the promoted runtime snapshot. Only a validated promoted snapshot at `~/.tokentotals/pricing/openai_verified.json` can overlay the checked-in OpenAI entries consumed by `pricing_engine.py`.

Failed or incomplete source checks preserve the previous verified snapshot. Suspicious rate jumps are quarantined. A source-content change that does not produce a recognized supported pricing/rule change is held for review rather than silently treated as unchanged. Failed checks remain due for retry. No LiteLLM/community pricing registry is permitted to overwrite production pricing.

The matrix generator reads `pricing_engine` as well, so regenerated OpenAI matrix rows and runtime calculations use the same effective verified pricing view. Anthropic and Google remain on dated checked-in verified entries until equivalent provider adapters are separately implemented and tested.

**Validation:** regression tests prove candidate parsing, failed-check preservation, runtime consumption of the promoted snapshot, suspicious-jump quarantine, same-day retry after failure, and review-required handling for source-only changes.

### IR-004 — “Official provider pricing audited live” — UNSUPPORTED CLAIM

The baseline dashboard said official vendor pricing was “audited live directly from provider documentation.” The code downloaded the LiteLLM GitHub registry, not the three provider documentation pages.

**Repair:** wording changed to dated provider receipts. OpenAI now has a separately validated official-source checker; Anthropic and Google remain explicitly described as dated verified catalog entries until their own adapters are implemented. The dashboard no longer makes the old blanket live-audit claim.

### IR-005 — Published model matrix was stale — STALE DATA

Baseline `MODEL_COMPARISON_MATRIX.md` centered Claude 3.x, GPT-4o/o1/o3-mini, and Gemini 2.x-era entries.

**Repair:** the matrix was regenerated from the effective verified pricing view supplied by `pricing_engine`. On the 2026-09-14/15 revalidation pass, every committed base input/output row was checked against the current official provider pricing documentation and matched the published base/standard rates represented by the matrix. The matrix is intentionally a standard comparison, not a representation of every context band, cache rate, service tier, regional modifier, tool charge, promotion, or account-specific condition.

A dedicated regression test now regenerates the portable base matrix from the checked-in verified pricing view and fails CI if `MODEL_COMPARISON_MATRIX.md` drifts from the catalog/generator. Runtime generation still consumes a promoted OpenAI overlay when one exists.

### IR-006 — Clean install omitted required dependency — CONFIRMED DEFECT

Baseline `proxy_server.py` imported `litellm`; baseline `requirements.txt` did not install it.

**Repair:** `litellm` is now a runtime requirement. The proxy guardrail tests were also corrected so they no longer inject a fake `litellm` module that could mask a missing dependency. The clean GitHub Actions environment installs `requirements-dev.txt`, which includes `requirements.txt`, imports the real installed LiteLLM package, and verifies that `proxy_server.litellm` is that installed module.

**Validation:** clean Ubuntu/Python 3.12 CI installed LiteLLM from the declared requirements and passed the hardened dependency/proxy suite. A future removal of LiteLLM from the declared runtime dependencies should now fail CI rather than being hidden by the test harness.

### IR-007 — Circuit breaker reserved input cost only — CONFIRMED SAFETY DEFECT

Baseline pre-flight called `calculate_cost(pricing, estimated_tokens, 0)` and checked only the input estimate before upstream egress.

**Impact:** a request could pass the pre-flight check and then exceed the stated budget through generated output.

**Repair:** pre-flight now reserves input **and bounded output** using high-side published guard rates. Requests without an output bound receive a bounded default constrained by remaining budget. Reservations are reconciled to reported usage after successful non-stream responses.

### IR-008 — Concurrent requests could race the budget — CONFIRMED SAFETY DEFECT

Baseline performed read/check/send logic without an atomic reservation. Multiple concurrent calls could each observe the same remaining budget and pass independently.

**Repair:** `try_reserve_spend()` performs check-and-reserve under a process lock with atomic state-file replacement.

### IR-009 — Global per-request callback state — CONFIRMED CONCURRENCY DEFECT

Baseline used process globals (`CURRENT_THREAD_ID`, `CURRENT_ROUTINE_FLAG`, `CURRENT_POTENTIAL_SAVING`) for request-specific data consumed by the LiteLLM callback.

**Impact:** overlapping requests could attribute spend/savings to the wrong request/thread.

**Repair:** request-specific values stay local to the request path; the global callback accounting path was removed.

### IR-010 — `/api/unlock` claimed acknowledgment it never verified — CONFIRMED INTEGRITY DEFECT

Baseline endpoint unlocked immediately and returned:

```text
Circuit breaker unlocked by user acknowledgment.
```

It accepted no acknowledgment value. The desktop Tk dialog did verify `I UNDERSTAND`, so the protection existed in one UI but was bypassable through the API.

**Repair:** `/api/unlock` requires the literal phrase `I UNDERSTAND`.

### IR-011 — Budget boost endpoint could be invoked without confirmation — CONFIRMED DEFECT

Baseline `/api/boost` raised the budget and unlocked immediately. Combined with permissive CORS configuration, this unnecessarily enlarged the local attack surface.

**Repair:** permissive CORS middleware was removed; dashboard boost requires the literal phrase `BOOST $5`. Native tray actions remain explicit local user actions.

### IR-012 — Dashboard telemetry numbers were hard-coded — FABRICATED / PLACEHOLDER TELEMETRY

Baseline HTML displayed:

- `~199k tok/turn`
- `14.5M tokens processed`
- `~85% Hit`
- “Prompt caching discount active”

The refresh loop did not update those values from runtime state.

**Impact:** the dashboard presented fixed values in locations styled as live telemetry.

**Repair:** removed. The dashboard now shows only values actually supplied by state/status. Missing telemetry is not invented.

### IR-013 — “Turn-by-turn chat telemetry badge” — UNSUPPORTED CLAIM

Baseline README said every developer turn renders a badge directly in the working context. No corresponding injection/rendering implementation exists in the proxy, GUI, or dashboard code reviewed.

**Repair requirement:** documentation must call this planned/not implemented unless an adapter is later added and tested.

### IR-014 — “BPE token count” / unsupported precision language — UNSUPPORTED CLAIM

Baseline pre-flight fallback used a character-length heuristic rather than a provider/model BPE tokenizer. The whitepaper described deterministic BPE counts.

**Repair:** current estimator is explicitly labeled a conservative local estimate. Post-response provider usage is preferred for reconciliation. Documentation must not represent the pre-flight count as a provider/model BPE count.

### IR-015 — WebSocket claim — UNSUPPORTED CLAIM

The whitepaper described an HTTP/WebSocket proxy. The reviewed application implements FastAPI HTTP endpoints and SSE-style streaming for `/v1/chat/completions`; no TokenTotals WebSocket endpoint/proxy lifecycle was identified.

**Repair requirement:** remove WebSocket language unless implemented and tested.

### IR-016 — “Every response contains everything needed to calculate spend” — UNSUPPORTED / OVERBROAD CLAIM

Provider response schemas, streaming behavior, caching fields, tools, service tiers, long-context rates, regional rates, and provider-specific billable items vary. Baseline itself already had to fall back when cost/usage was absent.

**Repair:** missing stream usage retains the conservative reservation and increments `unreconciled_streams`; it is not represented as invoice-level reconciliation.

### IR-017 — Government/FedRAMP statement — UNSUPPORTED CLAIM

Baseline README said a local tool “sails through compliance review.” Localhost architecture alone does not establish FedRAMP/FISMA authorization, suitability, accreditation, or approval for a government environment.

**Repair requirement:** replace with factual architectural properties and require organization-specific security/compliance review.

### IR-018 — Cross-platform badge overstated GUI support — UNSUPPORTED CLAIM

Baseline README advertised Windows/macOS/Linux. `app_gui.py` imports Windows-specific `winsound`, uses `os.startfile`, and the supplied packaging script is PowerShell/Windows-oriented.

**Repair requirement:** advertise the packaged GUI as Windows unless macOS/Linux paths are implemented and tested. The Python proxy may be portable separately.

## Confirmed implemented baseline behavior

The forensic review also found real code, not just claims:

- FastAPI proxy application exists.
- Direct server launch binds to `127.0.0.1`.
- Persistent local config/state files exist under `~/.tokentotals`.
- Daily spend state, thread spend state, lock flag, tray traffic-light monitoring, and Tk acknowledgment dialog are implemented.
- Upstream routing through LiteLLM is implemented.
- SSE-style streaming pass-through is implemented for chat completions.

These components were preserved rather than rewritten wholesale.

## Repair validation

Current GitHub Actions regression suite on the hardened branch: **21 passed / 0 failed** on Ubuntu/Python 3.12 after the IR-006 clean-dependency proof was hardened.

Regression coverage includes:

1. verified input + output cost math;
2. conservative guard rate >= displayed base estimate;
3. strict alias resolution, no fuzzy model pricing;
4. unknown model pricing fails closed;
5. atomic reservation blocks concurrent-style over-budget reservations;
6. reservation reconciliation releases unused headroom;
7. unlock requires `I UNDERSTAND`;
8. boost requires `BOOST $5`;
9. unknown price does not call upstream;
10. output reservation can block before upstream;
11. absent max output is bounded before egress and reconciled after usage;
12. fabricated dashboard constants cannot regress unnoticed;
13. OpenAI pricing-page parsing for supported fields;
14. cache-write derivation and long-context rule capture;
15. service-mode relationship capture where published by the supported source;
16. incomplete/failed OpenAI source checks preserve the last verified snapshot;
17. promoted OpenAI snapshot is the runtime pricing view;
18. suspicious pricing changes are quarantined and failed checks remain retryable;
19. source-content-only changes require review instead of being silently ignored;
20. committed base pricing matrix must match the generator/base verified pricing view;
21. proxy imports the real installed LiteLLM runtime dependency in the clean CI environment.

## Remaining limitations before calling this production-proven

- The 21-test suite is focused regression coverage, not a full integration or load test.
- The IR-003 CI tests use controlled source fixtures to test parser and promotion behavior; deployment still depends on the availability and continued documented structure of the official provider pages.
- No live paid provider request was executed during this review; doing so should use intentionally tiny limits and test keys.
- Multi-process workers are not supported for the file-lock budget invariant; the current lock is process-local. Run one TokenTotals proxy process unless cross-process locking is added.
- OpenAI source synchronization does not by itself implement every OpenAI billing dimension in transaction accounting. Tool-call fees, image/audio billing, prompt caching details, service tiers, regional variations, provider promotions, and other applicable meters require explicit accounting support before they can be represented as a high-confidence provider-rule estimate.
- Anthropic and Google do not yet have the dynamic official-source synchronization path implemented for OpenAI.
- Streaming responses without final usage retain the worst-case reservation and are marked unreconciled rather than guessed.
- Vendor prices and page structures change. Source verification evidence records what was checked; it is not a promise that a provider cannot later change either pricing or documentation format.

## Integrity conclusion

The baseline repository was **not an empty shell**. Its proxy, local state, GUI lock dialog, and routing path were substantive. However, it contained several material integrity failures: machine-specific dependencies, silent invented pricing, disconnected sync logic, an input-only safety check, API bypasses, race-prone accounting, and hard-coded dashboard telemetry presented as live-looking metrics. Documentation also exceeded implementation in several places.

The hardening branch removes the known silent fabrication/fallback paths and changes the governing rule to: **unknown or unreconciled data stays unknown/conservative; it is never converted into a plausible-looking number merely to keep the UI green.**
