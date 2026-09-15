# IR-006 Dependency Integrity Proof

**Finding:** Clean install omitted required dependency  
**Classification:** CONFIRMED DEFECT / REPAIRED AND REVALIDATED  
**Repair branch:** `sol/forensic-hardening`  
**Revalidation date:** 2026-09-15

## Baseline defect

Baseline `main` imported `litellm` from `proxy_server.py`, but baseline `requirements.txt` did not declare `litellm`.

That meant a clean installation could satisfy the published requirements and still fail when the production proxy attempted to import its upstream routing dependency.

## Repair

The hardened branch declares `litellm` in `requirements.txt`.

`requirements-dev.txt` includes the runtime requirements with:

```text
-r requirements.txt
pytest
```

This prevents the test dependency set from becoming a separate shadow list that can silently omit a production dependency.

`proxy_server.py` also fails explicitly if LiteLLM is unavailable:

```python
try:
    import litellm
except ImportError as exc:
    raise RuntimeError(
        "TokenTotals requires LiteLLM. Install dependencies with: pip install -r requirements.txt"
    ) from exc
```

There is no fake or generic routing fallback in that import path.

## Test-harness integrity

`tests/test_proxy_guardrails.py` imports the installed `litellm` package directly and verifies:

```python
assert proxy_server.litellm is litellm
assert callable(litellm.acompletion)
assert getattr(litellm, "__file__", None)
```

The test suite no longer injects a fake `litellm` module that could make a missing runtime dependency appear healthy.

## Dedicated runtime-only clean-install proof

The GitHub Actions workflow now performs clean runtime smoke checks independently of the pytest dependency set. Each smoke job creates a fresh virtual environment, installs the declared runtime requirements through the validated Python 3.12 constraints, runs `pip check`, imports both `litellm` and the production `proxy_server`, and verifies that `proxy_server.litellm` is the installed LiteLLM module.

The runtime-only proof now runs on both Ubuntu and Windows.

### 2026-09-15 result

- clean runtime requirements installation: **PASS** on Ubuntu and Windows;
- `pip check`: **PASS**;
- LiteLLM installed from the declared runtime requirements: **PASS**;
- constrained LiteLLM version: **1.101.0**;
- production `proxy_server` import: **PASS** on Ubuntu and Windows;
- identity check (`proxy_server.litellm is litellm`): **PASS**;
- normal constrained regression suite on the final IR-020 revision: **33 passed / 0 failed**.

This proves the repaired runtime dependency declaration works in fresh environments independently of the development/test dependency set.

## Packaging path

`build.ps1` consumes the same declared runtime dependency list and the validated Python 3.12 constraints before invoking PyInstaller. The Windows build-tool smoke job separately verifies the constrained packaging dependency graph.

This is evidence about dependency declaration, constrained installation, and the packaging dependency path. It is **not** a claim that the final Windows executable has completed release-level packaging validation on every supported machine.

## Reproducibility follow-up resolved separately

The unpinned-dependency limitation originally recorded during IR-006 was kept separate from the missing-dependency defect. It is now tracked and repaired as **IR-020 — dependency reproducibility**.

See [`IR-020_DEPENDENCY_REPRODUCIBILITY_PROOF.md`](IR-020_DEPENDENCY_REPRODUCIBILITY_PROOF.md) for the measured Linux/Windows dependency graph, `constraints-py312.txt`, constrained PyInstaller toolchain, clean-venv proof, Python 3.12 compatibility contract, and daily runtime-version/dependency-drift watch.

IR-020 provides version reproducibility for the validated dependency graph; it does not claim cryptographic package-artifact/hash pinning.

## Verdict

**IR-006 — PASS: REPAIRED AND REVALIDATED.**

The original missing-runtime-dependency defect is removed, the real package is exercised in clean CI, and clean runtime smoke jobs make the dependency invariant independently testable on both Linux and Windows.