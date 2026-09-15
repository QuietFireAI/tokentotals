from pathlib import Path
import re

import runtime_compat


ROOT = Path(__file__).resolve().parents[1]


def _requirement_name(line: str) -> str | None:
    line = line.strip()
    if not line or line.startswith("#") or line.startswith("-r "):
        return None
    line = line.split(";", 1)[0].strip()
    name = re.split(r"[<>=!~\[]", line, maxsplit=1)[0].strip()
    return name.lower().replace("_", "-") if name else None


def test_runtime_requirements_are_covered_by_constraints():
    requirements = {
        name
        for line in (ROOT / "requirements.txt").read_text(encoding="utf-8-sig").splitlines()
        if (name := _requirement_name(line))
    }
    constraints = {
        name
        for line in (ROOT / "constraints-py312.txt").read_text(encoding="utf-8-sig").splitlines()
        if (name := _requirement_name(line))
    }

    assert requirements <= constraints
    assert "pytest" in constraints
    assert "pyinstaller" in constraints


def test_ci_uses_clean_constrained_environments_on_linux_and_windows():
    workflow = (ROOT / ".github" / "workflows" / "tests.yml").read_text(encoding="utf-8-sig")

    assert "runtime-smoke-linux:" in workflow
    assert "runtime-smoke-windows:" in workflow
    assert "build-tool-smoke-windows:" in workflow
    assert workflow.count("python -m venv .venv") >= 4
    assert workflow.count("constraints-py312.txt") >= 4


def test_python_runtime_contract_is_daily_and_consistent():
    workflow = (ROOT / ".github" / "workflows" / "tests.yml").read_text(encoding="utf-8-sig")
    build = (ROOT / "build.ps1").read_text(encoding="utf-8-sig")

    assert runtime_compat.SUPPORTED_PYTHON == (3, 12)
    assert "cron: '17 09 * * *'" in workflow
    assert workflow.count("python-version: '3.12'") >= 4
    assert workflow.count("runtime_compat.py") >= 4
    assert 'Trim() -ne "3.12"' in build


def test_windows_build_is_python312_and_constraint_bound():
    build = (ROOT / "build.ps1").read_text(encoding="utf-8-sig")

    assert 'Trim() -ne "3.12"' in build
    assert "pip install -c constraints-py312.txt -r requirements.txt pyinstaller" in build
    assert "python -m pip check" in build
    assert "python -m PyInstaller" in build
