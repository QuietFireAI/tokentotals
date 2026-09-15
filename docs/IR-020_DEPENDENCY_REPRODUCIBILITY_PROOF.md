# IR-020 Dependency Reproducibility Proof

**Finding:** Clean installs were dependency-complete but not version-reproducible across dates  
**Classification:** HARDENING DEFECT / REPAIRED AND REVALIDATED  
**Repair branch:** `sol/forensic-hardening`  
**Revalidation date:** 2026-09-15

## Diagnosis

IR-006 proved that the required runtime dependency (`litellm`) was declared and clean-installable. A separate reproducibility gap remained: `requirements.txt` and the Windows PyInstaller build installed unconstrained package versions, so a clean install performed later could resolve a different transitive dependency graph.

The first measurement pass intentionally resolved the runtime graph on both Ubuntu/Python 3.12 and Windows/Python 3.12. The Windows runner also exposed packages already present in the hosted image. Those runner-image packages were not automatically treated as TokenTotals dependencies; the repair instead uses clean virtual environments so the validated graph is determined by TokenTotals requirements and their dependency closure.

A separate Windows build measurement captured the PyInstaller toolchain as well.

## Repair

`constraints-py312.txt` now pins the validated CPython 3.12 dependency graph used by runtime, tests, and packaging.

Platform-specific dependencies use environment markers where the measured graph genuinely differs, including Windows-only packaging/color support and Linux `python-xlib` support.

The Windows packaging toolchain is constrained as well, including PyInstaller 6.22.3 and its measured supporting packages.

`build.ps1` now:

1. refuses to build under a Python major/minor other than 3.12;
2. installs runtime and PyInstaller dependencies through `constraints-py312.txt`;
3. runs `pip check`; and
4. invokes PyInstaller through the validated Python interpreter.

The GitHub Actions test workflow now creates fresh virtual environments instead of relying on packages preinstalled in hosted runners. Runtime smoke jobs run on both Ubuntu and Windows, and a separate Windows build-tool smoke job verifies the constrained PyInstaller graph.

## Daily Python compatibility watch

Python-version mismatch is treated as part of the reproducibility contract.

`runtime_compat.py` defines the currently validated interpreter contract as CPython 3.12.x and exits with a clear compatibility error on another major/minor version.

The CI workflow executes that checker in every clean environment and contains a daily schedule. Once the hardening branch is merged to the repository default branch, GitHub Actions will run the same clean Linux/Windows runtime and Windows build checks daily. Pushes and pull requests exercise the checker immediately before merge.

Regression tests also require the workflow, build script, and compatibility contract to agree on Python 3.12 so one cannot silently drift away from the others.

## Revalidation evidence

On the final IR-020 branch revision:

- clean Ubuntu/Python 3.12 runtime venv: **PASS**;
- Python compatibility check: **PASS** (`CPython 3.12.14` in the final Ubuntu regression run);
- constrained runtime install + `pip check`: **PASS**;
- production `proxy_server` import in clean Linux environment: **PASS**;
- clean Windows/Python 3.12 runtime venv: **PASS**;
- constrained Windows runtime install + `pip check`: **PASS**;
- production `proxy_server` import in clean Windows environment: **PASS**;
- clean Windows build-tool venv: **PASS**;
- constrained PyInstaller toolchain check: **PASS**;
- focused regression suite: **33 passed / 0 failed**.

During implementation, the first scheduled/constrained workflow revision failed before jobs were created because a Windows inline command made the YAML invalid. That was a workflow-harness defect, not a dependency-resolution failure. The YAML was corrected without weakening or changing the dependency constraints, and the final four-job proof then passed.

A full-file integrity check also caught an over-broad intermediate edit to `proxy_server.py`; that file was restored byte-for-byte to its pre-change hardened blob before final validation. The reproducibility repair therefore does not depend on unrelated proxy rewrites.

## Boundary

This is a **version-reproducible dependency graph for the validated CPython 3.12 environments**. It is not a cryptographic supply-chain guarantee: package hashes are not pinned in this revision, and external package repositories remain part of the installation trust chain.

Deliberate dependency upgrades should update `constraints-py312.txt` and pass the Linux runtime, Windows runtime, Windows build-tool, and regression jobs before promotion.

## Verdict

**IR-020 — PASS: REPAIRED AND REVALIDATED.**

TokenTotals now has an explicit Python 3.12 compatibility contract, a constrained cross-platform dependency graph, constrained Windows packaging dependencies, clean-environment CI proof, and a daily compatibility/drift watch.