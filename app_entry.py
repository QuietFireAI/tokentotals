import os
import sys

# Desktop entrypoint for the external-surface candidate. Keep package smoke
# headless, but explicitly import the new module so missing bundled dependencies
# fail before a candidate is handed to a user.
if "--smoke-test" in sys.argv:
    from packaging_smoke import run_packaging_smoke_test
    from external_turn_api import build_external_record

    try:
        run_packaging_smoke_test()
        probe = build_external_record({
            "surface": "gemini_web",
            "external_turn_id": "packaging-smoke-turn",
            "external_thread_id": "packaging-smoke-thread",
            "model_id": "gemini-2.5-flash",
            "visible_input_text": "hello",
            "visible_output_text": "world",
        })
        if not probe.get("turn_id") or probe.get("estimated_cost_usd") is not None:
            raise RuntimeError("External-turn packaging contract failed")
        import google.auth  # noqa: F401 - packaged Gemini runtime proof
    except BaseException:
        os._exit(1)
    os._exit(0)

from proxy_server import app
from external_turn_api import register_external_turn_routes

register_external_turn_routes(app)

from app_gui import main

if __name__ == "__main__":
    main()
