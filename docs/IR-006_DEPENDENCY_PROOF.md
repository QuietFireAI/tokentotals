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

The GitHub Actions `tests` workflow now contains a separate `runtime-smoke` job that does **not** install `requirements-dev.txt` or pytest.

On a fresh Ubuntu / Python 3.12 runner it performs:

```text
python -m pip install -r requirements.txt
python -m pip check
```

It then imports both `litellm` and the production `proxy_server`, verifies that `proxy_server.litellm` is the same installed module, verifies that `litellm.acompletion` is callable, and reports the installed LiteLLM package version.

### 2026-09-15 result

- runtime requirements installation: **PASS**
- `pip check`: **PASS** — `No broken requirements found.`
- LiteLLM installed from `requirements.txt`: **PASS**
- resolved LiteLLM version in that run: **1.101.0**
- production `proxy_server` import: **PASS**
- identity check (`proxy_server.litellm is litellm`): **PASS**
- normal regression suite on the same branch revision: **PASS**

This proves the repaired runtime dependency declaration works in a fresh environment independently of the development/test dependency set.

## Packaging path

`build.ps1` installs `requirements.txt` before invoking PyInstaller, so the Windows build path consumes the same declared runtime dependency list rather than a developer-private dependency directory.

This is evidence about dependency declaration and installation. It is **not** a claim that the final Windows executable has completed release-level packaging validation on every supported machine.

## Separate follow-up risk: dependency reproducibility

The current `requirements.txt` entries are unpinned, and this revision does not contain a lock or constraints file.

That does **not** reopen IR-006: the required dependency is now declared and clean-installable. It does mean that installs performed on different dates can resolve different package versions and transitive dependency graphs.

Treat reproducible dependency locking / constraints as a separate hardening item rather than calling IR-006 incomplete.

## Verdict

**IR-006 — PASS: REPAIRED AND REVALIDATED.**

The original missing-runtime-dependency defect is removed, the real package is exercised in clean CI, and a runtime-only smoke job now makes the dependency invariant independently testable.