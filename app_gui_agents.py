"""Desktop entrypoint for the TokenTotals agent-host launch candidate.

Loads the common TokenTotals desktop runtime plus both first-class launch-host
routers: Hermes and OpenClaw.
"""

import app_gui
from hermes_turn_api import router as hermes_turn_router
from openclaw_turn_api import router as openclaw_turn_router

app_gui.app.include_router(hermes_turn_router)
app_gui.app.include_router(openclaw_turn_router)

if __name__ == "__main__":
    app_gui.main()
