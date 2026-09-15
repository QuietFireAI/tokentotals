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
- Unknown model pricing **fails closed** instead of using a generic dollar fallback.
- Conservative pre-flight reservation for estimated input **and bounded output** tokens.
- Atomic in-process budget check/reservation and post-response reconciliation.
- Daily local spend state and active-thread spend state under `~/.tokentotals`.
- Lock state with desktop tray/modal monitoring on the Windows GUI.
- Literal `I UNDERSTAND` requirement for the HTTP unlock endpoint.
- Explicit `BOOST $5` acknowledgement for dashboard budget boosts.
- Dashboard that displays runtime state only; it does not ship fake token/cache telemetry.
- SSE-style streaming pass-through. If final usage is unavailable, TokenTotals keeps the conservative reservation and marks the stream unreconciled rather than inventing a final cost.

## What is **not** claimed

- Pre-flight token counts are **not represented as provider/model BPE counts**. The current local estimator is a conservative UTF-8 length heuristic.
- TokenTotals does not claim invoice parity or guaranteed identity with provider billing.
- The current OpenAI source synchronization is not the same thing as a complete OpenAI billing adapter. Service-tier, cache, context-band, regional, tool, modality, storage, and other billing-event accounting are implemented only when specifically documented and tested.
- Anthropic and Google do not yet have the dynamic official-source synchronization path implemented for OpenAI; they remain dated verified catalog entries in this revision.
- It does not intercept applications that bypass the configured local proxy.
- It does not provide a TokenTotals WebSocket proxy endpoint.
- It does not inject a telemetry badge into every IDE/chat turn.
- It is not a FedRAMP/FISMA authorization and does not make an environment compliant by itself.
- The packaged GUI/build path in this repository is currently Windows-oriented. The Python proxy may be portable, but macOS/Linux GUI packaging is not release-tested here.

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

Anthropic and Google continue to use the checked-in dated catalog until equivalent official-source adapters are separately implemented and tested.

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
4. computes a conservative high-side reservation;
5. atomically checks and reserves that amount against the daily limit;
6. sends the request only if the reservation succeeds;
7. reconciles the reservation to provider-reported token usage when available.

This closes the baseline implementation's input-only pre-flight gap and its check-then-send concurrency race within a single TokenTotals process.

### Important process boundary

The budget lock in this revision is **process-local**. Do not run multiple TokenTotals proxy processes against the same state file and assume the hard-budget invariant is preserved. Cross-process locking is a separate requirement.

## Quickstart from source

```bash
python -m venv .venv
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
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

`app_gui.py` starts the proxy, tray monitor, and dashboard integration. The modal lock dialog requires typing `I UNDERSTAND` before native unlock. The native `+$5` button is an explicit local user action.

Build on Windows:

```powershell
.\build.ps1
```

The build script no longer depends on a developer-specific Antigravity/Gemini plugin directory and bundles `pricing_catalog.json` with the application.

## Tests

Install development dependencies and run:

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

The forensic hardening suite now covers:

- verified input/output cost math;
- fail-closed unknown model pricing;
- high-side pre-flight guard rates;
- atomic reservation/reconciliation;
- unlock and boost acknowledgements;
- prevention of upstream calls after price/budget rejection;
- bounded output reservation;
- removal of hard-coded dashboard telemetry;
- OpenAI official-source pricing parsing;
- preservation of the last verified OpenAI snapshot after incomplete/failed checks;
- runtime consumption of the same promoted OpenAI snapshot;
- quarantine of suspicious price jumps;
- same-day retry after failed source checks;
- review-required handling when source content changes without a recognized pricing/rule change;
- committed matrix drift detection against the base verified pricing view;
- clean-install use of the real declared LiteLLM dependency rather than a test-injected stand-in.

GitHub Actions on Ubuntu/Python 3.12 passed **21 tests / 0 failures** after the IR-006 dependency-proof test was hardened. This is regression evidence, not a substitute for live-provider integration, load, packaging, or security testing.

## Security and privacy boundary

The HTTP listener binds to IPv4 loopback when started through the supplied server paths. TokenTotals itself does not send analytics to a QuietFireAI service. **Upstream model requests still leave the machine and go to the selected AI provider**; “local proxy” does not mean the AI request itself is zero-egress.

API keys are passed to LiteLLM for the upstream request and are not intentionally persisted by TokenTotals. Users should still review LiteLLM/provider behavior and their own operating environment before handling sensitive material.

## License

GNU General Public License v3.0. See [`LICENSE`](LICENSE).

Built by QuietFireAI.
