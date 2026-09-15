# TokenTotals by QuietFireAI

> A local LLM cost-estimation proxy with conservative pre-flight budget reservations, local spend state, and a Windows tray/dashboard UI.

TokenTotals listens on `127.0.0.1`, forwards supported chat-completion requests through LiteLLM, estimates transaction cost from a verified pricing view, and reserves conservative spend **before** an upstream request is sent. After a response reports usage, the reservation is reconciled to the best supported estimate.

> [!IMPORTANT]
> TokenTotals is a developer pacing/observability tool, **not a provider billing portal or network firewall**. Dollar values are independent estimates based on the request/response telemetry available to the user and the provider pricing rules represented in TokenTotals. Provider billing can differ because of model snapshots, token and cache telemetry, context bands, requested versus actual service tier, regional processing, modality, hosted tools, storage/runtime meters, fine-tuning, promotions/effective dates, account-specific pricing, retries/partial streams, missing telemetry, and provider-side pricing changes. Always monitor the provider's own account and billing controls as the authority for actual charges.

See [`docs/ACCURACY_AND_ESTIMATION_STANDARD.md`](docs/ACCURACY_AND_ESTIMATION_STANDARD.md) for the governing accuracy and disclosure standard.

## What is implemented

- FastAPI proxy on `127.0.0.1`.
- `/v1/chat/completions` routing through LiteLLM.
- Checked-in, dated base pricing catalog with official provider receipt URLs.
- Official-source OpenAI pricing checker for the supported OpenAI models in this revision.
- Validated OpenAI candidate snapshots that are promoted separately from the last verified runtime snapshot.
- Non-destructive daily source-drift validation for the dated Anthropic and Google matrix base rates and represented conservative guard rates.
- Unknown model pricing **fails closed** instead of using a generic dollar fallback.
- Conservative pre-flight reservation for estimated input **and bounded output** tokens.
- Atomic in-process budget check/reservation and post-response reconciliation.
- Request-scoped thread/routine/savings accounting stays local to each request rather than using shared callback globals.
- Daily local spend state and active-thread spend state under `~/.tokentotals`.
- Lock state with desktop tray/modal monitoring on the Windows GUI.
- Request-supplied `I UNDERSTAND` acknowledgment requirement for the HTTP unlock endpoint; surrounding whitespace and letter case are normalized, but different wording is rejected.
- Request-supplied `BOOST $5` acknowledgment for HTTP/dashboard budget boosts.
- HTTP state-changing controls (`/api/unlock` and `/api/boost`) require `Content-Type: application/json`, valid object JSON, and the applicable acknowledgment phrase before state mutation.
- No permissive CORS middleware; the tested foreign-origin preflight is not granted, and browser-style `text/plain` state-control POSTs are rejected before mutation.
- Dashboard that displays runtime state only; it does not ship fake token/cache telemetry.
- SSE-style streaming pass-through. If final usage is unavailable, TokenTotals keeps the conservative reservation and marks the stream unreconciled rather than inventing a final cost.
- A validated CPython 3.12 dependency contract with a version-constrained runtime/test/build dependency graph.
- Clean Linux and Windows runtime smoke checks plus a constrained Windows PyInstaller toolchain check.
- A daily GitHub Actions compatibility watch for Python-version and dependency-resolution drift once this workflow is on the repository default branch.

## What is **not** claimed

- Pre-flight token counts are **not represented as provider/model BPE counts**. The current local estimator is a conservative UTF-8 length heuristic.
- TokenTotals does not claim invoice parity or guaranteed identity with provider billing.
- The current OpenAI source synchronization is not the same thing as a complete OpenAI billing adapter. Service-tier, cache, context-band, regional, tool, modality, storage, and other billing-event accounting are implemented only when specifically documented and tested.
- Anthropic and Google do not yet have the dynamic official-source synchronization path implemented for OpenAI; they remain dated verified catalog entries in this revision. Their live source-drift check validates represented base/standard and conservative guard rates but does not automatically promote new rates into runtime pricing.
- It does not intercept applications that bypass the configured local proxy.
- It does not provide a TokenTotals WebSocket proxy endpoint.
- It does not inject a telemetry badge into every IDE/chat turn.
- It is not a FedRAMP/FISMA authorization and does not make an environment compliant by itself.
- The packaged GUI/build path in this repository is currently Windows-oriented. The Python proxy may be portable, but macOS/Linux GUI packaging is not release-tested here.
- The HTTP acknowledgment phrases are **not authentication secrets**. A malicious local process running with the user's privileges can deliberately call the loopback control endpoint with valid JSON and the published phrase.
- The dependency constraints provide version reproducibility for the validated CPython 3.12 environments; they are not a cryptographic package-artifact/hash guarantee.

See [`INTEGRITY_REPORT.md`](INTEGRITY_REPORT.md) for the forensic findings that led to these corrections.

## Pricing authority

`pricing_engine.py` is the runtime pricing view used by both the proxy and the matrix generator.

The base is [`pricing_catalog.json`](pricing_catalog.json). For OpenAI, a successfully validated and promoted snapshot at `~/.tokentotals/pricing/openai_verified.json` overlays the checked-in OpenAI entries. Candidate, status, and history files stay separate from the promoted runtime snapshot so a failed or suspicious source update cannot silently replace the last verified rates.

`openai_pricing_sync.py` checks the official OpenAI developer documentation for the OpenAI models currently supported by this pricing adapter. A complete candidate must parse and validate before promotion. Incomplete fetches preserve the previous verified snapshot. Large suspicious rate jumps are quarantined, and source-content changes that do not correspond to a recognized pricing/rule change are held for review instead of being treated as harmless.

The checker is scheduled daily. A failed check remains due and is retried; a successful check with no supported change records the fresh check without inventing a new rate version.

Official pricing receipts used by this revision:

- OpenAI: https://developers.openai.com/api/docs/pricing
- Anthropic: https://platform.claude.com/docs/en/about-claude/pricing
- Google Cloud: https://cloud.google.com/gemini-enterprise-agent-platform/generative-ai/pricing

Anthropic and Google continue to use the checked-in dated catalog until equivalent official-source adapters are separately implemented and tested. `matrix_source_check.py` independently checks their represented base/standard rates and conservative guard rates against those official pages every day and on relevant pricing changes. It is deliberately non-destructive: drift, a parsing ambiguity, a missing model row, an unsupported guard value, or an expired effective-dated rate fails the check rather than rewriting runtime pricing.

The Google Gemini 3.6/3.7/3.8 Flash promotional rates represented in this revision are effective only through **2026-12-31**. Their catalog records carry that expiration so the validator cannot continue treating the historical promotional number as current after its effective window ends.

The human-readable matrix and the marked README pricing snapshot are generated with:

```bash
python generate_model_matrix.py
```

The generator reads the same effective pricing view as the runtime. Regenerating after an OpenAI snapshot promotion therefore uses the promoted OpenAI rates rather than an independent hand-maintained table. CI checks both the committed portable matrix and the README pricing block against the generator/base verified pricing view so stale model/rate tables cannot silently survive below the fold.

Unknown models are rejected until a verified pricing entry is deliberately added. This is intentional: TokenTotals should say **unknown** rather than quietly inventing a plausible dollar rate.

<!-- TOKENTOTALS_VERIFIED_PRICING_START -->
## Current verified model pricing snapshot

**Verified catalog date:** 2026-09-15  
**Comparison workload:** 10,000 input tokens + 2,000 output tokens.

This table is generated from the same `pricing_engine` view used by the proxy and `MODEL_COMPARISON_MATRIX.md`; it is not a separately maintained marketing table. Dollar values are independent approximations from represented provider rules and observed/estimated telemetry, not provider invoices.

| Provider | Verified model | Base input / 1M | Base output / 1M | 10K in + 2K out base estimate | Conservative pre-flight reservation |
| :--- | :--- | ---: | ---: | ---: | ---: |
| Anthropic | `claude-fable-5.1` | $10 | $50 | $0.200000 | $0.300000 |
| Anthropic | `claude-haiku-4.5` | $1 | $5 | $0.020000 | $0.030000 |
| Anthropic | `claude-opus-5` | $5 | $25 | $0.100000 | $0.150000 |
| Anthropic | `claude-sonnet-5` | $2 | $10 | $0.040000 | $0.060000 |
| Google | `gemini-3.1-flash-lite` | $0.25 | $1.5 | $0.005500 | $0.010890 |
| Google | `gemini-3.1-pro-preview` | $2 | $12 | $0.044000 | $0.136800 |
| Google | `gemini-3.5-flash` | $1.5 | $9 | $0.033000 | $0.065340 |
| Google | `gemini-3.5-flash-lite` | $0.3 | $2.5 | $0.008000 | $0.015840 |
| Google | `gemini-3.6-flash` | $0.75 | $3.75 | $0.015000 | $0.029700 |
| Google | `gemini-3.7-flash` | $0.75 | $3.75 | $0.015000 | $0.029700 |
| Google | `gemini-3.8-flash` | $0.75 | $3.75 | $0.015000 | $0.029700 |
| OpenAI | `gpt-5.6-luna` | $0.2 | $1.2 | $0.004400 | $0.007600 |
| OpenAI | `gpt-5.6-sol` | $4 | $20 | $0.080000 | $0.140000 |
| OpenAI | `gpt-5.6-terra` | $2 | $12 | $0.044000 | $0.076000 |
| OpenAI | `gpt-6-astra` | $10 | $50 | $0.200000 | $0.350000 |

Base-turn approximation:

```text
base_estimate = (input_tokens / 1,000,000 × base_input_rate)
              + (output_tokens / 1,000,000 × base_output_rate)
```

Pre-flight reservation uses the same formula with the catalog's conservative guard rates. The guard is deliberately a high-side pacing amount; it is **not** a prediction that the provider will invoice that amount. After usable provider token telemetry arrives, TokenTotals reconciles the reservation to the most specific supported estimate. Unknown pricing fails closed instead of receiving an invented rate.

The compact table shows represented base text-token rates. Context bands, cache read/write rates, service modes, region, tools, modalities, promotions/effective dates, account-specific pricing, and other billable dimensions can change the applicable provider charge. See [MODEL_COMPARISON_MATRIX.md](MODEL_COMPARISON_MATRIX.md) for the row-by-row guard rates and qualifiers.
<!-- TOKENTOTALS_VERIFIED_PRICING_END -->

## Budget-gate behavior

For a supported model TokenTotals:

1. estimates incoming prompt tokens locally;
2. resolves a verified pricing record;
3. chooses/validates a bounded output-token allowance;
4. computes a conservative high-side reservation for estimated input plus the bounded output ceiling;
5. atomically checks and commits that reservation against the daily limit **before** the upstream call begins;
6. sends the request only if the reservation succeeds;
7. reconciles the reservation to provider-reported token usage when available.

If a caller supplies both `max_tokens` and `max_completion_tokens`, TokenTotals reserves against the larger valid ceiling. If a stream ends without usable final usage telemetry, the conservative reservation remains on the books and the stream is marked unreconciled rather than silently releasing budget headroom.

This closes the baseline implementation's input-only pre-flight gap and its check-then-send concurrency race within a single TokenTotals process. Simultaneous-request regression tests also verify that the process-local reservation gate admits only one of two reservations that cannot both fit, and that overlapping requests keep their own thread/routine/savings context through reconciliation.

### Important process boundary

The budget lock in this revision is **process-local**. Do not run multiple TokenTotals proxy processes against the same state file and assume the hard-budget invariant is preserved. Cross-process locking is a separate requirement.

## HTTP budget controls

The two state-changing HTTP controls are deliberately narrower than ordinary proxy requests:

- `/api/unlock` requires `application/json`, an object payload, and the `I UNDERSTAND` acknowledgment phrase.
- `/api/boost` requires `application/json`, an object payload, and the `BOOST $5` acknowledgment phrase.

The API trims surrounding whitespace and compares acknowledgment letter case insensitively. Missing bodies, malformed JSON, explicit JSON `null`, non-object payloads, and different phrases are rejected before state mutation.

The IR-011 revalidation specifically found that the first hardening pass was incomplete: despite removing permissive CORS and requiring the phrase, a cross-origin `text/plain` POST containing JSON text still returned HTTP 200 because `request.json()` parsed it. The final repair added the shared JSON-only state-action gate. Regression tests now require that browser-style simple POST to receive HTTP 415 and that the tested foreign-origin CORS preflight receive no grant.

A successful boost increases the configured daily limit by exactly `$5.00` and releases the lock; it does not reset previously tracked spend/accounting. A successful unlock releases the lock without changing the configured budget or accounting.

## Python and dependency contract

The currently validated source/runtime dependency contract is **CPython 3.12.x**.

`constraints-py312.txt` pins the validated runtime/test/build dependency versions. Platform-specific packages use environment markers where the validated Linux and Windows graphs differ. Deliberate dependency upgrades should update the constraints and pass the Linux runtime, Windows runtime, Windows build-tool, and regression jobs together.

`runtime_compat.py` is the machine-readable compatibility check used by CI. The GitHub Actions workflow exercises the Python-version contract and constrained dependency graph on pushes and pull requests, and is scheduled daily on the default branch to catch future interpreter/dependency drift.

## Quickstart from source

Confirm Python 3.12 first:

```bash
python --version
python runtime_compat.py
```

Then install through the validated constraints:

```bash
python -m venv .venv
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
python -m pip install -c constraints-py312.txt -r requirements.txt
python -m pip check
python proxy_server.py
```

The proxy/dashboard will listen on the configured loopback port (default `8080`):

```text
http://127.0.0.1:8080/v1
http://127.0.0.1:8080/dashboard
```

Configure a compatible client to use the local `/v1` base URL and provide the real provider API key through that client.

## Configuration

`~/.tokentotals/config.json` defaults to:

```json
{
  "daily_budget_limit_usd": 10.0,
  "port": 8080,
  "auto_economy_mode": false,
  "warning_threshold_pct": 75,
  "default_max_output_tokens": 4096
}
```

`default_max_output_tokens` is used when a request does not provide a maximum output bound. TokenTotals may lower that bound further when the remaining budget cannot safely reserve the configured amount.

## Windows tray application

`app_gui.py` starts the proxy, tray monitor, and dashboard integration. The modal lock dialog requires the `I UNDERSTAND` acknowledgment phrase before native unlock. The native `+$5` button is an explicit local user action.

Build on Windows with CPython 3.12:

```powershell
.\build.ps1
```

The build script refuses another Python major/minor, installs through `constraints-py312.txt`, runs `pip check`, and uses the constrained PyInstaller toolchain. It no longer depends on a developer-specific Antigravity/Gemini plugin directory and bundles `pricing_catalog.json` with the application.

## Tests

Install development dependencies through the same constraints and run:

```bash
python -m pip install -c constraints-py312.txt -r requirements-dev.txt
python -m pip check
python -m pytest -q
```

The forensic hardening suite now covers:

- verified input/output cost math;
- fail-closed unknown model pricing;
- high-side pre-flight guard rates;
- atomic reservation/reconciliation;
- true simultaneous in-process reservation contention;
- overlapping request-context isolation for thread identity, routine classification, and potential-savings metadata;
- regression guards preventing the old shared request-scoped globals/callback from returning;
- HTTP unlock rejection for missing, malformed, null, non-object, text/plain, or wrong acknowledgment input;
- intentional case/whitespace normalization of the `I UNDERSTAND` phrase;
- proof that successful unlock changes only the lock flag and preserves accounting plus configured budget;
- HTTP boost rejection for browser-style text/plain requests, explicit JSON null, empty/wrong confirmation, and ungranted foreign-origin preflight;
- proof that successful boost changes only the `$5` budget increase and lock release while preserving accounting;
- prevention of upstream calls after price/budget rejection;
- bounded output reservation, including conflicting output-bound fields;
- proof that the full input-plus-output reservation is committed before upstream execution begins;
- retention of the conservative reservation when a stream ends without final usage telemetry;
- reservation against the exact model actually selected for auto-economy routing;
- removal of hard-coded dashboard telemetry and source-backed dashboard dynamic fields;
- public-claim guard preventing the unsupported turn-by-turn telemetry badge claim from returning;
- non-stream response pass-through proof that provider assistant content is not silently decorated by TokenTotals;
- OpenAI official-source pricing parsing;
- preservation of the last verified OpenAI snapshot after incomplete/failed checks;
- runtime consumption of the same promoted OpenAI snapshot;
- quarantine of suspicious price jumps;
- same-day retry after failed source checks;
- review-required handling when source content changes without a recognized pricing/rule change;
- committed matrix and README pricing-block drift detection against the base verified pricing view;
- Anthropic/Google live matrix-source parsing anchored to their base/standard pricing sections;
- live base-rate and guard-rate drift rejection rather than silent catalog acceptance;
- effective-date expiry enforcement for promotional matrix rates;
- clean-install use of the real declared LiteLLM dependency rather than a test-injected stand-in;
- public-claim guards that prevent a blanket all-provider “audited live” claim and preserve the actual provider synchronization scope;
- runtime requirement coverage by the Python 3.12 constraints;
- clean constrained environments on Linux and Windows;
- Python 3.12 agreement across the compatibility contract, CI, and Windows build path;
- constrained Windows PyInstaller packaging dependencies.

The latest focused regression revision passed **48 tests / 0 failures** on Ubuntu/Python 3.12 before this generated-pricing synchronization and guard-rate correction. Separate clean-environment jobs continue to exercise the constrained Linux runtime import, constrained Windows runtime import, and constrained Windows PyInstaller toolchain. The non-destructive matrix-source workflow previously passed against the live Anthropic and Google official pricing pages on the 2026-09-15 revalidation pass; the current change extends that daily check to the represented conservative guard rates as well. This is regression/source-validation evidence, not a substitute for live-provider integration, broader load, final executable packaging, or security testing.

See [`docs/IR-007_OUTPUT_RESERVATION_PROOF.md`](docs/IR-007_OUTPUT_RESERVATION_PROOF.md) for output-reservation evidence, [`docs/IR-008_CONCURRENT_RESERVATION_PROOF.md`](docs/IR-008_CONCURRENT_RESERVATION_PROOF.md) for in-process contention evidence, [`docs/IR-009_REQUEST_CONTEXT_ISOLATION_PROOF.md`](docs/IR-009_REQUEST_CONTEXT_ISOLATION_PROOF.md) for request-context isolation evidence, [`docs/IR-010_UNLOCK_ACKNOWLEDGEMENT_PROOF.md`](docs/IR-010_UNLOCK_ACKNOWLEDGEMENT_PROOF.md) for unlock acknowledgment evidence, [`docs/IR-011_BOOST_AND_BROWSER_ORIGIN_PROOF.md`](docs/IR-011_BOOST_AND_BROWSER_ORIGIN_PROOF.md) for budget-control/browser-origin evidence, [`docs/IR-012_DASHBOARD_TELEMETRY_INTEGRITY_PROOF.md`](docs/IR-012_DASHBOARD_TELEMETRY_INTEGRITY_PROOF.md) for dashboard telemetry-integrity evidence, [`docs/IR-013_TELEMETRY_BADGE_CLAIM_PROOF.md`](docs/IR-013_TELEMETRY_BADGE_CLAIM_PROOF.md) for the in-context badge claim boundary, and [`docs/IR-020_DEPENDENCY_REPRODUCIBILITY_PROOF.md`](docs/IR-020_DEPENDENCY_REPRODUCIBILITY_PROOF.md) for dependency-reproducibility and daily Python compatibility evidence.

## Security and privacy boundary

The HTTP listener binds to IPv4 loopback when started through the supplied server paths. TokenTotals itself does not send analytics to a QuietFireAI service. **Upstream model requests still leave the machine and go to the selected AI provider**; “local proxy” does not mean the AI request itself is zero-egress.

API keys are passed to LiteLLM for the upstream request and are not intentionally persisted by TokenTotals. Users should still review LiteLLM/provider behavior and their own operating environment before handling sensitive material.

The acknowledgment phrases are explicit-intent controls, not credentials. The browser-origin hardening reduces accidental/remote-web triggering of localhost controls; it does not claim to defend against a malicious process already executing locally with the user's permissions.

## License

GNU General Public License v3.0. See [`LICENSE`](LICENSE).

Built by QuietFireAI.