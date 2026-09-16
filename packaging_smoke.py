"""Packaged Windows runtime smoke checks with phase tracing.

This module deliberately stays lightweight at import time. Heavy/runtime imports are
performed inside ``run_packaging_smoke_test`` so a packaged smoke run can identify
exactly which phase stalls or fails without starting the tray UI or local server.
"""

import os
import sys
from pathlib import Path


TRACE_FILE_NAME = "packaging-smoke-trace.txt"


def _trace_path() -> Path:
    return Path.cwd() / TRACE_FILE_NAME


def _trace(stage: str) -> None:
    path = _trace_path()
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"{stage}\n")
        handle.flush()
        try:
            os.fsync(handle.fileno())
        except OSError:
            pass


def _resource_path(relative_path: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path.cwd()))
    return base / relative_path


def run_packaging_smoke_test() -> None:
    """Validate bundled assets, provider registries, FastAPI routes, and Hermes modules."""
    try:
        _trace("entry")

        _trace("pil_import_start")
        from PIL import Image
        _trace("pil_imported")

        for name in ("icon.png", "icon_green.png", "icon_yellow.png", "icon_red.png"):
            _trace(f"icon_start:{name}")
            path = _resource_path(name)
            if not path.exists():
                raise RuntimeError(f"Bundled tray icon is unavailable: {name}")
            with Image.open(path) as image:
                image.verify()
            _trace(f"icon_ok:{name}")

        _trace("pricing_import_start")
        from anthropic_pricing import resolve_anthropic_model
        from google_pricing import resolve_google_model
        from openai_pricing import resolve_openai_model
        _trace("pricing_imported")

        if resolve_openai_model("gpt-5.6-sol") is None:
            raise RuntimeError("Bundled OpenAI pricing registry is unavailable")
        _trace("openai_registry_ok")

        if resolve_anthropic_model("claude-sonnet-5") is None:
            raise RuntimeError("Bundled Anthropic pricing registry is unavailable")
        _trace("anthropic_registry_ok")

        if resolve_google_model("gemini-2.5-flash") is None:
            raise RuntimeError("Bundled Google pricing registry is unavailable")
        _trace("google_registry_ok")

        _trace("proxy_import_start")
        from proxy_server import app
        _trace("proxy_imported")

        routes = {getattr(route, "path", None) for route in app.routes}
        for required in (
            "/dashboard",
            "/chat",
            "/api/status",
            "/api/telemetry/thread",
            "/api/turn-receipt",
            "/api/turn-receipt/{turn_id}",
            "/api/turn-receipt/{turn_id}/render",
        ):
            if required not in routes:
                raise RuntimeError(f"Packaged FastAPI route missing: {required}")
        _trace("proxy_routes_ok")
        _trace("turn_receipt_surfaces_ok")

        _trace("hermes_import_start")
        import hermes_evidence_store
        import hermes_turn_ingest
        import turn_receipt_terminal
        from hermes_turn_api import router as hermes_router
        _ = (hermes_evidence_store, hermes_turn_ingest, turn_receipt_terminal)
        hermes_routes = {getattr(route, "path", None) for route in hermes_router.routes}
        for required in (
            "/api/hermes/turn",
            "/api/hermes/turn/{receipt_id}/receipt.txt",
            "/api/hermes/turn/{receipt_id}/evidence",
        ):
            if required not in hermes_routes:
                raise RuntimeError(f"Packaged Hermes route missing: {required}")
        _trace("hermes_routes_ok")
        _trace("complete")
    except BaseException as exc:
        try:
            _trace(f"error:{type(exc).__name__}:{exc}")
        finally:
            raise
