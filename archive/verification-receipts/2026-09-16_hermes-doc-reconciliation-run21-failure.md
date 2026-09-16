# Verification Receipt — Hermes Integration Run 21 Documentation Failure

**Date:** 2026-09-16  
**Branch:** `integration-hermes-turnreceipt`  
**Head commit tested:** `d300fa10974c39dabf27cf3f58b282b365e1dd30`  
**GitHub Actions run:** `35163193827`  
**Workflow:** `TokenTotals Hermes Integration`

## Result

The Hermes integration itself remained green in the observed jobs:

- `tokentotals-hermes-contract`: PASS
- `hermes-upstream-doctor`: PASS
- Windows Hermes candidate: still executing when the regression failure was diagnosed
- `tokentotals-regression`: FAIL

The full regression suite ran **256 tests** and produced **255 passes / 1 failure**.

## Sole failure

`test_public_wording_cleanup.PublicWordingCleanupTests.test_turn_receipt_definition_and_public_surfaces_are_preserved`

Required phrase absent from `TURN_RECEIPTS.md`:

```text
formalizes the term **turn receipt**
```

The document still contained a substantive definition of Turn Receipt. The failure is therefore classified as a **public documentation-contract regression**, not a Hermes runtime, accounting, plugin, packaging, or correlation failure.

## Repair boundary

One repair only:

- restore explicit formalization language to `TURN_RECEIPTS.md` without changing the receipt definition, Hermes runtime, accounting engine, plugin, or provider logic.

## Evidence rule

This failed run is preserved rather than overwritten or described as green. A subsequent run must independently prove the documentation repair and full regression status.
