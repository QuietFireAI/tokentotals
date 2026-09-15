# IR-018 GUI Platform Scope Proof

**Finding:** IR-018 — Cross-platform badge overstated GUI support  
**Verdict:** UNSUPPORTED CLAIM / REPAIRED AND REVALIDATED  
**Proof revision:** 2026-09-15

## What was wrong

The baseline README advertised a platform badge for **Windows | macOS | Linux**.

The reviewed desktop implementation did not support that claim. `app_gui.py` imports the Windows-only `winsound` module and uses `os.startfile()`, while the supplied packaging path is `build.ps1` with the Windows-oriented PyInstaller flow.

The Python proxy and the packaged GUI are separate portability questions. Evidence that the proxy can run in constrained Linux CI does not prove that the tray/Tk desktop application is packaged, tested, or release-supported on macOS or Linux.

## Why it mattered

A broad platform badge can reasonably be read as a statement that the user-facing desktop product is supported on all listed operating systems. That exceeded the packaging and GUI evidence in the repository.

## Actual repair

The hardened README removes the cross-platform platform badge and states the narrower boundary:

> The packaged GUI/build path in this repository is currently Windows-oriented. The Python proxy may be portable, but macOS/Linux GUI packaging is not release-tested here.

This preserves the distinction between source-level proxy portability and release-tested desktop support.

No fake macOS/Linux installer, compatibility shim, or untested platform claim was added merely to retain the baseline badge.

## Regression proof

`tests/test_public_claim_integrity.py::test_gui_platform_claim_matches_current_windows_oriented_implementation` now:

- rejects the baseline Windows/macOS/Linux badge form and equivalent broad GUI claims;
- requires the README's explicit Windows-oriented GUI/build statement;
- requires the separate proxy-portability caveat;
- checks the current implementation evidence that establishes the boundary: `import winsound`, `os.startfile`, and the supplied PyInstaller PowerShell build path.

The implementation-evidence assertions are deliberately changeable if real cross-platform GUI work is later completed. A future macOS/Linux release claim should replace this guard together with platform-specific packaging and CI evidence rather than simply deleting the caveat.

## Revalidation target

This regression is executed in the complete forensic suite together with the constrained Linux runtime, Windows runtime, and Windows build-tool checks. IR-018 does not require removal of the Windows GUI; it requires the public support claim to match what is actually packaged and tested.

## Remaining boundary

The existing Linux runtime smoke and loopback tests are evidence for the Python proxy/runtime path, not for a Linux desktop tray build. No macOS GUI/package test exists in this revision.

A future cross-platform desktop claim requires real platform-specific execution/package evidence for the GUI, not inference from the portability of FastAPI or Python source alone.
