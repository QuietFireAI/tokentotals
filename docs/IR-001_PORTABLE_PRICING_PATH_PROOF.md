# IR-001 Portable Pricing Path Proof

**Finding:** IR-001 — Developer-machine pricing path  
**Verdict:** CONFIRMED DEFECT / REPAIRED AND REVALIDATED  
**Proof revision:** 2026-09-15

## What was wrong

The baseline runtime inserted a developer-specific path into `sys.path`:

```text
C:\Users\Command Center\.gemini\config\plugins\token-cost-estimator\scripts
```

The baseline Windows build script repeated the same external directory through its PyInstaller path configuration.

That meant a clean installation was not guaranteed to use the same pricing implementation as the developer workstation. A local private plugin could materially affect runtime behavior while being absent from the repository being reviewed.

## Actual repair

The hardened runtime uses the checked-in repository pricing implementation directly:

- `pricing_engine.py` defines `CATALOG_PATH = Path(__file__).with_name("pricing_catalog.json")`;
- `proxy_server.py` imports `resolve_model`, `calculate_cost`, and `estimate_text_tokens` from that repository module;
- the Windows build no longer uses a PyInstaller `--paths` escape to a developer directory;
- `build.ps1` explicitly bundles `pricing_catalog.json` with `--add-data "pricing_catalog.json;."`.

The separately promoted OpenAI verified snapshot remains an intentional user-local data overlay under `~/.tokentotals/pricing/`; it is pricing data produced by the documented validation path, not executable code imported from a developer machine.

No production-code change was required during this sequential IR-001 pass because the earlier hardening had already removed the external plugin path. This pass supplied permanent regression evidence.

## Regression proof

`tests/test_ir001_portable_pricing_path.py` enforces three boundaries.

1. **No developer-machine pricing dependency.** `proxy_server.py` and `build.ps1` must not contain the baseline `C:\Users\Command Center`, `.gemini/.../token-cost-estimator`, or equivalent plugin-script path, and the build may not reintroduce PyInstaller `--paths` to reach external code.
2. **Repository pricing identity.** `pricing_engine.CATALOG_PATH` must resolve to this repository's `pricing_catalog.json`, the catalog must load a real model map, and the production proxy must use the same imported pricing functions from `pricing_engine`.
3. **Portable build data.** The Windows build must package the repository's `pricing_catalog.json` rather than relying on an external developer plugin directory.

The historical baseline remains preserved in Git history, where the old absolute path can still be inspected as evidence of the original defect. The regression applies to the hardened runtime/build surfaces, not to historical commits or forensic documentation quoting the old path.

## Revalidation result

GitHub Actions run `34998467570` on branch head `5eb87d9bdd01c57340dcf6718750e1c96324e588` passed:

- **79/79** regression/integration tests on Ubuntu / CPython 3.12.14;
- constrained Linux runtime smoke;
- constrained Windows runtime smoke;
- constrained Windows PyInstaller/build-tool smoke;
- `pip check` in the validated environments.

The run therefore exercised the repository-local pricing implementation in clean CI environments that do not depend on the original developer path.

## Remaining boundary

Repository-local code does not mean all pricing data is immutable or compiled into the executable. TokenTotals intentionally supports a documented verified OpenAI pricing-data overlay under the user's TokenTotals data directory. That overlay is accepted only through the pricing validation/promotion rules covered by IR-003; it is not an arbitrary Python module or external executable code path.

IR-001 proves removal of the baseline developer-machine executable pricing dependency. It does not claim that a user with local filesystem privileges cannot deliberately alter their own installation or data files.
