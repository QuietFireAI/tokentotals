# Browser / External Surface Integration — Experimental Track

This document no longer defines the TokenTotals launch path.

**Launch surface:** Hermes Agent  
**Next first-class integration:** OpenClaw  
**Browser work:** experimental/reference testing only

## Why this track still exists

The original product requirement remains useful beyond Hermes:

> use the AI where you already use it; when the answer finishes, the matching Turn Receipt appears directly beneath that answer.

Hermes gives TokenTotals a strong telemetry/correlation contract for proving that idea first.

Consumer browser sites are different. They may allow DOM placement while exposing only partial—or no—same-turn usage telemetry. Therefore browser work must not be used to make a stronger accounting claim than the underlying evidence supports.

## Built-in `/chat`

TokenTotals' built-in `/chat` page is a controlled reference client.

It is useful for testing:

- provider plumbing;
- canonical receipt creation;
- receipt settlement;
- exact TokenTotals-owned receipt IDs;
- Standard/Expanded rendering; and
- missing-data behavior.

It is **not** the Hermes launch destination and does not satisfy the Hermes product gate.

## Browser extension track

The experimental extension architecture can:

- observe permitted page/runtime signals;
- communicate with the localhost TokenTotals engine;
- render a receipt container beneath a matching answer element; and
- request canonical TokenTotals receipt rendering.

That proves placement is technically possible. It does not prove that a consumer site exposes sufficient accounting telemetry.

## Hard evidence rule

A provider-site browser adapter may only label a field observed when that exact field is legitimately exposed to the adapter for the same transaction.

If a site exposes:

- stable turn/message IDs but no token usage, token fields remain unavailable;
- token usage but no defensible pricing dimension, cost remains unavailable/partial;
- no stable identity connecting telemetry to the visible answer, settlement must not rely on timing proximity alone.

A receipt-shaped UI is not proof of accounting.

## Privacy boundary

Experimental browser probes must exclude ordinary conversation content and credentials from the TokenTotals accounting payload.

The intended whitelist is limited to defensible transaction metadata such as:

- stable response/turn/request IDs;
- provider/model identity;
- numeric usage counters;
- pricing-relevant tier/mode information where explicitly exposed; and
- timing/status metadata required for correlation.

Prompt text, answer text, API keys, cookies, authorization headers and hidden reasoning are not accounting inputs merely because a page happens to contain them.

## Experimental acceptance gate

If browser-provider work resumes, an adapter is not complete until one real transaction proves:

1. normal provider-site prompt;
2. normal answer remains unchanged;
3. receipt appears under that exact answer;
4. no second model call creates the receipt;
5. stable same-turn identity exists;
6. observed fields are actually observed;
7. missing fields remain unavailable;
8. deterministic TokenTotals accounting produces the receipt; and
9. reload/concurrency/new-thread behavior does not cross-bind receipts.

## Priority

Browser work is currently behind:

1. Hermes live proof and launch hardening;
2. OpenClaw integration/proof; and
3. Lobster workflow stress testing.

It may move forward sooner only when it directly supports a concrete test or new evidence makes it the stronger integration path.
