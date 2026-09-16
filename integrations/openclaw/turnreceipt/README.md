# TokenTotals TurnReceipt for OpenClaw

This plugin adds a TokenTotals Turn Receipt to the final OpenClaw reply without asking the model to calculate its own accounting.

## Why this integration is different from a browser adapter

OpenClaw exposes the transaction boundary directly. The plugin uses OpenClaw's typed plugin hooks rather than DOM timing or network scraping:

- `model_call_started` / `model_call_ended` provide sanitized provider/model call lifecycle metadata;
- `reply_payload_sending` supplies the exact per-turn `runId`, canonical session key, and the live `usageState` for that reply;
- `usageState.usage` is OpenClaw's turn aggregate across model work;
- `usageState.lastUsage` preserves the final model-call snapshot when the harness exposes it; and
- `usageState.turnUsd` can carry OpenClaw's own recorded/estimated turn amount.

The receipt is correlated by OpenClaw `runId`, not by timing proximity.

## Answer integrity

The plugin does not rewrite `payload.text`.

After TokenTotals settles the turn, the plugin appends the receipt as OpenClaw `presentation` metadata. OpenClaw can render that presentation natively or deterministically degrade it to text beneath the existing answer on channels that do not support native presentation blocks.

No second model call is made merely to calculate or render the receipt.

## Privacy boundary

The TokenTotals request contains only accounting/correlation metadata:

- `runId` and canonical session key;
- provider/model/resolved model reference;
- normalized turn usage;
- final-call usage where available;
- runtime turn cost where OpenClaw exposes one;
- context-budget/used-token counters where available;
- model-call lifecycle IDs/outcomes/timing; and
- non-content runtime flags such as fast mode/fallback mode.

The plugin does not send TokenTotals:

- prompt text;
- assistant answer text;
- conversation history;
- tool arguments/results;
- API keys;
- cookies;
- authorization headers; or
- hidden reasoning content.

`reply_payload_sending` necessarily receives the outgoing payload from OpenClaw because it is the host presentation hook. This plugin does not read or transmit the answer text; it only preserves the payload and adds receipt presentation metadata.

## Cost provenance

OpenClaw normalizes `input` as uncached input and keeps cache reads/writes in separate buckets. TokenTotals preserves that distinction.

For a turn with exactly one completed model call, TokenTotals may independently reconstruct cost through its own provider pricing registry when the provider/model is supported.

For multi-call turns, local models, routed models, or provider plugins where aggregate token pricing would erase request boundaries, TokenTotals does **not** pretend the aggregate is one request. If OpenClaw supplies `turnUsd`, TokenTotals can preserve that value as `openclaw_runtime_reported`. Otherwise cost remains unavailable.

That distinction matters because OpenClaw itself can retain per-request pricing tiers across tool loops and retries, while a flattened aggregate can be mathematically wrong for tiered pricing.

## Local engine discovery

By default the plugin probes TokenTotals on loopback ports `8080` through `8089`, matching the Windows desktop runtime's fallback range.

Optional plugin config:

```json
{
  "mode": "standard",
  "engineUrl": "http://127.0.0.1:8080"
}
```

`engineUrl` is accepted only for `http://localhost` or `http://127.0.0.1`. Remote destinations are rejected by the plugin.

## Development install

From the plugin directory:

```bash
openclaw plugins install --link . --force
openclaw plugins enable turnreceipt
openclaw plugins inspect turnreceipt --runtime --json
```

The pre-release proof uses a pinned OpenClaw host version before public launch.

## Product gate

A successful package load is not the final proof.

The build passes only when a real OpenClaw user turn demonstrates:

```text
normal OpenClaw answer

TURN RECEIPT
...
TurnReceipt.com
```

The receipt must be tied to that exact `runId`, values must come from that turn's actual usage state, missing fields must remain unavailable, and disabling the plugin must leave OpenClaw behavior normal.
