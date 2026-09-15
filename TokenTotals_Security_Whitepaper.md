# TokenTotals Technical & Security Whitepaper
### Localhost LLM Cost Proxy, Conservative Pre-Flight Reservations, and Local Pacing Controls

**Author:** QuietFireAI (Jeff Phillips)  
**License:** GNU General Public License v3.0 (GPLv3)  
**Review revision:** 2026-09-15 forensic hardening branch

---

## 1. Scope

TokenTotals is a local Layer-7 HTTP proxy and cost-estimation/pacing tool for supported LLM chat-completion traffic. It listens on IPv4 loopback (`127.0.0.1`), estimates request cost from a verified pricing view, reserves estimated token spend before sending an upstream request, and reconciles that reservation to provider-reported token usage when available.

This document describes the implementation boundary. It is **not** a statement of FedRAMP/FISMA authorization, a provider invoice guarantee, a network-firewall guarantee, or a legal opinion about patentability/prior-art effect.

## 2. Trust and network boundary

### 2.1 Local listener

The supplied server paths bind to `127.0.0.1`. TokenTotals does not intentionally expose its FastAPI listener on `0.0.0.0`.

### 2.2 Upstream egress still exists

“Local proxy” does **not** mean the LLM transaction is zero-egress. Requests accepted by the proxy are forwarded through LiteLLM to the selected external provider. Prompts, supported attachments/inputs, and API credentials therefore remain subject to the selected provider and LiteLLM execution path.

TokenTotals does not intentionally transmit separate analytics or telemetry to a QuietFireAI service.

### 2.3 API keys

TokenTotals obtains the request authorization value and passes it to LiteLLM for the upstream call. The TokenTotals state/config implementation does not intentionally persist API keys. Users must still assess the complete runtime, provider, operating system, and dependency chain for their own security requirements.

## 3. Pricing authority

`pricing_engine.py` supplies the runtime pricing view. Its base is the checked-in, dated `pricing_catalog.json`.

OpenAI is the first provider with a dynamic official-source overlay in this revision. `openai_pricing_sync.py` checks the supported OpenAI model documentation on `developers.openai.com`, builds a candidate snapshot, validates it, and keeps candidate/status/history separate from the promoted runtime snapshot. Only a snapshot marked `verified` at `~/.tokentotals/pricing/openai_verified.json` can overlay the checked-in OpenAI entries consumed by `pricing_engine.py`.

A failed or incomplete OpenAI check preserves the previous verified snapshot. Suspicious rate jumps are quarantined. If the official source content changes while the supported parser detects no corresponding pricing/rule change, the candidate is held for review rather than silently treated as harmless. A failed check remains due for retry.

Anthropic and Google remain on the dated checked-in verified catalog until equivalent official-source adapters are separately implemented and tested. No third-party community registry is permitted to overwrite the runtime pricing authority.

A separate non-destructive `matrix_source_check.py` validates the Anthropic and Google base/standard matrix rates against their official pricing pages on a daily schedule and when relevant pricing/matrix files change. It does not promote or rewrite prices. A missing/mismatched model rate, parsing ambiguity, or expired effective-dated catalog record fails the check for review. The Gemini 3.6/3.7/3.8 Flash promotional entries represented by this revision explicitly expire on 2026-12-31 so an old promotional value cannot remain current merely because it still appears historically on the provider page.

The matrix generator reads the same `pricing_engine` view as the runtime. When regenerated after an OpenAI promotion, its OpenAI rows therefore come from the same promoted pricing snapshot rather than a separate hand-maintained table. CI additionally checks that the committed portable base matrix remains identical to the base verified pricing view generated from the repository.

Unknown models fail closed. TokenTotals does not substitute a generic “close enough” dollar rate.

### 3.1 Accuracy boundary

Provider charges can include billing dimensions beyond uncached text input/output tokens, including model snapshots, token and cache telemetry, context bands, requested versus actual service tier, regional processing, modality, hosted tools, storage/runtime meters, fine-tuning, promotions/effective dates, account-specific pricing, retries/partial streams, missing telemetry, and provider-side pricing changes.

TokenTotals therefore reports the most accurate independent estimate supported by the telemetry and pricing rules available for the transaction. It does not claim invoice parity. See `docs/ACCURACY_AND_ESTIMATION_STANDARD.md` for the normative disclosure standard.

The OpenAI source synchronization described above is a pricing-source integrity mechanism; it is **not** by itself a complete OpenAI billing-event adapter. The Anthropic/Google matrix source checker is likewise a drift detector, not a dynamic runtime pricing adapter. Each additional billing dimension must be explicitly implemented and tested before TokenTotals represents that dimension as supported.

## 4. Pre-flight budget reservation

Let:

- `S` = currently reserved/reconciled daily estimated spend;
- `L` = configured daily budget limit;
- `Tin` = conservative locally estimated input tokens;
- `Tout` = bounded maximum output tokens for the request;
- `Pin_guard` / `Pout_guard` = high-side catalog token rates.

The pre-flight reservation is:

```text
R = (Tin / 1,000,000 * Pin_guard)
  + (Tout / 1,000,000 * Pout_guard)
```

The request is eligible for upstream routing only if the in-process atomic check-and-reserve operation can commit `S + R <= L`. The reservation is committed before `litellm.acompletion()` begins.

If the caller supplies both `max_tokens` and `max_completion_tokens`, TokenTotals reserves against the larger valid output ceiling. If the caller supplies no output-token maximum, TokenTotals applies `default_max_output_tokens`, lowering it further when necessary to fit the remaining budget. This converts an otherwise unbounded output-cost assumption into an explicit bound.

The 2026-09-15 IR-007 revalidation directly instrumented the mocked upstream boundary and verified that `current_spend_usd` already contained the full input-plus-output conservative reservation when upstream execution began. This is lifecycle evidence that reservation is pre-egress rather than merely calculated before the call and committed later.

### 4.1 Input token estimation

The current pre-flight estimator is a conservative local UTF-8-length heuristic. It is **not represented as a provider/model BPE tokenizer**. Provider-reported usage is preferred after the response.

### 4.2 Reconciliation

For non-stream responses containing usable input/output token counts, TokenTotals calculates the supported pricing estimate and replaces the pre-flight reservation with that estimate.

For streams where final usage is unavailable, TokenTotals keeps the conservative reservation and increments an `unreconciled_streams` counter. It does not replace unknown cost with an invented constant or release budget headroom without evidence. The IR-007 revalidation includes a streamed-response regression test that proves the reservation remains after a stream completes without final usage telemetry.

### 4.3 Process boundary

The reservation lock is process-local. The current hardening does not provide an operating-system/inter-process file lock. Running multiple TokenTotals processes against the same state file is outside the proven budget invariant.

## 5. State integrity and request isolation

State/config JSON writes use a temporary file followed by `os.replace()` while protected by a process-local re-entrant lock. This reduces partial-write corruption and closes the baseline check-then-send race for concurrent requests handled by one process.

The IR-008 revalidation used two simultaneous worker threads, each attempting a `$0.06` reservation against a `$0.10` budget. Exactly one reservation was accepted and one rejected, proving the in-process budget decision and reservation commit remain serialized under contention.

The baseline also used shared request-scoped globals for thread identity, routine classification, and potential-savings metadata. Those shared values were unsafe under overlapping requests because one request could overwrite another request's context before callback accounting ran. The hardened request path keeps those values local and passes them explicitly into reservation and reconciliation operations.

The IR-009 overlap revalidation held two HTTP requests simultaneously at the mocked upstream boundary and verified that distinct thread IDs, routine classification, and potential-savings metadata remained attached to the correct request through both reservation and reconciliation. The old request-scoped globals and callback symbol are separately guarded against regression.

Tracked state includes estimated/reserved daily spend, active-thread spend, request count, advisory savings estimate, lock state, and unreconciled stream count. `active_thread_id` / `thread_spend_usd` are one current display slot, not a historical per-thread ledger.

## 6. Lock, boost, and acknowledgment behavior

When the local state is locked, new chat-completion requests receive HTTP 403 before TokenTotals performs an upstream LiteLLM call.

The baseline HTTP unlock path was unconditional: it did not read or require request-supplied acknowledgment before clearing the lock, even though its response described the action as user-acknowledged. The baseline HTTP boost path was also unconditional: it raised the configured daily budget by `$5.00` and cleared the lock without confirmation. The baseline application additionally installed permissive CORS middleware.

The hardened HTTP controls use two layers before mutation:

1. **State-control transport/payload gate.** `/api/unlock` and `/api/boost` require `Content-Type: application/json`, syntactically valid JSON, and a JSON object. Missing media type, browser-style `text/plain`, malformed JSON, explicit JSON `null`, and non-object JSON are rejected before acknowledgment evaluation.
2. **Intent phrase gate.** Unlock requires `I UNDERSTAND`; boost requires `BOOST $5`. The validator trims surrounding whitespace and compares letter case insensitively; different wording is rejected.

These phrases are explicit-intent controls, not passwords or authentication secrets.

A valid unlock changes only `is_locked` to `False`. It does not reset tracked spend, request counts, savings, thread accounting, unreconciled-stream state, or the configured daily budget.

A valid HTTP boost changes exactly the configured daily budget by `+$5.00` and releases the lock. It preserves the already-recorded spend and accounting fields.

The Windows Tk lock dialog separately validates `I UNDERSTAND` before native unlock. Native tray/GUI boost controls are explicit local user actions and invoke the local state manager directly rather than the HTTP endpoint.

TokenTotals does not install the baseline permissive CORS middleware. The IR-011 regression sends a foreign-origin preflight to `/api/boost` and requires that no `Access-Control-Allow-Origin` or `Access-Control-Allow-Methods` grant be returned.

### 6.1 Browser-simple-POST finding

IR-011 specifically tested whether removing permissive CORS plus adding the phrase was enough. It was not.

The first adversarial test sent the correct JSON-formatted phrase in a cross-origin request declared as `Content-Type: text/plain`. The endpoint returned **HTTP 200** and performed the boost because `request.json()` parsed the JSON-formatted body despite the text/plain media type. Certain browser cross-origin text/plain requests can be sent without a CORS preflight, so the first hardening pass left a real state-changing route.

The final repair added the JSON-only state-control transport gate described above. The same browser-style request now receives HTTP 415 before JSON parsing or state mutation. An `application/json` cross-origin browser request requires preflight, and TokenTotals does not grant the tested foreign-origin preflight.

This control reduces browser-origin/accidental triggering of localhost state actions. It does **not** authenticate against a malicious program already executing locally with the user's privileges; such a process can deliberately send valid JSON and the published acknowledgment phrase to the loopback endpoint.

## 7. Telemetry integrity rule

The dashboard must not show values as live telemetry unless runtime state actually supplies them. The forensic hardening removed baseline fixed values for token velocity, cumulative tokens, and cache-hit percentage.

The governing rule is:

> Unknown telemetry remains unknown. Conservative accounting remains conservative. The UI does not invent plausible values to fill empty space.

## 8. Streaming and protocol scope

The current chat proxy supports HTTP `/v1/chat/completions` and SSE-style streamed responses through that endpoint. This revision does **not** claim a TokenTotals WebSocket proxy endpoint.

## 9. Government / regulated environments

Loopback binding, local state, source availability, and absence of a QuietFireAI telemetry service can be useful architectural properties in some controlled environments. They do not by themselves establish FedRAMP authorization, FISMA compliance, ATO suitability, classification handling approval, or permission for deployment. Those determinations belong to the relevant organization and security/compliance authority.

## 10. Runtime and dependency reproducibility

The validated source/runtime contract for this revision is **CPython 3.12.x**.

`constraints-py312.txt` pins the validated dependency versions used by runtime, tests, and the Windows build path. Platform-specific dependencies use environment markers where the measured Linux and Windows graphs differ. `build.ps1` refuses another Python major/minor, installs through the constraints, runs `pip check`, and uses the constrained PyInstaller toolchain.

The CI workflow creates fresh virtual environments for Linux runtime, Windows runtime, Windows build tools, and the regression suite. This avoids treating unrelated packages preinstalled in a hosted runner as TokenTotals dependencies.

`runtime_compat.py` is the executable compatibility contract. It reports a clear failure when the running Python major/minor differs from the validated 3.12 contract. The GitHub Actions workflow executes this check on pushes and pull requests and includes a daily schedule on the default branch, providing an ongoing Python-version/dependency-drift watch.

The constraints provide **version reproducibility for the validated CPython 3.12 dependency graph**. They are not a cryptographic package-artifact or supply-chain guarantee; package hashes are not pinned in this revision.

## 11. Verification

The forensic hardening regression suite covers pricing math, fail-closed unknown models, conservative guard rates, atomic reservation/reconciliation, simultaneous in-process reservation contention, request-context isolation under overlapping HTTP calls, unlock acknowledgment/normalization/state integrity, state-control media-type and JSON-object validation, browser-style text/plain rejection, ungranted foreign-origin CORS preflight, boost acknowledgment/state integrity, no-upstream rejection paths, bounded output reservation including conflicting output ceilings, direct proof that input-plus-output spend is committed before upstream execution, retention of a conservative reservation for streams without final usage, reservation against the model actually selected for automatic routing, removal of fabricated dashboard constants, OpenAI pricing-source synchronization failure/quarantine paths, committed-matrix drift detection, Anthropic/Google base/standard source parsing and effective-date expiry enforcement, clean-install use of the declared LiteLLM runtime dependency, public-claim guards that preserve the actual provider synchronization scope, dependency-constraint coverage, clean constrained Linux/Windows environments, Python-version contract consistency, and constrained Windows packaging dependencies.

The IR-011 evidence chain intentionally includes failures. The first adversarial run produced **1 failed / 43 passed** because a browser-style text/plain POST unexpectedly returned HTTP 200 and performed the boost. After the production JSON-only gate was added, a second run produced **2 failed / 43 passed** because the test harness's `json=None` did not actually send an application/json null payload and therefore correctly received HTTP 415. The tests were changed to send an explicit body `null` with `Content-Type: application/json`. The corrected repair revision then passed **45 tests / 0 failures** on Ubuntu/Python 3.12, and `pip check` reported no broken requirements.

Separate clean-environment jobs continue to exercise the constrained Linux runtime import, constrained Windows runtime import, and constrained Windows PyInstaller toolchain. The daily Python compatibility check remains part of the same workflow and becomes scheduled automatically when the workflow resides on the repository default branch.

The separate non-destructive matrix-source workflow also passed against the live Anthropic and Google official pricing pages on the 2026-09-15 revalidation pass.

This is regression/source-validation evidence. It is not a substitute for live-provider integration tests, broader concurrency/load tests, final executable packaging tests, cryptographic dependency verification, or security assessment.

## 12. Forensic record

See `INTEGRITY_REPORT.md` for the separate baseline integrity findings and hardening findings, including confirmed machine-specific paths, silent pricing fallbacks, disconnected price synchronization, stale matrix data, input-only pre-flight accounting, API bypasses, concurrency hazards, static dashboard telemetry, routed-model reservation ordering, dependency reproducibility, browser-origin state-control hardening, and documentation claims that exceeded implementation.

See `docs/IR-007_OUTPUT_RESERVATION_PROOF.md` for output-reservation lifecycle evidence, `docs/IR-008_CONCURRENT_RESERVATION_PROOF.md` for in-process contention evidence, `docs/IR-009_REQUEST_CONTEXT_ISOLATION_PROOF.md` for overlapping request-context evidence, `docs/IR-010_UNLOCK_ACKNOWLEDGEMENT_PROOF.md` for unlock acknowledgment evidence, `docs/IR-011_BOOST_AND_BROWSER_ORIGIN_PROOF.md` for boost/browser-origin evidence, and `docs/IR-020_DEPENDENCY_REPRODUCIBILITY_PROOF.md` for the measured dependency and Python compatibility evidence.