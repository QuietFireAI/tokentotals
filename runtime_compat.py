"""TokenTotals runtime compatibility contract.

TokenTotals is currently validated and dependency-constrained for CPython 3.12.x.
Fail early with a useful message instead of allowing a later dependency/import error.
"""

from __future__ import annotations

import sys

SUPPORTED_PYTHON = (3, 12)


def require_supported_python() -> None:
    current = sys.version_info[:2]
    if current != SUPPORTED_PYTHON:
        supported = ".".join(map(str, SUPPORTED_PYTHON))
        detected = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        raise RuntimeError(
            "TokenTotals runtime compatibility check failed: "
            f"validated Python is {supported}.x; detected Python {detected}. "
            "Use CPython 3.12 and install dependencies through constraints-py312.txt."
        )
