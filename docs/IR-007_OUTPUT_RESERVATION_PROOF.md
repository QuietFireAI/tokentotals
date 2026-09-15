# IR-007 Output Reservation Proof

**Finding:** Circuit breaker reserved input cost only  
**Classification:** CONFIRMED SAFETY DEFECT / REPAIRED AND REVALIDATED  
**Repair branch:** `sol/forensic-hardening`  
**Revalidation date:** 2026-09-15

## Baseline defect

Baseline `proxy_server.py` estimated prompt tokens, resolved pricing, and called:

```python
calculate_cost(pricing, estimated_tokens, 0)
```

The pre-flight budget decision therefore reserved input cost only. The output side of the transaction was not represented in the reservation before upstream egress.

**Impact:** a request could pass the pre-flight budget check and then generate billable output that pushed the transaction beyond the amount considered by the gate.

## Repair

The hardened proxy now performs the budget decision against the model that will actually be routed upstream and builds a conservative reservation from both sides of the supported text-token transaction:

```text
reservation = conservative input estimate + bounded output ceiling
```

For caller-supplied output ceilings, both `max_tokens` and `max_completion_tokens` are inspected. If both are supplied, TokenTotals reserves against the larger valid value so the smaller field cannot create an under-reservation path.

If the request supplies no output ceiling, TokenTotals derives a bounded allowance from:

1. the configured `default_max_output_tokens`; and
2. the amount affordable under the remaining daily budget at the model's conservative output guard rate.

The bounded value is inserted into the upstream payload before the request is sent.

The complete conservative reservation is then passed to `config_manager.try_reserve_spend()`. That state operation commits the reservation before `litellm.acompletion()` is invoked. If the reservation would exceed the daily limit, TokenTotals rejects the request and does not call upstream.

## Reconciliation behavior

For non-stream responses with usable provider-reported input/output token counts, the pre-flight reservation is reconciled to the supported post-response estimate.

If a stream completes without usable final usage telemetry, TokenTotals deliberately keeps the conservative reservation and increments `unreconciled_streams`. Unknown final usage is therefore not converted into an invented lower amount and does not release budget headroom merely to make the meter look complete.

If the upstream call itself fails before a billable response is accepted, the existing error path reconciles the reservation back to zero.

## Adversarial revalidation

The 2026-09-15 IR-007 pass added two direct lifecycle tests without changing production proxy logic.

### Reservation exists before upstream execution

The first test calculates the expected conservative input-plus-output reservation for a bounded request, replaces `litellm.acompletion()` with a test function, and reads TokenTotals state **from inside that mocked upstream function**.

The test requires:

- the expected output ceiling to be present in the upstream call;
- `current_spend_usd` to already equal the full conservative reservation when upstream execution begins; and
- that amount to be greater than the input-only reservation.

This would fail if reservation were moved after upstream egress or if output cost were dropped from the pre-flight amount.

### Usage-less stream retains reservation

The second test returns a streamed response with no final usage telemetry. It requires:

- a non-zero conservative reservation to exist before upstream execution;
- the same reservation to remain in `current_spend_usd` after the stream ends; and
- `unreconciled_streams` to increment.

This would fail if an unknown streamed total were silently treated as zero or if the conservative reservation were released without evidence.

## Existing related regression coverage

The suite already verifies that:

- a large requested output ceiling can block the request before upstream egress;
- conflicting `max_tokens` and `max_completion_tokens` values reserve against the larger ceiling;
- a missing output ceiling receives a bounded value before egress and later reconciles when usage is reported; and
- auto-economy routing reserves against the model actually sent upstream rather than the originally requested model.

## Revalidation evidence

On the IR-007 test revision:

- focused regression suite: **35 passed / 0 failed**;
- CPython compatibility check: **PASS**;
- constrained dependency install and `pip check`: **PASS**;
- Windows clean runtime/import job: **PASS**;
- the remaining clean-environment jobs were retained unchanged from the IR-020 reproducibility contract.

No production code was modified during the IR-007 revalidation pass because the existing hardened implementation already satisfied the tested output-reservation invariant.

## Boundary

This proof covers the supported `/v1/chat/completions` text-token reservation path represented by the current pricing engine. It does not claim that every provider billing dimension is already represented. Tool fees, multimodal meters, service tiers, regional modifiers, cache accounting, storage/runtime charges, and other provider-specific billable events require explicit implementation and testing before they can be included in a high-confidence transaction estimate.

The budget lock also remains process-local; cross-process locking is tracked separately from IR-007.

## Verdict

**IR-007 — PASS: REPAIRED AND REVALIDATED.**

The baseline input-only safety defect is removed. Supported text-token requests reserve conservative input plus bounded output before upstream egress, and missing final stream usage preserves rather than releases the conservative reservation.