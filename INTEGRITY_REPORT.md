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

### IR-003 — Pricing “sync” was disconnected from runtime meter — CONFIRMED DEFECT / REPAIRED AND REVALIDATED

Baseline `pricing_sync.py` downloaded LiteLLM's community model-price registry into `~/.tokentotals/model_prices.json`. Baseline `proxy_server.py` did not use that file for its pre-flight pricing calculation; it used the private plugin/fallback path instead.

**Impact:** a successful “sync” did not prove the meter was using the synchronized prices.

**Repair:** OpenAI is now the first provider with a connected official-source synchronization path. `openai_pricing_sync.py` checks the supported OpenAI model documentation on `developers.openai.com`, parses a complete candidate snapshot, validates it, and writes candidate/status/history separately from the promoted runtime snapshot. Only a validated promoted snapshot at `~/.tokentotals/pricing/openai_verified.json` can overlay the checked-in OpenAI entries consumed by `pricing_engine.py`.

Failed or incomplete source checks preserve the previous verified snapshot. Suspicious rate jumps are quarantined. A source-content change that does not produce a recognized supported pricing/rule change is held for review rather than silently treated as unchanged. Failed checks remain due for retry. No LiteLLM/community pricing registry is permitted to overwrite production pricing.

The matrix generator reads `pricing_engine` as well, so regenerated OpenAI matrix rows and runtime calculations use the same effective verified pricing view. Anthropic and Google remain on dated checked-in verified entries until equivalent provider adapters are separately implemented and tested.

**Validation:** fixture-based regression tests prove candidate parsing, failed-check preservation, runtime consumption of the promoted snapshot, suspicious-jump quarantine, same-day retry after failure, and review-required handling for source-only changes. A separate non-destructive GitHub Actions source check then fetched the live OpenAI documentation on 2026-09-15, parsed and validated the supported Astra/Sol/Terra/Luna source pages into a temporary candidate, and completed successfully without writing the runtime verified snapshot. Its audit output reported the current parsed base rates, cache-read/cache-write rates, conservative guard rates, source URLs, and source hashes. The ordinary regression workflow on that branch revision also passed 21/21 tests.

### IR-004 — “Official provider pricing audited live” — UNSUPPORTED CLAIM / REPAIRED AND REVALIDATED

The baseline dashboard said official vendor pricing was “audited live directly from provider documentation.” The code downloaded the LiteLLM GitHub registry, not the three provider documentation pages.

**Repair:** wording changed to dated provider receipts. OpenAI now has a separately validated official-source checker; Anthropic and Google remain explicitly described as dated verified catalog entries until their own adapters are implemented. The dashboard no longer makes the old blanket live-audit claim.

**Validation:** a dedicated public-claim integrity test scans the README, technical/security whitepaper, and dashboard source. It fails if the old blanket live-audit wording (or close variants) returns, and it separately requires the documentation to preserve the actual scope: OpenAI has the current official-source synchronization path; Anthropic and Google remain dated catalog entries. That guard passed in the 25-test GitHub Actions run on the repaired branch.

### IR-005 — Published model matrix was stale — STALE DATA / REPAIRED AND REVALIDATED

Baseline `MODEL_COMPARISON_MATRIX.md` centered Claude 3.x, GPT-4o/o1/o3-mini, and Gemini 2.x-era entries.

**Repair:** the matrix was regenerated from the effective verified pricing view supplied by `pricing_engine`. On the 2026-09-15 revalidation pass, every committed base input/output row was checked against the current official provider pricing documentation and matched the published base/standard rates represented by the matrix. The matrix is intentionally a standard comparison, not a representation of every context band, cache rate, service tier, regional modifier, tool charge, promotion, or account-specific condition.

A dedicated regression test regenerates the portable base matrix from the checked-in verified pricing view and fails CI if `MODEL_COMPARISON_MATRIX.md` drifts from the catalog/generator. Runtime generation still consumes a promoted OpenAI overlay when one exists.

For the providers that remain dated catalog entries, `matrix_source_check.py` now performs a separate **non-destructive live source check** against the official Anthropic and Google pricing pages. It anchors parsing inside Anthropic's model-pricing section and Google's Standard pricing section so navigation, promotional copy, Priority, Flex, or Batch repeats cannot accidentally satisfy the base-rate check. It records provider-source hashes and fails when a represented model/rate cannot be found in the applicable base/standard section. It does not rewrite or promote pricing automatically.

The first live IR-005 source-check attempt failed on Claude Fable 5.1 because the initial parser selected an earlier navigation occurrence of the model name instead of the actual pricing table. Inspection confirmed the published Fable rate was still correct; the validator was repaired to anchor to the pricing section and then rerun. The corrected live workflow passed against both Anthropic and Google.

Google's Gemini 3.6/3.7/3.8 Flash promotional matrix records now carry `effective_until: 2026-12-31`. The validator enforces that effective date, including a regression test proving that an expired promotional rate fails after 2026-12-31 even when the historical old dollar value remains visible on the provider page. This prevents a historical rate from being mistaken for a current one merely because the source page still contains both old and future pricing.

**Validation:** on the final IR-005 matrix revision, the clean GitHub Actions regression suite passed **29/29**, and the separate `matrix-source-check` workflow successfully fetched and validated the live Anthropic and Google official pricing pages. No pricing file was modified by that live validator.

### IR-006 — Clean install omitted required dependency — CONFIRMED DEFECT / REPAIRED AND REVALIDATED

Baseline `proxy_server.py` imported `litellm`; baseline `requirements.txt` did not install it.

**Repair:** `litellm` is now a runtime requirement. The proxy guardrail tests were also corrected so they no longer inject a fake `litellm` module that could mask a missing dependency. Clean runtime smoke jobs create fresh virtual environments, install the declared runtime requirements through the validated Python 3.12 constraints, import the real installed LiteLLM package, and verify that `proxy_server.litellm` is that installed module.

**Validation:** clean Ubuntu/Python 3.12 and Windows/Python 3.12 runtime jobs installed the declared requirements, passed `pip check`, imported the production proxy, and verified the real LiteLLM module. The dependency-version reproducibility follow-up is tracked separately as IR-020 and is now repaired/revalidated.

### IR-007 — Circuit breaker reserved input cost only — CONFIRMED SAFETY DEFECT / REPAIRED AND REVALIDATED

Baseline pre-flight called `calculate_cost(pricing, estimated_tokens, 0)` and checked only the input estimate before upstream egress.

**Impact:** a request could pass the pre-flight check and then exceed the amount considered by the budget gate through generated output.

**Repair:** pre-flight now reserves estimated input **and bounded output** using high-side published guard rates for the model actually routed upstream. Caller-supplied `max_tokens` and `max_completion_tokens` are both inspected; if both are present, the larger valid ceiling controls the reservation. Requests without an output bound receive a bounded default constrained by the configured default and remaining budget. The complete reservation is committed through `try_reserve_spend()` before `litellm.acompletion()` begins. Successful responses with usable token counts reconcile the reservation to the supported post-response estimate.

For streams without usable final usage telemetry, the conservative reservation remains on the books and `unreconciled_streams` increments rather than treating the unknown final amount as zero.

**Validation:** the 2026-09-15 IR-007 pass added two direct lifecycle tests without changing production proxy logic. One reads `current_spend_usd` from inside the mocked upstream function and requires it to already equal the full conservative input-plus-output reservation and to exceed the input-only amount. The second returns a stream with no final usage telemetry and requires the same reservation to remain after stream completion while `unreconciled_streams` increments. Existing tests also prove oversized output ceilings block before upstream, conflicting output-bound fields reserve against the larger value, and missing bounds are constrained before egress. The resulting clean regression suite passed **35/35**.

See `docs/IR-007_OUTPUT_RESERVATION_PROOF.md` for the dedicated proof sheet.

### IR-008 — Concurrent requests could race the budget — CONFIRMED SAFETY DEFECT / REPAIRED AND REVALIDATED

Baseline performed read/check/send logic without an atomic reservation. Multiple concurrent calls could each observe the same remaining budget and pass independently.

**Impact:** requests that were individually affordable could collectively cross the configured budget if they performed independent read/check decisions against the same pre-reservation state.

**Repair:** `try_reserve_spend()` now performs the budget check and reservation commit while holding one process-local `threading.RLock`. The accepted reservation, request accounting, and atomic state-file replacement occur inside that critical section before the lock is released.

**Validation:** the 2026-09-15 IR-008 pass added a true simultaneous-thread contention test. Two worker threads are released from the same barrier and each attempts to reserve `$0.06` against a `$0.10` budget. Each request fits alone but the pair cannot fit together. The required result is exactly one accepted reservation and one rejection; final spend must remain `$0.06`, `total_requests` must remain `1`, and the breaker must be locked. The test passed as part of the clean **36/36** regression suite. No production locking code was changed during this pass because the existing hardened implementation satisfied the tested single-process concurrency invariant.

**Boundary:** the lock is process-local. Independent operating-system processes do not share the Python `RLock`, so multiple TokenTotals proxy processes against the same state file remain outside the proven budget invariant.

See `docs/IR-008_CONCURRENT_RESERVATION_PROOF.md` for the dedicated proof sheet.

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

### IR-019 — Auto-economy reservation could price one model and route another — CONFIRMED SAFETY DEFECT / REPAIRED AND REVALIDATED

A regression test added during the hardening pass forced the auto-economy selector to choose a deliberately more expensive model. The proxy returned HTTP 200 even though the routed model's conservative reservation exceeded the configured budget. Inspection showed why: the proxy calculated and committed the budget reservation using the originally requested model, then changed `routed_model` afterward.

**Impact:** any automatic routing decision that selected a more expensive model than the request-side pricing assumption could under-reserve before upstream egress and violate the budget-gate invariant.

**Repair:** route selection now occurs before the budget calculation. The proxy resolves pricing for the exact model that will be sent upstream, estimates/reserves against that routed model, and uses the same routed pricing for response reconciliation. If auto-economy selects a model with no verified pricing, the request fails closed before upstream egress.

**Validation:** the adversarial routed-model test previously failed with HTTP 200 where 403 was required. After the repair, that test passes. It remains part of the current **36/36** clean regression suite.

### IR-020 — Dependency graph was not version-reproducible — CONFIRMED HARDENING DEFECT / REPAIRED AND REVALIDATED

IR-006 repaired the missing runtime dependency, but `requirements.txt` and the Windows packaging path still allowed package versions and transitive dependencies to float across installation dates. PyInstaller was also installed without a version constraint.

**Impact:** two clean installations could satisfy the same top-level requirements while resolving materially different runtime or packaging dependency graphs. Python major/minor mismatch could also present later as a confusing package/runtime failure instead of a clear compatibility error.

**Repair:** `constraints-py312.txt` pins the validated CPython 3.12 runtime/test/build graph, with platform markers where Linux and Windows differ. CI creates fresh virtual environments so unrelated packages preinstalled on hosted runners do not become accidental TokenTotals dependencies. `build.ps1` now refuses Python major/minor versions other than 3.12, installs runtime and PyInstaller dependencies through the same constraints, runs `pip check`, and uses the constrained PyInstaller toolchain.

`runtime_compat.py` defines the validated runtime contract as CPython 3.12.x. The GitHub Actions workflow executes that check in the clean Linux runtime, Windows runtime, Windows build-tool, and regression environments. The workflow is also scheduled daily on the repository default branch so interpreter/dependency drift becomes a failing check rather than a user-discovered runtime surprise.

**Validation:** the final IR-020 revision passed clean constrained runtime/import checks on Ubuntu and Windows, the constrained Windows build-tool check, and **33/33** regression tests. The final Ubuntu regression run reported CPython 3.12.14 and `pip check` reported no broken requirements. An initial workflow revision failed before job creation because of YAML quoting in a Windows inline command; the harness was corrected without changing the lock. A full-file integrity check also caught an over-broad intermediate `proxy_server.py` edit, and that file was restored byte-for-byte to the pre-change hardened blob before final validation.

**Boundary:** this is version reproducibility for the validated CPython 3.12 dependency graph. Package hashes are not pinned, so this is not a cryptographic package-artifact or supply-chain guarantee.

See `docs/IR-020_DEPENDENCY_REPRODUCIBILITY_PROOF.md` for the detailed proof sheet.

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

Current GitHub Actions regression suite on the hardened branch: **36 passed / 0 failed** on Ubuntu/Python 3.12.

Regression coverage includes:

1. verified input + output cost math;
2. conservative guard rate >= displayed base estimate;
3. strict alias resolution, no fuzzy model pricing;
4. unknown model pricing fails closed;
5. atomic reservation blocks sequential over-budget reservations;
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
21. proxy imports the real installed LiteLLM runtime dependency in the clean CI environment;
22. conflicting output-bound fields reserve against the largest supplied ceiling;
23. auto-economy reservations follow the model actually routed upstream;
24. blanket “all providers audited live” pricing claims cannot return to public claim surfaces;
25. public documentation must preserve the actual provider synchronization scope;
26. Anthropic live-rate validation anchors to the actual model-pricing section instead of navigation occurrences;
27. Google live-rate validation anchors to the Standard section instead of promotional/Priority repeats;
28. live matrix-source rate drift fails rather than silently accepting a changed number;
29. effective-dated promotional pricing fails after expiration even if the old historical rate remains on the provider page;
30. top-level runtime requirements are covered by the Python 3.12 constraints;
31. clean constrained Linux and Windows runtime environments remain part of CI;
32. the Python 3.12 compatibility contract, CI interpreters, and Windows build requirement cannot silently diverge;
33. the Windows packaging path remains bound to the constrained PyInstaller dependency graph;
34. the full conservative input-plus-output reservation is committed before upstream execution begins;
35. a stream without final usage retains its conservative reservation and is marked unreconciled;
36. two simultaneous in-process reservations that cannot both fit the remaining budget produce exactly one acceptance and one rejection.

IR-003 additionally has a separate live-source validation workflow. On 2026-09-15 it fetched the supported OpenAI model pages directly from `developers.openai.com`, parsed and validated the temporary candidate successfully, and recorded source hashes/rates without promoting or modifying the runtime snapshot.

IR-005 additionally has a separate `matrix-source-check` workflow. On the 2026-09-15 revalidation pass it fetched the live Anthropic and Google official pricing pages, validated the dated catalog's represented base/standard rates, and completed successfully without changing or promoting pricing data.

IR-020 additionally has clean-environment Linux runtime, Windows runtime, and Windows build-tool jobs using the same CPython 3.12 constraints. The same workflow carries a daily schedule on the default branch to detect future Python-version or dependency-resolution drift.

## Remaining limitations before calling this production-proven

- The 36-test suite is focused regression coverage, not a full integration or load test.
- The live OpenAI, Anthropic, and Google source checks prove the currently supported source pages can be fetched and parsed at the recorded time; future provider page changes can still break parsing. Such failures must be surfaced for review rather than treated as proof that the provider price changed.
- No live paid provider request was executed during this review; doing so should use intentionally tiny limits and test keys.
- Multi-process workers are not supported for the file-lock budget invariant; the current lock is process-local. Run one TokenTotals proxy process unless cross-process locking is added.
- OpenAI source synchronization does not by itself implement every OpenAI billing dimension in transaction accounting. Tool-call fees, image/audio billing, prompt caching details, service tiers, regional variations, provider promotions, and other applicable meters require explicit accounting support before they can be represented as a high-confidence provider-rule estimate.
- Anthropic and Google have live source-drift validation for their dated matrix/catalog entries, but they do not yet have the dynamic promoted runtime-pricing adapter implemented for OpenAI.
- Streaming responses without final usage retain the worst-case reservation and are marked unreconciled rather than guessed.
- Dependency versions are constrained for the validated CPython 3.12 graph, but package hashes are not pinned; external package repositories remain part of the installation trust chain.
- Vendor prices and page structures change. Source verification evidence records what was checked; it is not a promise that a provider cannot later change either pricing or documentation format.

## Integrity conclusion

The baseline repository was **not an empty shell**. Its proxy, local state, GUI lock dialog, and routing path were substantive. However, it contained several material integrity failures: machine-specific dependencies, silent invented pricing, disconnected sync logic, stale matrix data, an input-only safety check, API bypasses, race-prone accounting, and hard-coded dashboard telemetry presented as live-looking metrics. Documentation also exceeded implementation in several places. The hardening pass additionally caught a routed-model reservation ordering defect and a dependency-reproducibility gap before release.

The hardening branch removes the known silent fabrication/fallback paths and changes the governing rule to: **unknown or unreconciled data stays unknown/conservative; it is never converted into a plausible-looking number merely to keep the UI green.**
