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
- Non-destructive daily source-drift validation for the dated Anthropic and Google matrix rates.
- Unknown model pricing **fails closed** instead of using a generic dollar fallback.
- Conservative pre-flight reservation for estimated input **and bounded output** tokens.
- Atomic in-process budget check/reservation and post-response reconciliation.
- Request-scoped thread/routine/savings accounting stays local to each request rather than using shared callback globals.
- Daily local spend state and active-thread spend state under `~/.tokentotals`.
- Lock state with desktop tray/modal monitoring on the Windows GUI.
- Request-supplied `I UNDERSTAND` acknowledgment requirement for the HTTP unlock endpoint; surrounding whitespace and letter case are normalized, but different wording is rejected.
- Explicit `BOOST $5` acknowledgement for dashboard budget boosts.
- Dashboard that displays runtime state only; it does not ship fake token/cache telemetry.
- SSE-style streaming pass-through. If final usage is unavailable, TokenTotals keeps the conservative reservation and marks the stream unreconciled rather than inventing a final cost.
- A validated CPython 3.12 dependency contract with a version-constrained runtime/test/build dependency graph.
- Clean Linux and Windows runtime smoke checks plus a constrained Windows PyInstaller toolchain check.
- A daily GitHub Actions compatibility watch for Python-version and dependency-resolution drift once this workflow is on the repository default branch.

## What is **not** claimed

- Pre-flight token counts are **not represented as provider/model BPE counts**. The current local estimator is a conservative UTF-8 length heuristic.
- TokenTotals does not claim invoice parity or guaranteed identity with provider billing.
- The current OpenAI source synchronization is not the same thing as a complete OpenAI billing adapter. Service-tier, cache, context-band, regional, tool, modality, storage, and other billing-event accounting are implemented only when specifically documented and tested.
- Anthropic and Google do not yet have the dynamic official-source synchronization path implemented for OpenAI; they remain dated verified catalog entries in this revision. Their live source-drift check validates those dated entries but does not automatically promote new rates into runtime pricing.
- It does not intercept applications that bypass the configured local proxy.
- It does not provide a TokenTotals WebSocket proxy endpoint.
- It does not inject a telemetry badge into every IDE/chat turn.
- It is not a FedRAMP/FISMA authorization and does not make an environment compliant by itself.
- The packaged GUI/build path in this repository is currently Windows-oriented. The Python proxy may be portable, but macOS/Linux GUI packaging is not release-tested here.
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

Anthropic and Google continue to use the checked-in dated catalog until equivalent official-source adapters are separately implemented and tested. `matrix_source_check.py` independently checks their represented base/standard matrix rates against those official pages every day and on relevant pricing changes. It is deliberately non-destructive: drift, a parsing ambiguity, a missing model row, or an expired effective-dated rate fails the check rather than rewriting runtime pricing.

The Google Gemini 3.6/3.7/3.8 Flash promotional rates represented in this revision are effective only through **2026-12-31**. Their catalog records carry that expiration so the validator cannot continue treating the historical promotional number as current after its effective window ends.

The human-readable matrix is generated with:

```bash
python generate_model_matrix.py
```

The generator reads the same effective pricing view as the runtime. Regenerating the matrix after an OpenAI snapshot promotion therefore uses the promoted OpenAI rates rather than an independent hand-maintained table. CI also checks that the committed portable matrix matches the checked-in base verified pricing view so catalog/generator changes cannot silently leave the public matrix stale.

Unknown models are rejected until a verified pricing entry is deliberately added. This is intentional: TokenTotals should say **unknown** rather than quietly inventing a plausible dollar rate.

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
- HTTP unlock rejection for missing, malformed, empty, or wrong acknowledgment input;
- intentional case/whitespace normalization of the `I UNDERSTAND` phrase;
- proof that successful unlock changes only the lock flag and preserves accounting plus configured budget;
- boost acknowledgements;
- prevention of upstream calls after price/budget rejection;
- bounded output reservation, including conflicting output-bound fields;
- proof that the full input-plus-output reservation is committed before upstream execution begins;
- retention of the conservative reservation when a stream ends without final usage telemetry;
- reservation against the exact model actually selected for auto-economy routing;
- removal of hard-coded dashboard telemetry;
- OpenAI official-source pricing parsing;
- preservation of the last verified OpenAI snapshot after incomplete/failed checks;
- runtime consumption of the same promoted OpenAI snapshot;
- quarantine of suspicious price jumps;
- same-day retry after failed source checks;
- review-required handling when source content changes without a recognized pricing/rule change;
- committed matrix drift detection against the base verified pricing view;
- Anthropic/Google live matrix-source parsing anchored to their base/standard pricing sections;
- live source-rate drift rejection rather than silent catalog acceptance;
- effective-date expiry enforcement for promotional matrix rates;
- clean-install use of the real declared LiteLLM dependency rather than a test-injected stand-in;
- public-claim guards that prevent a blanket all-provider “audited live” claim and preserve the actual provider synchronization scope;
- runtime requirement coverage by the Python 3.12 constraints;
- clean constrained environments on Linux and Windows;
- Python 3.12 agreement across the compatibility contract, CI, and Windows build path;
- constrained Windows PyInstaller packaging dependencies.

GitHub Actions on Ubuntu/Python 3.12 passed **41 tests / 0 failures** on the IR-010 unlock-integrity revalidation revision. The IR-008 contention test proves the in-process budget gate serializes two simultaneous reservations that cannot both fit. The IR-009 tests prove the old request-scoped globals/callback cannot silently return and that overlapping requests retain their own accounting identity through reservation and reconciliation. The IR-010 tests prove the HTTP unlock path rejects absent/malformed/wrong acknowledgment, intentionally normalizes case/outer whitespace for the required phrase, and changes only the lock state after valid acknowledgment. Separate clean-environment jobs continue to exercise the constrained Linux runtime import, constrained Windows runtime import, and constrained Windows PyInstaller toolchain. The non-destructive matrix-source workflow previously passed against the live Anthropic and Google official pricing pages on the 2026-09-15 revalidation pass. This is regression/source-validation evidence, not a substitute for live-provider integration, broader load, final executable packaging, or security testing.

See [`docs/IR-007_OUTPUT_RESERVATION_PROOF.md`](docs/IR-007_OUTPUT_RESERVATION_PROOF.md) for output-reservation evidence, [`docs/IR-008_CONCURRENT_RESERVATION_PROOF.md`](docs/IR-008_CONCURRENT_RESERVATION_PROOF.md) for in-process contention evidence, [`docs/IR-009_REQUEST_CONTEXT_ISOLATION_PROOF.md`](docs/IR-009_REQUEST_CONTEXT_ISOLATION_PROOF.md) for request-context isolation evidence, [`docs/IR-010_UNLOCK_ACKNOWLEDGEMENT_PROOF.md`](docs/IR-010_UNLOCK_ACKNOWLEDGEMENT_PROOF.md) for unlock acknowledgment evidence, and [`docs/IR-020_DEPENDENCY_REPRODUCIBILITY_PROOF.md`](docs/IR-020_DEPENDENCY_REPRODUCIBILITY_PROOF.md) for dependency-reproducibility and daily Python compatibility evidence.

## Security and privacy boundary

The HTTP listener binds to IPv4 loopback when started through the supplied server paths. TokenTotals itself does not send analytics to a QuietFireAI service. **Upstream model requests still leave the machine and go to the selected AI provider**; “local proxy” does not mean the AI request itself is zero-egress.

API keys are passed to LiteLLM for the upstream request and are not intentionally persisted by TokenTotals. Users should still review LiteLLM/provider behavior and their own operating environment before handling sensitive material.

## License

GNU General Public License v3.0. See [`LICENSE`](LICENSE).

Built by QuietFireAI.
