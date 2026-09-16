# Final release reconciliation and Windows package recheck — 2026-09-15

## Focus

Final launch-proof pass for the hardened TokenTotals repository, with special attention to the shipped Windows desktop package. This receipt preserves both successful evidence and the packaging failures that were discovered and repaired during the pass.

This is a release-candidate verification receipt. It does **not** create or claim a public release tag.

## Scope checked

- current launch-facing repository/runtime wording and network boundary;
- current Windows-only desktop claim and Quickstart/build instructions;
- clean GitHub Actions regression execution;
- PyInstaller Windows build from the repository build script;
- packaged executable startup smoke path;
- required TokenTotals pricing registries and tray assets inside the package;
- LiteLLM runtime package data required by the bundled runtime;
- tiktoken encoding plugin availability inside the package;
- packaged proxy import and expected localhost routes;
- candidate ZIP creation and GitHub Actions artifact upload;
- public GitHub repository metadata manually corrected during closeout.

Same-day provider-engine verification receipts remain the source of truth for the OpenAI, Anthropic, and Google/Gemini calculator mechanics. No provider registry/calculator redesign was introduced by this packaging pass.

## Public metadata closeout

The repository About description was manually changed from the stale pre-hardening wording to:

> `🛡️  Turn receipts for AI`

The stale `zero-egress` repository topic was removed.

The historical v2.5 release body now carries a pre-hardening warning. Its old release title can still be renamed separately for clarity; that cosmetic historical-title change is not a runtime/package acceptance condition.

## Post-closeout artifact-identity reconciliation

A later release-preparation audit found that the original candidate-artifact block in this receipt had treated the release-candidate ZIP and GitHub Actions' uploaded artifact wrapper as though they were one object. That was an evidence-record defect, not a demonstrated runtime/package defect. The original values are intentionally preserved below as historical record, but **they are superseded and must not be used as the current candidate identity**.

The workflow was repaired so it now records the inner candidate ZIP SHA-256 and byte size before upload, then separately records the GitHub Actions artifact ID and artifact digest after upload. A regression test locks that separation in source.

Revalidation on the repaired workflow:

- source head: `495eb30b6e26bdf0dd6b48a3f522de06254c6ec3`
- Linux regression run: `35048613981`
- Linux regression job: `104643880073`
- regression result: **177/177 tests passed** (`Ran 177 tests in 0.746s` — `OK`)
- Windows workflow run: `35048614019`
- Windows job: `104643880026`
- Windows conclusion: **success** across build, packaged smoke, file verification, ZIP creation, candidate identity recording, artifact upload, and artifact identity recording
- inner candidate file: `TokenTotals_Windows_candidate.zip`
- inner candidate size: **83,661,751 bytes**
- inner candidate SHA-256: **`fdd36a2b44029f5577560cd1a88c7ea942ca1d0f074d7942817fb880339c526e`**
- GitHub Actions artifact name: `TokenTotals-Windows-candidate-fdd36a2b44029f5577560cd1a88c7ea942ca1d0f074d7942817fb880339c526e`
- GitHub Actions artifact ID: **`10427982768`**
- GitHub Actions artifact wrapper size: **82,673,019 bytes**
- GitHub Actions artifact digest: **`sha256:3834450401c94d4ac04c5127c8f1137bb639644a9c7bb0935a72a78e56b2c297`**

The differing inner ZIP hash/size and Actions artifact digest/size are expected because `actions/upload-artifact` packages the supplied candidate ZIP into its own downloadable artifact archive. The corrected workflow now makes those identities explicit instead of conflating them.

## Linux regression evidence

GitHub Actions regression run:

- run: `35045779521`
- job: `104635168300`
- head commit: `b85b164d652f283b864484d86e39e2a1367a625c`
- clean proxy import: passed
- regression result: **176/176 tests passed**
- unittest timing: `Ran 176 tests in 0.763s` — `OK`

The receipt/roadmap documentation closeout was then independently rechecked on a later clean runner; that evidence appears in the final section below.

## Windows packaging failure chain

The failed evidence is intentionally retained. Each failure exposed a separate packaging assumption and was repaired narrowly rather than bypassed.

### Failure 1 — packaged smoke did not terminate

The initial Windows package attempt completed PyInstaller successfully, launched `TokenTotals_QuietFireAI.exe --smoke-test`, but the smoke process did not exit. The workflow eventually hit its job timeout and the hosted runner terminated the orphan TokenTotals process.

Diagnosis: the package build itself had completed; the smoke harness lacked a deterministic process-exit contract.

Repair:

- force a deterministic process exit after packaged smoke success/failure; and
- add an independent 90-second PowerShell watchdog so a future smoke hang fails quickly instead of consuming the whole job timeout.

### Failure 2 — missing LiteLLM runtime package data

After the smoke path was moved ahead of desktop startup and instrumented with phase tracing, the packaged executable successfully loaded all four tray assets and all three TokenTotals pricing registries, then failed at `proxy_import_start` because the bundle did not contain LiteLLM's required runtime data file:

`litellm/model_prices_and_context_window_backup.json`

Repair:

- add PyInstaller `--collect-data "litellm"`; and
- add a package-verification assertion that the LiteLLM backup data exists in the resulting bundle.

### Failure 3 — missing tiktoken encoding plugin

Windows package run:

- run: `35045458150`
- head commit: `466f336bc8ae9d57f8871ae4dbeb026a017ab709`

The LiteLLM-data repair cleared the prior missing-file failure. The new trace reached `proxy_import_start` and then failed with:

- `ValueError: Unknown encoding cl100k_base.`
- `Plugins found: []`
- `tiktoken version: 0.14.0`

Diagnosis: tiktoken registers OpenAI encodings through a dynamically discovered extension module that PyInstaller did not infer automatically.

Repair:

- add hidden imports for `tiktoken_ext` and `tiktoken_ext.openai_public`; and
- lock those requirements into the source-level Windows packaging regression contract.

### Failure 4 — verifier counted dependency registries as TokenTotals registries

Windows package run:

- run: `35045779558`
- head commit: `b85b164d652f283b864484d86e39e2a1367a625c`

This run is important positive evidence even though the overall workflow was red. The packaged executable itself completed the entire phase trace successfully:

- `entry`
- PIL import
- all four icon files
- pricing imports
- `openai_registry_ok`
- `anthropic_registry_ok`
- `google_registry_ok`
- `proxy_import_start`
- `proxy_imported`
- `proxy_routes_ok`
- `complete`

The subsequent post-build verifier failed because it recursively counted every `*_registry.json` in the enlarged bundle and found five instead of the assumed three. Bundling LiteLLM correctly had introduced additional dependency registry files, invalidating the wildcard-count assumption.

Repair:

- stop asserting that the whole package contains exactly three files matching `*_registry.json`; and
- require the three TokenTotals registry files by exact name: `openai_registry.json`, `anthropic_registry.json`, and `google_registry.json`.

## Final Windows acceptance

End-to-end green Windows package run:

- workflow: `TokenTotals Windows Package Smoke`
- run: **`35046049359`**
- job: **`104635972189`**
- head commit: **`5d0cd7f5f246a15a6d8f10e0190151e607d9e457`**
- conclusion: **success**

Every release-candidate package gate passed:

1. Checkout — passed.
2. Python 3.12 setup — passed.
3. Build and smoke-test packaged desktop — passed.
4. Verify packaged files — passed.
5. Create candidate ZIP — passed.
6. Upload smoke-tested candidate — passed.

The successful packaged smoke proves that the built executable can enter the package smoke path and, in that packaged environment, load the required icon assets, load the three TokenTotals pricing registries, initialize enough of the bundled LiteLLM/tiktoken runtime for `proxy_server` to import, and verify the expected localhost proxy/dashboard/API routes.

## Candidate artifact evidence — original record, superseded

**Superseded by the post-closeout artifact-identity reconciliation above. The values in this historical block must not be used as the current candidate identity.**

Uploaded GitHub Actions artifact as originally recorded:

- name: **`TokenTotals-Windows-candidate`**
- artifact ID: **`6151997384`**
- size: **`92,753,806 bytes`**
- SHA-256: **`1f672af62f047f2a2952d5cd7e7d362d271c42c770557040f028e48ea928f33b`**
- source workflow run: **`35046049359`**
- source head SHA: **`5d0cd7f5f246a15a6d8f10e0190151e607d9e457`**
- artifact state when checked: not expired

This block is retained to show what was originally recorded and later corrected; it is not current release evidence.

## Packaging regressions now locked in source

The repository now carries automated checks that require:

- the packaged smoke branch to run before desktop UI imports;
- deterministic smoke exit behavior;
- a 90-second external smoke watchdog;
- phase-trace output on smoke failure;
- bundled LiteLLM runtime data;
- bundled tiktoken OpenAI encoding plugin support;
- exact presence of all three TokenTotals pricing registry files;
- the Windows packaging workflow to include the package-smoke source in its path trigger; and
- release identity metadata changes in `CITATION.cff` to trigger Windows package proof.

These checks convert the discovered packaging failures into permanent regression coverage rather than one-off CI fixes.

## What this receipt does not prove

This evidence does **not** claim or prove:

- invoice-exact provider billing;
- a provider account balance, credit balance, spending allowance, or safe amount remaining;
- account entitlement to every model represented in a pricing registry;
- live provider API connectivity for every provider/account/key combination;
- that direct provider calls made outside TokenTotals are blocked;
- multi-process/distributed atomicity beyond the documented single local daemon boundary;
- Windows code signing, Microsoft SmartScreen reputation, MSI/MSIX/installer behavior, or store distribution;
- universal compatibility with every Windows machine/configuration; or
- macOS/Linux desktop packaging support.

The provider invoice/account record remains authoritative. TokenTotals records and derives local estimates/telemetry from the information legitimately available to it.

## Release-candidate verdict

The Windows desktop release-candidate path is **verified end to end in GitHub Actions**: package build, packaged-runtime smoke, required-file verification, candidate identity recording, ZIP creation, artifact upload, and separate Actions artifact identity recording all pass.

The launch-critical engineering/proof roadmap is closed for the release candidate. Public tagging/publication remains a separate deliberate release action.

## Final documentation-closeout CI

The receipt plus roadmap closeout were checked on a clean GitHub Actions runner:

- workflow: `TokenTotals Regression Tests`
- run: **`35046663526`**
- job: **`104637843227`**
- head commit: **`d2b5ffe4df21797d92edfb2c4337ea9d7aa4c0b1`**
- dependency install: passed
- source compilation: passed
- clean `proxy_server` smoke import: passed
- regression result: **176/176 tests passed**
- unittest timing: `Ran 176 tests in 0.779s` — `OK`
- overall job conclusion: **success**

A later artifact-identity reconciliation is documented above and supersedes the original candidate-artifact identity block. The release-metadata reconciliation commit that incorporates this correction must itself pass the normal regression and Windows package gates before it is selected for public tagging.
