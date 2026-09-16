# TokenTotals TurnReceipt for Hermes

This integration is deliberately split into two layers.

1. **Accounting / correlation** uses Hermes' documented observer hooks:
   `pre_llm_call`, `post_api_request`, `api_request_error`, `post_llm_call`, and
   `on_session_finalize`.
2. **CLI placement** wraps Hermes' current `_chat_print_response_panel` method at
   runtime so the normal Hermes answer is rendered first and the receipt is printed
   immediately below it. The answer is never replaced, appended to, or sent through
   another model call.

The placement wrapper is guarded and fail-open because Hermes does not currently
document a post-response-render plugin hook. If that method disappears, accounting
continues but inline placement disables itself instead of guessing.

## Data boundary

The plugin sends TokenTotals only:

- session / turn / API-request correlation IDs;
- provider, model, platform, API mode;
- numeric usage buckets exposed by `hermes.observer.v1`;
- request timing;
- failure status/type metadata.

It does **not** send prompt text, assistant response text, conversation history,
tool arguments/results, API keys, cookies, authorization headers, or hidden reasoning.

The assistant response is hashed in memory only to bind the settled receipt to the
exact CLI response panel. The response text is not persisted or transmitted by this
plugin.

## Local engine

Start the TokenTotals Hermes candidate first. The plugin probes localhost ports
8080-8089, matching TokenTotals' desktop fallback behavior.

Optional environment variables:

- `HERMES_TURNRECEIPT_URL=http://127.0.0.1:8080`
- `HERMES_TURNRECEIPT_MODE=standard|expanded`

## Install during development

Copy this directory to:

`~/.hermes/plugins/turnreceipt/`

Then run:

`hermes plugins doctor ~/.hermes/plugins/turnreceipt --ci`

Enable it through the normal Hermes plugin workflow.

## Proof gate

The build is not considered complete until a real Hermes turn shows:

**normal Hermes answer -> Turn Receipt directly beneath it**

and the receipt's request count/tokens/cost reconcile with the Hermes observer events
for that same `turn_id`.
