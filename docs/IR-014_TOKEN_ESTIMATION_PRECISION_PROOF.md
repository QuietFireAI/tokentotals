# IR-014 — Pre-flight token-estimation precision claim

**Classification:** UNSUPPORTED CLAIM / REPAIRED AND REVALIDATED  
**Date:** 2026-09-15  
**Branch:** `sol/forensic-hardening`

## What was wrong

The baseline public documentation described TokenTotals' pre-flight count as a BPE token count even though the reviewed implementation did not execute a verified provider/model tokenizer for that pre-flight estimate.

Baseline public wording included:

- README architecture copy describing a **“Pre-flight BPE token count & budget audit”**; and
- whitepaper language describing **“pre-flight cryptographic/BPE token counts.”**

That wording exceeded the precision of the implementation. The issue was a public accuracy/integrity claim, not evidence that the estimator itself was secretly a BPE implementation.

## Actual current estimator

`pricing_engine.estimate_text_tokens()` is intentionally simple and explicit:

```text
estimated_tokens = max(1, ceil(len(text encoded as UTF-8 bytes) / 3))
```

The function accepts an optional `model` argument, but that argument does not alter the calculation. The same UTF-8 text therefore receives the same local estimate for OpenAI, Anthropic, and Google model names.

This estimate exists for pre-flight pacing before trustworthy provider usage telemetry is available. It is not represented as a provider/model tokenizer result.

## Repair

The hardening branch now does four things:

1. README explicitly states that pre-flight token counts are **not represented as provider/model BPE counts** and identifies the estimator as a conservative UTF-8-length heuristic.
2. The whitepaper states the same boundary and says provider-reported usage is preferred after the response.
3. `tests/test_public_claim_integrity.py` rejects the baseline BPE/precision language, including “cryptographic/BPE token counts,” “deterministic BPE token count,” “exact BPE token count,” and “provider-accurate pre-flight token count.”
4. `docs/TOKEN_ESTIMATION_CONTRACT.md` makes the boundary normative across future UI, receipts, documentation, and tokenizer work. Its governing rule is that the precision of the language must never exceed the precision of the implementation.

No production estimator rewrite was made merely to preserve the baseline marketing claim.

## Attack / tests used

### 1. Exact heuristic behavior

`tests/test_pricing_engine.py::test_preflight_token_estimator_is_documented_utf8_heuristic_not_model_tokenizer` checks ordinary ASCII and multi-byte UTF-8 text and requires the implementation to equal:

```text
max(1, ceil(utf8_byte_length / 3))
```

It also sends the same text through representative OpenAI, Anthropic, and Google model names and requires the estimate to remain identical.

### 2. Public-claim regression gate

`tests/test_public_claim_integrity.py::test_preflight_token_estimator_cannot_be_claimed_as_bpe_or_exact` rejects unsupported BPE/exact/provider-accurate wording and requires the README and whitepaper to preserve the current heuristic disclosure.

### 3. Provider-usage reconciliation proof

`tests/test_ir014_token_estimation_boundary.py::test_provider_reported_usage_supersedes_preflight_token_heuristic` deliberately makes the local estimator return **10,000 input tokens** so the pre-flight reservation is obviously larger than the final provider telemetry.

The mocked provider response then reports:

```text
prompt/input tokens: 7
completion/output tokens: 3
```

The test captures the spend already reserved when upstream execution begins, then requires the persisted final spend after the response to equal the supported base-rate calculation for **7 input + 3 output tokens**, not the deliberately inflated 10,000-token heuristic.

This directly proves the current lifecycle distinction:

```text
before response -> estimate locally and reserve conservatively
after usable provider usage -> reconcile from observed provider usage
```

## Result

GitHub Actions run `34990973664` on commit `f9decbafa2f9fbc1cfd9dac0d94464a890828fac` passed:

- **64 passed / 0 failed** on Ubuntu / CPython 3.12.14;
- `pip check`: PASS;
- Linux runtime smoke: PASS;
- Windows runtime smoke: PASS;
- Windows constrained PyInstaller/build-tool smoke: PASS.

The new reconciliation test passed with the intentionally divergent pre-flight estimate and provider-reported usage.

## What this proves

TokenTotals no longer represents its current pre-flight heuristic as BPE/exact/model-specific tokenization. The implementation, documentation, and regression tests agree on what the estimator actually is, and usable provider token telemetry supersedes the heuristic for the supported post-response reconciliation calculation.

## Remaining boundary

Provider-reported input/output token counts are stronger observed telemetry than the local heuristic, but the resulting dollar value remains an **independent cost estimate**, not invoice parity. Provider billing can still depend on cache detail, context bands, service tier, region, tools, modalities, promotions, account-specific terms, and other implemented or unimplemented billing dimensions.

A future true tokenizer integration must define and validate its model/encoding mappings, request serialization rules, tokenizer provenance/version, aliases/snapshots, unsupported-model behavior, and reference fixtures before public wording may claim provider/model tokenization.

Installing a tokenizer package as a dependency is not sufficient evidence by itself.
