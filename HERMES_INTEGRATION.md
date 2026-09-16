# TokenTotals — Hermes Launch Integration

## Launch definition

Hermes is the first TokenTotals launch surface.

The product behavior is:

> **Use Hermes normally. When the answer finishes, the matching Turn Receipt appears directly beneath that answer.**

The TokenTotals built-in `/chat` page is a reference/test harness. Browser-extension work is experimental/testing work. Neither substitutes for the Hermes launch gate.

## Why Hermes became the launch path

TokenTotals' initial integration/testing concept used frontier-model/browser workflows. That work helped prove the core receipt machinery, but continuing to validate those surfaces at the project's evidence standard became **too cost-intensive on our end**.

The project therefore changed the launch dependency rather than lowering the proof bar. Hermes offers a cleaner host for first release because it exposes stable turn/request identities and documented observer telemetry. This lets TokenTotals test actual simple turns, retries, tools, and multi-call behavior without making expensive frontier-browser testing the condition for launch.

The earlier browser/frontier work remains a valid testing/reference track and may continue later. The sequence is now **Hermes first, OpenClaw next, browser/frontier adapters as continuing work rather than a launch blocker**.

## Current status

**Implemented:** Hermes accounting/placement candidate.  
**Automated tested:** yes.  
**Pinned real-Hermes plugin doctor:** passed.  
**Windows candidate package/smoke:** passed.  
**Live user-zero Hermes answer → receipt proof:** pending.  
**Merged/released:** no.

The candidate remains a candidate until the exact live behavior above is observed and reconciled.

## Architecture

```text
Hermes user turn
    ↓
Hermes observer lifecycle
    ├─ stable session_id
    ├─ stable turn_id
    ├─ stable api_request_id
    ├─ provider/model metadata
    ├─ normalized usage
    └─ request success/error lifecycle
    ↓
TurnReceipt Hermes plugin
    ↓ privacy-limited accounting payload
TokenTotals localhost engine
    ├─ child transaction accounting
    ├─ deterministic pricing
    ├─ missing-data semantics
    ├─ canonical receipt
    ├─ ledger/evidence
    └─ Standard/Expanded rendering
    ↓
Hermes answer renders normally
    ↓
Turn Receipt renders beneath that answer
```

## Hermes observer hooks

The accounting path uses Hermes' documented plugin hooks:

- `pre_llm_call` — establish turn scope;
- `post_api_request` — record one successful provider transaction;
- `api_request_error` — preserve retry/failure evidence;
- `post_llm_call` — settle one top-level human-turn receipt; and
- `on_session_finalize` — clean up session-scoped transient state.

The plugin accepts additive keyword payloads so it can coexist with Hermes' documented hook-evolution model.

## Multi-call turns

One human instruction can involve several model transactions.

TokenTotals does not collapse those children before accounting:

```text
Hermes turn
  ├─ API request 1
  ├─ API request 2
  └─ API request 3
        ↓
one top-level Turn Receipt
```

Successful child calls are priced independently when enough telemetry/pricing information exists. The top-level receipt then sums the defensible child amounts.

The turn cost basis is:

- `hermes_child_transaction_sum_complete` when every successful child is completely priced;
- `hermes_child_transaction_sum_partial` when only part of the child cost can be reconstructed; or
- `unavailable` when no defensible child cost can be established.

Failed/retried attempts remain failure evidence and are not silently turned into successful billed children.

## Missing-data rule

Hermes can normalize some optional usage buckets to numeric zero even when the original upstream field may not have been present.

TokenTotals therefore does not automatically interpret every optional canonical zero as an observed zero.

For optional cache/reasoning-style buckets:

- positive evidence can be recorded;
- defensibly observed zero can be recorded only when the upstream/runtime contract establishes it; and
- otherwise the top-level receipt keeps the field unavailable.

The governing rule remains:

> **missing ≠ 0**

## Answer integrity

The model does not calculate its own receipt.

The plugin does not ask Hermes' model for token counts, cost, or receipt prose. It does not issue a second LLM call merely to calculate or render the receipt.

Hermes renders the ordinary answer first.

The current Hermes plugin contract does not expose a documented post-response-render callback. For this candidate, the placement layer uses one guarded compatibility shim around Hermes' current `CLIChatTurnMixin._chat_print_response_panel` method.

The shim:

- calls the original Hermes method first;
- does not alter the response argument;
- prints the separately settled TokenTotals receipt afterward; and
- disables inline placement rather than guessing if the expected seam disappears.

Accounting remains on the documented observer contract even if placement compatibility changes.

A future documented Hermes post-render contribution/hook would allow this one compatibility shim to be removed.

## Exact answer binding

The plugin does not persist or transmit the assistant answer to TokenTotals.

For CLI placement it computes a short-lived in-memory digest of the final answer. The digest is used only to match the already settled receipt to the exact response panel rendered by Hermes.

The answer text itself is not written to the Hermes evidence store or sent in the TokenTotals accounting payload.

## Privacy boundary

The plugin sends TokenTotals only the metadata needed for receipt accounting and correlation, including where available:

- session / turn / API-request IDs;
- API-call count/order;
- provider/model/platform/API-mode identity;
- numeric usage buckets;
- request timing; and
- failure status/type metadata.

It excludes:

- prompt text;
- answer text;
- conversation history;
- tool arguments/results;
- API keys;
- cookies;
- authorization headers; and
- hidden reasoning content.

## Acceptance tests

The Hermes launch gate requires live evidence for all of the following:

1. one normal no-tool Hermes prompt produces one receipt;
2. the Hermes answer is unchanged;
3. the receipt appears immediately after the exact answer panel;
4. receipt identity derives from stable Hermes turn identity;
5. successive turns do not cross-bind;
6. one multi-call/tool-loop turn produces one top-level receipt with child count/evidence;
7. child transactions are priced individually before summing;
8. failed/retried API attempts do not become invented successful billed children;
9. duplicate observer callbacks remain idempotent;
10. missing telemetry remains unavailable rather than fake zero;
11. TokenTotals stopped/unreachable does not break Hermes;
12. plugin disabled leaves ordinary Hermes behavior unchanged;
13. restart/new session does not attach an old receipt;
14. Standard and Expanded use the same canonical receipt object; and
15. no second LLM call occurs for receipt calculation/rendering.

CI, `/chat`, a screenshot of a mock receipt, or a ledger-only record cannot replace these live acceptance behaviors.

## Pinned upstream reference

Initial implementation and automated compatibility work used Hermes commit:

`d5b3cad7b98b3bcd157ea8b585759b0bb4fb8a6d`

The installed Hermes version must be checked/revalidated before release because the display placement shim intentionally depends on a current internal CLI render seam.

## After Hermes

OpenClaw is the next first-class integration target. Its lifecycle/aggregation semantics will be tested independently rather than assumed equivalent to Hermes.

Browser/frontier integrations remain continuing research/testing work after those first-class agent integrations are established.