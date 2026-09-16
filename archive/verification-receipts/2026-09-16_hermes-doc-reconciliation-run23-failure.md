# Verification Receipt — Hermes Integration Run 23 Documentation Failure

**Date:** 2026-09-16  
**Branch:** `integration-hermes-turnreceipt`  
**Head commit tested:** `634a91a483e0593787bd4675cc5c2a98508781db`  
**GitHub Actions run:** `35163371762`  
**Workflow:** `TokenTotals Hermes Integration`

## Result

Observed job status at diagnosis:

- `tokentotals-hermes-contract`: PASS
- `hermes-upstream-doctor`: PASS
- `tokentotals-regression`: FAIL
- `windows-hermes-candidate`: still in progress when the regression failure was diagnosed

The full regression suite ran **256 tests** and produced **255 passes / 1 failure**.

## Sole regression failure

`test_public_wording_cleanup.PublicWordingCleanupTests.test_turn_receipt_definition_and_public_surfaces_are_preserved`

The prior missing formalization sentence was repaired successfully. The next required public-contract phrase exposed by the same test was absent from `TURN_RECEIPTS.md`:

```text
provider account and final invoice remain authoritative
```

The document already stated similar invoice/billing limitations, so this remains classified as a **public documentation-contract reconciliation defect**, not a Hermes runtime, accounting, plugin, provider, or correlation defect.

## Repair boundary

One documentation reconciliation in `TURN_RECEIPTS.md` only. Reconcile the complete set of public receipt-contract semantics already enforced by the existing test so CI is not used as a one-string-at-a-time discovery mechanism. No runtime or Hermes code changes are justified by this failure.

## Evidence rule

This failed run remains preserved. A later run must independently prove the complete public-contract reconciliation and all four Hermes workflow jobs before the branch can be called automated-green.
