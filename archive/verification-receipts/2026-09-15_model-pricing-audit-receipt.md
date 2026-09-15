# TokenTotals Model-Pricing Audit Receipt

**Receipt date:** 2026-09-15  
**Repository:** `QuietFireAI/tokentotals`  
**Branch:** `main`  
**Snapshot commit inspected:** `2648ace614a62600e4777deb9921d1130f9b962a`

## Purpose

This file is a permanent historical receipt of the model-pricing review state at the point the audit thread was continued after a conversation/system-cap handoff.

It is intentionally preserved whether the reviewed state proves correct, partially correct, or incorrect. It is evidence of what was inspected and what the repository asserted at this point in time; it is **not** a claim that any listed price, model, registry, or calculation is exact or permanently current.

TokenTotals should be described as producing the most accurate calculation reasonably available from the telemetry, model identity, provider pricing information, and billing particulars available to it at calculation time. Provider billing rules can contain model-specific and platform-specific conditions that must be represented explicitly when known.

## Repository state observed

At the inspected snapshot:

- `MODEL_COMPARISON_MATRIX.md` stated that TokenTotals normalizes costs against "official developer API pricing registries" across OpenAI, Anthropic, and Google.
- `pricing_sync.py` fetched its remote pricing catalog from LiteLLM's public `model_prices_and_context_window.json` registry and cached it locally as `model_prices.json`.
- `pricing_sync.py` fell back to the bundled `litellm.model_cost` dictionary if the local cached catalog was unavailable.
- `proxy_server.py` attempted to import a pricing engine and token estimator from a machine-specific local filesystem path and supplied hard-coded fallback behavior if that import failed.
- The repository root did not yet contain an archive/evidence directory before this receipt was created.

## Audit rule carried forward

The governing sequence for remaining work is:

1. Diagnose one concern completely before implementation.
2. Identify the actual failure/mismatch path and the smallest defensible repair.
3. Implement only that item.
4. Recheck/regression-test the item after implementation.
5. Update documentation to match runtime reality.
6. Preserve material verification evidence in this archive as a receipt, including findings that are unfavorable.
7. Proceed to the next item only after the current one has been rechecked.

No fork is required for this cleanup sequence; the repository itself is the source of truth.

## Next unresolved item at handoff

**Source-of-truth mismatch for model pricing.**

The public comparison document describes pricing as coming from official provider registries, while the current synchronization code obtains its live catalog from LiteLLM, a third-party registry. This needs diagnosis before any implementation change. The diagnosis must determine what pricing information is actually available from each provider, which fields TokenTotals can observe, which billing particulars can be calculated reliably, what requires provider/model-specific handling, and what provenance/freshness metadata should accompany every calculation.

## Historical commit trail immediately preceding this receipt

Recent repository history included multiple revisions to model catalogs, pricing tables, and documentation, including commits that alternately added, removed, or replaced OpenAI model references. Those changes are retained in Git history and should be treated as evidence of why model catalog/pricing provenance must be explicit and mechanically verifiable rather than inferred from static documentation.

## Interpretation

This receipt is deliberately conservative. A future audit may validate, supersede, or contradict any underlying pricing assertion. That outcome should be appended through a new receipt rather than rewriting this historical record.