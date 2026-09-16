# TokenTotals — Hermes Build

## Product gate

The Hermes build exists to prove the original Turn Receipt requirement on a telemetry-rich
surface:

> Use Hermes normally. When the answer finishes, a Turn Receipt appears directly beneath
> that answer.

A green unit test, a local TokenTotals `/chat` receipt, or a ledger-only Hermes record does
not satisfy this gate.

## Why Hermes is the primary proof surface

Hermes publishes a documented `hermes.observer.v1` contract with stable `session_id`,
`turn_id`, `api_request_id`, request lifecycle hooks, and normalized usage. That lets
TokenTotals bind accounting to explicit identities instead of DOM timing guesses.

The integration consumes:

- `pre_llm_call` — create turn scope;
- `post_api_request` — one successful provider transaction;
- `api_request_error` — retry/error evidence;
- `post_llm_call` — close the human turn and settle one top-level receipt;
- `on_session_finalize` — cleanup.

Each successful provider API request is priced independently before the human-turn total is
summed. This avoids incorrectly applying one pricing tier to an aggregate that actually
contains several provider requests.

## Missing-data rule

Hermes' canonical optional buckets use integer zero even when an upstream optional field may
not have been present. TokenTotals therefore does not blindly turn every canonical zero into
an observed zero. Optional cache/reasoning buckets are shown only when positive evidence is
present; otherwise they remain unavailable in the top-level receipt.

## Receipt topology

One human Hermes turn produces one top-level Turn Receipt.

Expanded evidence preserves the child provider transactions:

`Hermes turn -> API request 1 -> API request 2 -> ...`

The top-level cost is:

- `hermes_child_transaction_sum_complete` only when every child transaction is priced
  completely by a TokenTotals provider registry;
- `hermes_child_transaction_sum_partial` when only part of the child cost can be priced;
- `unavailable` when no defensible child cost exists.

Missing cost is never converted to a displayed zero.

## Answer integrity

The model does not calculate the receipt.

The plugin never asks a model for usage or cost, and never sends assistant text to
TokenTotals. Hermes renders the ordinary answer first. A guarded display adapter then prints
TokenTotals' independently rendered terminal receipt.

The current Hermes plugin contract has no documented post-response-render hook. For this
candidate, the display adapter wraps the current Hermes
`CLIChatTurnMixin._chat_print_response_panel` method in memory. It calls the original method
first and does not alter its response argument. If this seam changes, inline placement
fails closed. The accounting hooks remain on the documented observer contract.

A future upstream Hermes `post_turn_render` observer/contribution hook would remove this one
compatibility shim.

## Acceptance tests

1. one no-tool Hermes prompt -> one receipt;
2. provider answer text is unchanged;
3. receipt appears after the exact answer panel;
4. receipt `turn_id` derives from Hermes stable turn identity;
5. one tool-loop turn with several API requests -> one top-level receipt with child count;
6. child transactions are priced individually, then summed;
7. failed/retried API attempts do not become successful billed children;
8. duplicate observer callbacks are idempotent;
9. optional missing telemetry is unavailable, not zero;
10. TokenTotals stopped/unreachable does not break Hermes;
11. plugin disabled leaves normal Hermes behavior unchanged;
12. restart + second turn does not cross-bind a prior receipt;
13. Standard and Expanded terminal receipts use the same canonical receipt object;
14. no second LLM call occurs for receipt calculation or rendering.

## Pinned upstream reference

Initial implementation research used Hermes commit:

`d5b3cad7b98b3bcd157ea8b585759b0bb4fb8a6d`

The build must be revalidated against the installed Hermes version before release.
