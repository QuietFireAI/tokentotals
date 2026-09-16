# TokenTotals v2.6.0 — Turn Receipts for AI

TokenTotals v2.6.0 makes the **Turn Receipt** the primary user-facing artifact: an inspectable per-turn record of AI usage telemetry, calculation provenance, reconciliation, availability, and estimated cost.

## What’s new

- **Turn Receipts in the conversation flow.** The local `/chat` surface renders a receipt directly beneath each completed model response.
- **Standard / Expanded display.** Standard is the compact default; Expanded exposes deeper turn detail and the current thread aggregate.
- **Exact turn binding.** Responses carry the server-owned `X-TokenTotals-Receipt-ID`, so concurrent turns can be matched to the correct receipt without modifying provider response content.
- **Visible uncertainty.** Fallback estimates, list-equivalent estimates, and unavailable cost are labeled explicitly. Missing telemetry is never silently converted to zero.
- **Pricing provenance.** Where recorded usage and component cost support it, receipts preserve reproducible effective rates from the completed turn rather than re-reading future price tables.
- **Provider identity preserved.** Requested, canonical, and observed model/provider information remain distinct where available; TokenTotals does not silently substitute a model.
- **Simplified Windows package.** The extracted executable is now `TokenTotals.exe`.

## Release evidence

- Source commit: `ef72901a4b72ee3145c1a0fc628c01b2973ff526`
- Linux regression: **238/238 tests passed**
- Windows PyInstaller build: **passed**
- Packaged smoke: **passed**, including `turn_receipt_surfaces_ok`
- Windows candidate size: **83,685,797 bytes**
- Windows candidate SHA-256: `b0d813331eb7418625db8216cf20850b93d4d9f81bb4117c0ad2d49667e8cc48`

## Important boundary

**A Turn Receipt is an independent usage estimate by TokenTotals — not a provider invoice.** Provider billing/account records remain authoritative. TokenTotals reports what it can establish from legitimately available telemetry, distinguishes observed from derived values, and marks unavailable dimensions rather than inventing them.

The desktop package in this release is validated for Windows. This release does not claim a macOS or Linux desktop package.

Licensed under GNU GPLv3.
