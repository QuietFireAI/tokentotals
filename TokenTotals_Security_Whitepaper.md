# TokenTotals Technical & Security Whitepaper
### Localhost LLM Cost Proxy, Conservative Pre-Flight Reservations, and Local Pacing Controls

**Author:** QuietFireAI (Jeff Phillips)  
**License:** GNU General Public License v3.0 (GPLv3)  
**Review revision:** 2026-09-14 forensic hardening branch

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

The matrix generator reads the same `pricing_engine` view as the runtime. When regenerated after an OpenAI promotion, its OpenAI rows therefore come from the same promoted pricing snapshot rather than a separate hand-maintained table.

Unknown models fail closed. TokenTotals does not substitute a generic “close enough” dollar rate.

### 3.1 Accuracy boundary

Provider charges can include billing dimensions beyond uncached text input/output tokens, including model snapshots, token and cache telemetry, context bands, requested versus actual service tier, regional processing, modality, hosted tools, storage/runtime meters, fine-tuning, promotions/effective dates, account-specific pricing, retries/partial streams, missing telemetry, and provider-side pricing changes.

TokenTotals therefore reports the most accurate independent estimate supported by the telemetry and pricing rules available for the transaction. It does not claim invoice parity. See `docs/ACCURACY_AND_ESTIMATION_STANDARD.md` for the normative disclosure standard.

The OpenAI source synchronization described above is a pricing-source integrity mechanism; it is **not** by itself a complete OpenAI billing-event adapter. Each additional billing dimension must be explicitly implemented and tested before TokenTotals represents that dimension as supported.

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

The request is eligible for upstream routing only if the in-process atomic check-and-reserve operation can commit `S + R <= L`.

If the caller supplies no output-token maximum, TokenTotals applies `default_max_output_tokens`, lowering it further when necessary to fit the remaining budget. This converts an otherwise unbounded output-cost assumption into an explicit bound.

### 4.1 Input token estimation

The current pre-flight estimator is a conservative local UTF-8-length heuristic. It is **not represented as a provider/model BPE tokenizer**. Provider-reported usage is preferred after the response.

### 4.2 Reconciliation

For non-stream responses containing usable input/output token counts, TokenTotals calculates the supported pricing estimate and replaces the pre-flight reservation with that estimate.

For streams where final usage is unavailable, TokenTotals keeps the conservative reservation and increments an `unreconciled_streams` counter. It does not replace unknown cost with an invented constant.

### 4.3 Process boundary

The reservation lock is process-local. The current hardening does not provide an operating-system/inter-process file lock. Running multiple TokenTotals processes against the same state file is outside the proven budget invariant.

## 5. State integrity

State/config JSON writes use a temporary file followed by `os.replace()` while protected by a process-local re-entrant lock. This reduces partial-write corruption and closes the baseline check-then-send race for concurrent requests handled by one process.

Tracked state includes estimated/reserved daily spend, active-thread spend, request count, advisory savings estimate, lock state, and unreconciled stream count.

## 6. Lock and acknowledgment behavior

When the local state is locked, new chat-completion requests receive HTTP 403 before TokenTotals performs an upstream LiteLLM call.

The HTTP unlock endpoint requires the literal acknowledgment text:

```text
I UNDERSTAND
```

The dashboard `+$5` boost endpoint requires:

```text
BOOST $5
```

The Windows Tk lock dialog separately validates `I UNDERSTAND` before native unlock. Native tray/GUI boost controls are explicit local user actions.

TokenTotals removed the baseline permissive CORS middleware so an arbitrary browser origin is not deliberately granted API access.

## 7. Telemetry integrity rule

The dashboard must not show values as live telemetry unless runtime state actually supplies them. The forensic hardening removed baseline fixed values for token velocity, cumulative tokens, and cache-hit percentage.

The governing rule is:

> Unknown telemetry remains unknown. Conservative accounting remains conservative. The UI does not invent plausible values to fill empty space.

## 8. Streaming and protocol scope

The current chat proxy supports HTTP `/v1/chat/completions` and SSE-style streamed responses through that endpoint. This revision does **not** claim a TokenTotals WebSocket proxy endpoint.

## 9. Government / regulated environments

Loopback binding, local state, source availability, and absence of a QuietFireAI telemetry service can be useful architectural properties in some controlled environments. They do not by themselves establish FedRAMP authorization, FISMA compliance, ATO suitability, classification handling approval, or permission for deployment. Those determinations belong to the relevant organization and security/compliance authority.

## 10. Verification

The forensic hardening regression suite covers pricing math, fail-closed unknown models, conservative guard rates, atomic reservation/reconciliation, acknowledgment enforcement, no-upstream rejection paths, bounded output reservation, removal of fabricated dashboard constants, and OpenAI pricing-source synchronization failure/quarantine paths.

GitHub Actions on Ubuntu/Python 3.12 passed **19 tests with 0 failures** after the IR-003 implementation and test-isolation correction. Subsequent documentation/matrix consistency commits are required to keep the same suite green before an item is treated as closed.

This is regression evidence. It is not a substitute for live-provider integration tests, concurrency/load tests, packaging tests, dependency review, or security assessment.

## 11. Forensic record

See `INTEGRITY_REPORT.md` for the separate baseline integrity findings, including confirmed machine-specific paths, silent pricing fallbacks, disconnected price synchronization, input-only pre-flight accounting, API bypasses, concurrency hazards, static dashboard telemetry, and documentation claims that exceeded implementation.
