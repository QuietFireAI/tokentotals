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
- **EVIDENCE GAP** — important behavior existed or appeared plausible but lacked direct validation at the stated boundary.
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

**Repair:** the matrix was regenerated from the effective verified pricing view supplied by `pricing_engine`. On the 2026-09-15 revalidation pass, every committed base input/output row was checked against the current official provider pricing documentation and matched the published base/standard rates represented by the matrix. The matrix is intentionally a verified comparison of the models represented by TokenTotals, not a representation of every provider model or every context band, cache rate, service tier, regional modifier, tool charge, promotion, modality, or account-specific condition.

`generate_model_matrix.py` now owns both public comparison surfaces: `MODEL_COMPARISON_MATRIX.md` and a marked current-pricing block in `README.md`. Both are rendered from the same `pricing_engine` view. CI requires the committed matrix and the README block to exactly match generator output from the checked-in verified pricing view, and it explicitly rejects reintroduction of the old GPT-4o/o1/o3-mini/Claude-3.x/Gemini-2.x comparison rows. Runtime generation still consumes a promoted OpenAI overlay when one exists.

The generated matrix now exposes the calculation instead of presenting only a price table. For the example workload of 10,000 input tokens plus 2,000 output tokens it shows both:

```text
base_estimate = (input_tokens / 1,000,000 × base_input_rate)
              + (output_tokens / 1,000,000 × base_output_rate)

reservation = (estimated_input_tokens / 1,000,000 × guard_input_rate)
            + (bounded_output_tokens / 1,000,000 × guard_output_rate)
```

The first is an independent base/standard approximation. The second is TokenTotals' high-side pre-flight pacing reservation. Neither is represented as a provider invoice.

For providers that remain dated catalog entries, `matrix_source_check.py` performs a separate **non-destructive live source check** against the official Anthropic and Google pricing pages. Base rates are anchored to Anthropic's model-pricing table and Google's Standard section. Following the later IR-021 stop-line finding, the same live checker also validates the represented conservative guard rates against the applicable official high-side pricing section; for Google this revision uses the Priority pricing table. It records provider-source hashes and fails when a represented base or guard rate cannot be found. It never rewrites or promotes pricing automatically.

The first live IR-005 source-check attempt failed on Claude Fable 5.1 because the initial parser selected an earlier navigation occurrence of the model name instead of the actual pricing table. Inspection confirmed the published Fable rate was still correct; the validator was repaired to anchor to the pricing section and then rerun. The corrected live workflow passed against both Anthropic and Google.

Google's Gemini 3.6/3.7/3.8 Flash promotional matrix records carry `effective_until: 2026-12-31`. The validator enforces that effective date, including a regression test proving that an expired promotional rate fails after 2026-12-31 even when the historical old dollar value remains visible on the provider page. This prevents a historical rate from being mistaken for a current one merely because the source page still contains both old and future pricing.

**Historical validation:** on the original completed IR-005 matrix revision, the clean GitHub Actions regression suite passed **29/29**, and the separate `matrix-source-check` workflow successfully fetched and validated the live Anthropic and Google official pricing pages. No pricing file was modified by that live validator.

**2026-09-15 stop-line revalidation:** a later release-facing review found that the unmerged `main` branch still visibly contained the old GPT-4o-era README/matrix while the hardening branch carried the current model set. The hardening branch was strengthened so the README and matrix are generated from one pricing truth and cannot drift independently. During that review, exposing and re-verifying the conservative guard math found the separate IR-021 Google Flash-Lite guard-rate defect. After correcting the catalog and extending the live checker to base **and guard** rates, the clean suite passed **51/51** and the separate live source check fetched the current Anthropic/Google pages and passed without modifying pricing data.

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

### IR-009 — Global per-request callback state — CONFIRMED CONCURRENCY DEFECT / REPAIRED AND REVALIDATED

Baseline used shared request-scoped module globals (`CURRENT_THREAD_ID`, `CURRENT_ROUTINE_FLAG`, `CURRENT_POTENTIAL_SAVING`) for data consumed later by a LiteLLM callback. Those variables were ordinary Python state, but they were unsafe under concurrent requests because one in-flight request could overwrite values before another request's callback used them.

**Impact:** overlapping requests could attribute spend, routine classification, or potential-savings accounting using another request's identity or metadata.

**Repair:** the shared request-scoped globals and callback accounting path were removed. `thread_id`, `is_routine`, `potential_saving`, routed pricing, reservation amount, and reconciliation context remain local to each request and are passed explicitly into the state-management functions that need them. The surviving `LAST_LATENCY_MS` module value is aggregate dashboard telemetry and is not used for request spend/thread/savings attribution.

**Validation:** the 2026-09-15 IR-009 pass added two regression guards without changing production proxy logic. One fails if the baseline request-scoped global names or old `track_cost_callback` symbol reappear. The second launches two overlapping HTTP requests with distinct thread IDs and deliberately different classification outcomes. A barrier inside the mocked upstream function prevents either response from finishing until both requests are simultaneously in flight. The short request must carry `is_routine=True` and a positive potential-savings estimate; the long request must carry `is_routine=False` and zero potential-savings metadata. Reservation and reconciliation instrumentation must preserve each request's own thread ID. The test passed as part of the clean **38/38** regression suite, with exactly two requests recorded and exactly one routine call.

**Boundary:** `active_thread_id` / `thread_spend_usd` remain a single display slot and may legitimately move to the most recently active thread. They are not represented as a historical per-thread ledger. IR-009 concerns cross-request attribution of request-local accounting context, which the overlap test revalidates.

See `docs/IR-009_REQUEST_CONTEXT_ISOLATION_PROOF.md` for the dedicated proof sheet.

### IR-010 — `/api/unlock` claimed acknowledgment it never verified — CONFIRMED INTEGRITY DEFECT / REPAIRED AND REVALIDATED

Baseline `/api/unlock` was unconditional. It did not read or require request-supplied acknowledgment data before calling `unlock_circuit_breaker()`, yet it returned:

```text
Circuit breaker unlocked by user acknowledgment.
```

The important defect was not that one special malformed value could fool a check; there was no HTTP acknowledgment decision at all. Once a POST reached the handler, request input was irrelevant to the unlock outcome. The Windows Tk dialog separately verified `I UNDERSTAND`, so acknowledgment protection existed in the native UI but not in the HTTP path.

**Impact:** an HTTP caller could clear the budget lock without demonstrating the acknowledgment that the endpoint claimed had occurred.

**Repair:** `/api/unlock` now parses the request body and validates the `acknowledgement` field before it calls the state transition. The required phrase is `I UNDERSTAND`. The validator intentionally trims surrounding whitespace and compares letter case insensitively; different wording is rejected. This is an explicit acknowledgment gate, not an authentication mechanism.

`unlock_circuit_breaker()` changes only `is_locked` to `False`. It does not reset recorded spend, request counts, savings, thread accounting, unreconciled-stream count, or the configured daily budget.

**Validation:** the 2026-09-15 IR-010 pass added three focused tests. Missing body, malformed JSON, empty JSON, `YES`, and `I UNDERSTAND THIS` were rejected and left the state locked. A normalization test proved `"  i understand  "` is intentionally accepted. A state-integrity test seeded non-default spend, budget, request, savings, thread, and unreconciled values and proved valid acknowledgment changes only `is_locked`. The clean regression suite passed **41/41** on the IR-010 revision.

IR-011 subsequently added a shared transport gate for the HTTP state-changing controls: `/api/unlock` and `/api/boost` now require `Content-Type: application/json` and an object payload before their phrase checks run. The unlock regression was extended to prove explicit JSON `null` and browser-style `text/plain` cannot unlock. This strengthens the transport boundary without changing the IR-010 acknowledgment invariant.

See `docs/IR-010_UNLOCK_ACKNOWLEDGEMENT_PROOF.md` for the dedicated proof sheet.

### IR-011 — Budget boost endpoint could be invoked without confirmation — CONFIRMED CONTROL DEFECT / REPAIRED AND REVALIDATED

Baseline `/api/boost` raised the daily budget by `$5.00` and cleared the lock immediately, without reading any request-supplied confirmation. The baseline application also installed permissive CORS middleware allowing arbitrary origins, methods, and headers.

**Impact:** the HTTP budget-control path could change the configured spending ceiling and lock state without demonstrating an intentional boost action.

**First repair and adversarial finding:** the initial hardening removed permissive CORS and required the `BOOST $5` acknowledgment phrase. During IR-011 revalidation, a new browser-style test deliberately sent the correct JSON-formatted phrase in a cross-origin `Content-Type: text/plain` POST. That request unexpectedly returned **HTTP 200** and performed the boost. The handler's `request.json()` call parsed the JSON-formatted body despite the declared text/plain media type. Because a browser can send certain text/plain cross-origin POSTs without a CORS preflight, phrase validation plus removal of permissive CORS was not sufficient by itself.

**Final repair:** a shared `_read_state_action_json()` gate now sits before both HTTP state-changing controls (`/api/boost` and `/api/unlock`). It requires `Content-Type: application/json`, valid JSON, and a JSON object before acknowledgment validation. `/api/boost` then requires the `BOOST $5` phrase; the API trims surrounding whitespace and compares letter case insensitively, while different wording is rejected. TokenTotals grants no tested foreign-origin CORS preflight permission. Native Windows tray/popup boost actions remain explicit local user actions and call the state manager directly rather than the HTTP endpoint.

A valid boost changes exactly two intended values: `daily_budget_limit_usd` increases by `$5.00`, and `is_locked` becomes `False`. It does not erase or reset existing spend, request, savings, thread, routine-call, or unreconciled-stream accounting.

**Validation:** the evidence chain preserves both failures rather than hiding them. The first adversarial run failed **1 test / 43 passed** because the browser-style text/plain request returned HTTP 200, exposing the incomplete repair. After the production transport gate was added, a second run had **2 failed / 43 passed** because `TestClient(json=None)` did not actually send an application/json null body and therefore correctly received HTTP 415 rather than the test's expected 400; this was a harness ambiguity, not a state-mutation failure. The tests were corrected to send an explicit body `null` with `Content-Type: application/json`. The corrected repair run passed **45/45**. It proves text/plain is rejected before mutation, CORS preflight is not granted, missing/null/empty/wrong confirmation cannot change config or state, and valid boost changes only the `$5` limit increase plus lock release.

**Boundary:** this is a localhost HTTP intent/transport control, not authentication against a malicious local process already running with the user's privileges. A deliberate local program can still call the loopback endpoint with valid JSON and the published acknowledgment phrase.

See `docs/IR-011_BOOST_AND_BROWSER_ORIGIN_PROOF.md` for the dedicated proof sheet.

### IR-012 — Dashboard telemetry numbers were hard-coded — FABRICATED / PLACEHOLDER TELEMETRY — REPAIRED AND REVALIDATED

Baseline HTML embedded fixed values directly in metric cards styled as live operational state:

- `~199k tok/turn`
- `14.5M tokens processed`
- `~85% Hit`
- “Prompt caching discount active”

The dashboard refresh path did not populate those fields from `/api/status` or another measured runtime source.

**Impact:** a user could reasonably interpret fixed demonstration/placeholder values as measured session telemetry. The integrity problem was not merely that those three numbers could become stale; TokenTotals did not have an implemented runtime source for the token-velocity, cumulative-token, cache-hit, or prompt-caching-status surfaces being shown.

**Repair:** the unsupported metric cards were removed rather than replaced with different plausible values. The surviving operational dashboard fields are populated from runtime `/api/status` data. Unknown or unavailable telemetry remains absent/unknown rather than being filled with demonstration numbers.

**Validation:** the earlier guard only rejected the original constants (`199k`, `14.5M`, `85%`). IR-012 strengthened this into two complementary gates. First, the regression test rejects the old values plus the unsupported semantic/UI surfaces themselves (`tok/turn`, `tokens processed`, `Prompt Cache Savings`, `Prompt caching discount active`, `velocityVal`, `cumulTokVal`, and `cacheVal`), so merely changing the numbers cannot recreate the same presentation-integrity defect. Second, a positive-source test seeds non-default runtime state, verifies those values through `/api/status`, and checks that the dashboard refresh code consumes the corresponding status fields for the dynamic metrics it does display. The clean regression suite passed **46/46**, and the same revision passed Linux runtime, Windows runtime, and Windows constrained build-tool smoke checks.

No production proxy change was required during the IR-012 revalidation because the earlier hardening had already removed the unsupported cards. This pass strengthened the proof and regression boundary.

**Integrity rule:** a value may be presented as live/runtime telemetry only when TokenTotals has an implemented runtime source for it. If real token-velocity or cache telemetry is implemented later, the current ban must be deliberately replaced by source-backed implementation and tests.

See `docs/IR-012_DASHBOARD_TELEMETRY_INTEGRITY_PROOF.md` for the dedicated proof sheet.

### IR-013 — “Turn-by-turn chat telemetry badge” — UNSUPPORTED CLAIM / REPAIRED AND REVALIDATED

Baseline README said every developer turn or agent interaction rendered a live telemetry badge directly in the working context. No corresponding IDE/chat injection adapter or render lifecycle exists in the reviewed proxy, GUI, or dashboard implementation.

**Impact:** users could reasonably expect TokenTotals telemetry to appear inside each IDE/chat turn when the repository actually supplied a separate localhost dashboard/tray plus transaction accounting around the proxy.

**Repair:** the implemented-feature claim was removed. The current README explicitly states that TokenTotals does not inject a telemetry badge into every IDE/chat turn. No production feature was invented merely to preserve the old marketing language.

**Validation:** IR-013 added two guards. The public-claim integrity suite rejects the old turn-by-turn badge language and requires the explicit non-implementation statement. A separate proxy regression sends known provider assistant content through the real non-stream FastAPI path and requires the content to return unchanged, with no TokenTotals badge decoration injected into the response. These guards passed as part of the subsequent **51/51** clean regression suite.

**Boundary:** an in-context badge may be a future feature, but it must have a real host/IDE/chat adapter and tests before TokenTotals may describe it as implemented.

See `docs/IR-013_TELEMETRY_BADGE_CLAIM_PROOF.md` for the dedicated proof sheet.

### IR-014 — “BPE token count” / unsupported precision language — UNSUPPORTED CLAIM / REPAIRED AND REVALIDATED

Baseline public documentation described the pre-flight count as a BPE token count even though the reviewed implementation did not execute a verified provider/model tokenizer for that pre-flight estimate. Baseline README architecture copy said **“Pre-flight BPE token count & budget audit,”** while the whitepaper described **“pre-flight cryptographic/BPE token counts.”**

**Impact:** the public wording implied model/provider tokenization precision that the implementation did not provide.

**Repair:** the current pre-flight estimator is explicitly defined as a local pacing heuristic:

```text
estimated_tokens = max(1, ceil(len(text encoded as UTF-8 bytes) / 3))
```

The optional model argument does not alter that calculation. Current README and whitepaper wording explicitly state that TokenTotals does not represent this value as a provider/model BPE count. `docs/TOKEN_ESTIMATION_CONTRACT.md` makes that boundary normative and prohibits BPE/exact/provider-accurate/model-specific tokenization claims unless a future implementation actually executes and validates the applicable tokenizer. No production estimator was rewritten merely to preserve the old marketing claim.

**Validation:** three independent guards now cover the lifecycle. The pricing-engine regression proves the exact UTF-8-byte heuristic and proves the same text receives the same estimate across representative OpenAI, Anthropic, and Google model names. The public-claim integrity regression rejects the old BPE/exact/provider-accurate wording. Finally, `tests/test_ir014_token_estimation_boundary.py` deliberately forces the local estimate to **10,000 input tokens** while the mocked provider reports **7 input + 3 output tokens**. The test captures the larger pre-flight reservation and requires the persisted final spend to reconcile to the supported calculation using the provider-reported 7/3 usage rather than retaining the heuristic amount.

**Result:** GitHub Actions run `34990973664` on commit `f9decbafa2f9fbc1cfd9dac0d94464a890828fac` passed **64/64** tests on Ubuntu / CPython 3.12.14, plus Linux runtime smoke, Windows runtime smoke, Windows constrained PyInstaller/build-tool smoke, and `pip check`.

**Boundary:** provider-reported usage is stronger observed telemetry than the local pre-flight heuristic, but the resulting dollar value remains an independent estimate rather than invoice parity. A future true tokenizer integration must define and validate tokenizer/model mappings, version provenance, request serialization, aliases/snapshots, unsupported-model behavior, and reference fixtures before stronger tokenization language is permitted.

See `docs/IR-014_TOKEN_ESTIMATION_PRECISION_PROOF.md` and `docs/TOKEN_ESTIMATION_CONTRACT.md` for the dedicated proof and normative contract.

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

**Validation:** the adversarial routed-model test previously failed with HTTP 200 where 403 was required. After the repair, that test passes. It remains part of the current **51/51** clean regression suite.

### IR-020 — Dependency graph was not version-reproducible — CONFIRMED HARDENING DEFECT / REPAIRED AND REVALIDATED

IR-006 repaired the missing runtime dependency, but `requirements.txt` and the Windows packaging path still allowed package versions and transitive dependencies to float across installation dates. PyInstaller was also installed without a version constraint.

**Impact:** two clean installations could satisfy the same top-level requirements while resolving materially different runtime or packaging dependency graphs. Python major/minor mismatch could also present later as a confusing package/runtime failure instead of a clear compatibility error.

**Repair:** `constraints-py312.txt` pins the validated CPython 3.12 runtime/test/build graph, with platform markers where Linux and Windows differ. CI creates fresh virtual environments so unrelated packages preinstalled on hosted runners do not become accidental TokenTotals dependencies. `build.ps1` now refuses Python major/minor versions other than 3.12, installs runtime and PyInstaller dependencies through the same constraints, runs `pip check`, and uses the constrained PyInstaller toolchain.

`runtime_compat.py` defines the validated runtime contract as CPython 3.12.x. The GitHub Actions workflow executes that check in the clean Linux runtime, Windows runtime, Windows build-tool, and regression environments. The workflow is also scheduled daily on the repository default branch so interpreter/dependency drift becomes a failing check rather than a user-discovered runtime surprise.

**Validation:** the final IR-020 revision passed clean constrained runtime/import checks on Ubuntu and Windows, the constrained Windows build-tool check, and **33/33** regression tests. The final Ubuntu regression run reported CPython 3.12.14 and `pip check` reported no broken requirements. An initial workflow revision failed before job creation because of YAML quoting in a Windows inline command; the harness was corrected without changing the lock. A full-file integrity check also caught an over-broad intermediate `proxy_server.py` edit, and that file was restored byte-for-byte to the pre-change hardened blob before final validation.

**Boundary:** this is version reproducibility for the validated CPython 3.12 dependency graph. Package hashes are not pinned, so this is not a cryptographic package-artifact or supply-chain guarantee.

See `docs/IR-020_DEPENDENCY_REPRODUCIBILITY_PROOF.md` for the detailed proof sheet.

### IR-021 — Google Flash-Lite guard rates understated/misaligned high-side text pricing — CONFIRMED SAFETY / PRICING-INTEGRITY DEFECT / REPAIRED AND REVALIDATED

During the stop-the-line public-matrix review, the ordinary Google Standard/base rates were still correct, but exposing and rechecking the conservative guard layer found two defects.

The catalog previously used Gemini 3.5 Flash-Lite guard rates of `$0.594` input / `$2.75` output per 1M and Gemini 3.1 Flash-Lite guard rates of `$0.55` input / `$1.65` output per 1M. The current official Google pricing page publishes higher Priority non-global **text** values represented by the corrected guard: `$0.594 / $4.95` for Gemini 3.5 Flash-Lite and `$0.495 / $2.97` for Gemini 3.1 Flash-Lite. The old Gemini 3.1 input value also did not align cleanly with the current high-side text path; audio is a separate modality and is not silently folded into the current text-token estimator.

**Impact:** TokenTotals uses guard rates to reserve budget before egress. A guard below a represented high-side text service-mode/geography rate could under-reserve a request even though the displayed Standard/base estimate was correct.

**Repair:** the two catalog records were corrected. For the 10,000-input / 2,000-output comparison, Gemini 3.5 Flash-Lite remains `$0.008000` at its Standard/base rate but now reserves `$0.015840`; Gemini 3.1 Flash-Lite remains `$0.005500` at its Standard/base rate but now reserves `$0.010890`.

The prior daily Anthropic/Google source checker validated only base/Standard rows. It now separately validates represented guard fields against the applicable official high-side section; for Google this revision anchors guard validation to the Priority table. A negative regression deliberately restores the old `$2.75` Gemini 3.5 Flash-Lite guard and requires the validator to fail rather than accepting that lower Standard value as a valid conservative guard.

**Validation:** the corrected branch passed **51/51** regression tests, Linux runtime smoke, Windows runtime smoke, Windows constrained build-tool smoke, and `pip check`. The separate live `matrix-source-check` workflow fetched the current Anthropic and Google official pages and passed with audit output containing the corrected Flash-Lite base and guard values. The live validator did not modify pricing files.

**Boundary:** these are high-side text-token guards for the published dimensions represented by this catalog revision, not a claim that TokenTotals has modeled every modality, hosted tool, grounding/search event, storage/runtime meter, account-specific term, or future provider billing rule.

See `docs/IR-021_GOOGLE_FLASH_LITE_GUARD_RATE_PROOF.md` for the dedicated proof sheet.

### IR-022 — Real loopback HTTP integration/load behavior lacked direct proof — EVIDENCE GAP / REVALIDATED

The hardened suite already exercised pricing, routing, state transitions, and concurrency, but most HTTP route tests used FastAPI/Starlette `TestClient`. That left an evidence gap at the actual Uvicorn + loopback TCP boundary used by the production proxy.

**Validation approach:** `tests/test_http_integration_load.py` starts the production `proxy_server.app` behind a real Uvicorn listener on an ephemeral `127.0.0.1` port and sends requests through `httpx` over the actual loopback HTTP/TCP path. The upstream provider call is deliberately mocked so the test isolates TokenTotals' local transport, reservation, reconciliation, and state behavior without spending provider money.

The first test proves a real loopback `/v1/chat/completions` round trip returns provider content unchanged, records one request, exposes the reconciled value through `/api/status`, and reconciles the conservative reservation to the expected usage-based estimate. The second test releases **24 client threads simultaneously** against the real Uvicorn listener while the mocked async upstream delays briefly to force overlap. All 24 requests must succeed, the upstream count must be exactly 24, `total_requests` must be exactly 24, final spend must equal the sum of the 24 reconciled estimates, and no unreconciled stream or accidental budget lock may appear.

**Result:** no production-code change was required. GitHub Actions proof run `34984018982` passed **55/55** tests on Ubuntu / CPython 3.12, plus the constrained Linux runtime smoke, Windows runtime smoke, Windows PyInstaller toolchain smoke, and dependency checks.

**Boundary:** this is a controlled single-process local integration/concurrency burst with mocked provider egress. It does not claim unlimited production throughput, sustained soak endurance, multi-process safety, provider-network reliability, invoice parity, or a live paid-provider canary.

See `docs/IR-022_HTTP_INTEGRATION_LOAD_PROOF.md` for the dedicated proof sheet.

### IR-023 — Sustained repeated-concurrency behavior lacked direct proof — EVIDENCE GAP / REVALIDATED

IR-022 proved a single real loopback round trip and one 24-request overlapping burst, but it did not show whether repeated concurrent reservation/reconciliation cycles would accumulate state drift over time.

**Validation approach:** the existing real-Uvicorn harness was extended rather than replaced with a synthetic benchmark. `tests/test_http_integration_load.py` now executes **8 successive rounds of 32 simultaneous loopback HTTP requests — 256 total requests** — against the production FastAPI application. Provider egress remains mocked so the test isolates TokenTotals' own HTTP, reservation, reconciliation, and state behavior without spending provider money.

After every one of the eight rounds, the test requires the cumulative upstream count, `total_requests`, and `current_spend_usd` to equal the exact expected values. It also requires `unreconciled_streams == 0`, `is_locked == False`, and `/api/status` to report the same request count and spend as persisted state. Checking every round prevents an early lost update from being hidden by a plausible final value.

**Result:** no production-code change was required. GitHub Actions proof run `34985140692` on commit `0c37ea2533e63788d085c427b3d1bae4739a7941` passed **56/56** tests on Ubuntu / CPython 3.12.14, plus Linux runtime smoke, Windows runtime smoke, Windows constrained PyInstaller/build-tool smoke, and `pip check`. The full regression/integration suite completed in 10.48 seconds on the hosted runner.

**Boundary:** this is a bounded integrity soak, not a production-capacity benchmark. It proves the tested single-process envelope of 32 simultaneous requests repeated for 8 rounds / 256 total requests. Higher concurrency, longer hours/days soak duration, multi-process behavior, paid-provider/network behavior, and maximum production throughput remain uncharacterized.

See `docs/IR-023_SUSTAINED_CONCURRENCY_SOAK_PROOF.md` for the dedicated proof sheet.

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

Current GitHub Actions regression/integration suite on the hardened branch: **64 passed / 0 failed** on Ubuntu/Python 3.12.

Regression/integration coverage includes:

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
12. baseline fabricated dashboard values and unsupported token/cache telemetry surfaces cannot regress unnoticed;
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
27. Google live base-rate validation anchors to the Standard section instead of promotional/Priority repeats;
28. live base-rate drift fails rather than silently accepting a changed number;
29. effective-dated promotional pricing fails after expiration even if the old historical rate remains on the provider page;
30. top-level runtime requirements are covered by the Python 3.12 constraints;
31. clean constrained Linux and Windows runtime environments remain part of CI;
32. the Python 3.12 compatibility contract, CI interpreters, and Windows build requirement cannot silently diverge;
33. the Windows packaging path remains bound to the constrained PyInstaller dependency graph;
34. the full conservative input-plus-output reservation is committed before upstream execution begins;
35. a stream without final usage retains its conservative reservation and is marked unreconciled;
36. two simultaneous in-process reservations that cannot both fit the remaining budget produce exactly one acceptance and one rejection;
37. baseline request-scoped accounting globals and the old callback symbol cannot silently return;
38. overlapping requests preserve distinct thread identity and routine/savings context through reservation and reconciliation;
39. missing, malformed, empty, or wrong HTTP unlock acknowledgments cannot clear the lock;
40. unlock acknowledgment normalization (surrounding whitespace/case) is intentional and tested;
41. valid HTTP unlock changes only the lock flag and preserves accounting plus configured budget;
42. browser-style cross-origin `text/plain` state-control POSTs are rejected before boost/unlock mutation;
43. the boost endpoint does not grant the tested foreign-origin CORS preflight;
44. missing, explicit JSON `null`, empty, or wrong boost confirmation cannot change budget or lock state;
45. valid HTTP boost changes only the daily budget by `$5.00` and releases the lock while preserving accounting;
46. displayed dynamic dashboard metrics are tied to implemented `/api/status` fields rather than unsupported static values;
47. unsupported turn-by-turn telemetry-badge claims cannot return to the public claim surfaces;
48. non-stream provider assistant content remains pass-through and is not silently decorated with TokenTotals badge content;
49. the README verified-pricing block must exactly match the generator/current verified pricing view and stale GPT-4o/o1/o3-mini/Claude-3.x/Gemini-2.x comparison rows cannot return;
50. Google conservative guard rates are positively validated against the official Priority pricing section used for this revision's high-side text guard;
51. a lower Standard value cannot satisfy the Google guard check when the official Priority section publishes a higher represented rate;
52. a verified pricing receipt at exactly 24 hours old remains current;
53. a pricing receipt older than 24 hours fails the freshness gate instead of being treated as current;
54. a real Uvicorn/loopback HTTP chat-completion round trip reconciles state and exposes the same reconciled spend through `/api/status`;
55. a 24-request overlapping loopback HTTP burst preserves every request and reconciled spend update without creating an unreconciled stream or accidental lock;
56. eight successive 32-request loopback bursts (256 requests total) preserve exact cumulative request/spend accounting at every round with no unreconciled streams or accidental lock;
57. the current pre-flight token estimator is exactly the documented UTF-8-byte heuristic and is model-independent;
58. public claim surfaces cannot describe the current pre-flight heuristic as BPE, exact, deterministic-provider, cryptographic, or provider-accurate tokenization;
59. the pricing-integrity workflow is schedule-driven by one fixed daily UTC cron, retains manual dispatch, and has no price-change/push trigger;
60. the daily success email is built from the generated pricing-status receipt, uses the exact published commit SHA, and targets `dailyreport@firelandsai.com`;
61. missing required SMTP configuration fails loudly rather than pretending a daily email was sent;
62. each successful daily pricing status is archived byte-for-byte at a unique UTC timestamped repository path;
63. an existing daily archive receipt cannot be overwritten by a later refresh using the same timestamp; and
64. usable provider-reported input/output usage supersedes an intentionally divergent local pre-flight token heuristic during supported post-response reconciliation.

IR-003 additionally has a separate live-source validation workflow. On 2026-09-15 it fetched the supported OpenAI model pages directly from `developers.openai.com`, parsed and validated the temporary candidate successfully, and recorded source hashes/rates without promoting or modifying the runtime snapshot.

IR-005/IR-021 additionally use the separate `matrix-source-check` workflow. On the 2026-09-15 stop-line revalidation it fetched the live Anthropic and Google official pricing pages, validated the dated catalog's represented base/standard **and conservative guard** rates, recorded provider source hashes, and completed successfully without changing or promoting pricing data.

IR-020 additionally has clean-environment Linux runtime, Windows runtime, and Windows build-tool jobs using the same CPython 3.12 constraints. The same workflow carries a daily schedule on the default branch to detect future Python-version or dependency-resolution drift.

The daily pricing-integrity path is now **schedule-first rather than change-triggered**. The workflow runs once per day at `05:05 UTC` plus explicit manual dispatch. A successful run verifies provider sources, regenerates the catalog-derived matrix/README/whitepaper/status calculations, writes an immutable timestamped copy under `docs/pricing_archive/YYYY/MM/`, runs the telemetry-honesty and full regression gates, publishes the allowed surfaces plus archive in one atomic commit, and then attempts to email the generated daily status to `dailyreport@firelandsai.com`. The 24-hour check is a validator/watchdog proving the last successfully published verified refresh is still current; it is not the mechanism that triggers refresh. A receipt at 24:00:00 remains current and at 24:00:01 fails closed. The unattended cron becomes operational only when the workflow exists on the repository default branch; actual email delivery additionally requires the documented SMTP repository secrets. `main` remains untouched during this hardening review.

IR-022 additionally runs the production FastAPI app behind a real Uvicorn `127.0.0.1` listener and exercises both a single TCP round trip and a 24-request overlapping local burst. Provider egress is mocked in that proof so no paid-provider claim is inferred from the local integration result.

IR-023 extends that same real-loopback harness through eight repeated 32-request bursts. It is an integrity soak for cumulative accounting correctness, not a throughput rating.

IR-014 additionally has a dedicated normative token-estimation contract. The current pre-flight estimate is a local pacing heuristic, while usable provider-reported token usage is the stronger observed quantity for the supported post-response reconciliation path.

## Remaining limitations before calling this production-proven

- Real loopback HTTP integration and a bounded sustained-concurrency envelope are now proven through **32 simultaneous requests repeated for 8 rounds / 256 total requests**. Higher concurrency, hours/days soak duration, multi-process behavior, and production capacity limits remain uncharacterized.
- The HTTP acknowledgment phrases are intent gates, not authentication secrets. A malicious local process running with the user's privileges can deliberately call loopback control endpoints with valid JSON and the published phrase.
- The live OpenAI, Anthropic, and Google source checks prove the currently supported source pages can be fetched and parsed at the recorded time; future provider page changes can still break parsing. Such failures must be surfaced for review rather than treated as proof that the provider price changed.
- No live paid provider request was executed during this review; doing so should use intentionally tiny limits and test keys.
- Multi-process workers are not supported for the file-lock budget invariant; the current lock is process-local. Run one TokenTotals proxy process unless cross-process locking is added.
- OpenAI source synchronization does not by itself implement every OpenAI billing dimension in transaction accounting. Tool-call fees, image/audio billing, prompt caching details, service tiers, regional variations, provider promotions, and other applicable meters require explicit accounting support before they can be represented as a high-confidence provider-rule estimate.
- Anthropic and Google have live source-drift validation for their dated catalog base and represented guard rates, but they do not yet have the dynamic promoted runtime-pricing adapter implemented for OpenAI.
- Streaming responses without final usage retain the worst-case reservation and are marked unreconciled rather than guessed.
- The unattended daily pricing cron is not operational until the workflow is present on the repository default branch, and the daily email cannot be delivered until the documented SMTP secrets are configured.
- Dependency versions are constrained for the validated CPython 3.12 graph, but package hashes are not pinned; external package repositories remain part of the installation trust chain.
- Vendor prices and page structures change. Source verification evidence records what was checked; it is not a promise that a provider cannot later change either pricing or documentation format.

## Integrity conclusion

The baseline repository was **not an empty shell**. Its proxy, local state, GUI lock dialog, and routing path were substantive. However, it contained several material integrity failures: machine-specific dependencies, silent invented pricing, disconnected sync logic, stale matrix data, an input-only safety check, API bypasses, race-prone accounting, and hard-coded dashboard telemetry presented as live-looking metrics. Documentation also exceeded implementation in several places. The hardening pass additionally caught a routed-model reservation ordering defect, a dependency-reproducibility gap, an incomplete first browser-origin defense on the budget-control endpoint, and understated/misaligned Google Flash-Lite conservative guard rates before release. It also closed the prior local integration/load and bounded sustained-concurrency evidence gaps with real loopback Uvicorn tests without requiring production-code changes. The daily pricing-integrity lifecycle is now explicitly schedule-first, archived, regression-gated, and designed to publish one auditable receipt per successful refresh; IR-014 additionally aligns token-estimation language with the actual pre-flight heuristic and provider-usage reconciliation behavior.

The hardening branch removes the known silent fabrication/fallback paths and changes the governing rule to: **unknown or unreconciled data stays unknown/conservative; it is never converted into a plausible-looking number merely to keep the UI green.**