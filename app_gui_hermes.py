"""Desktop entrypoint for the TokenTotals Hermes integration candidate."""

import app_gui
from hermes_turn_api import router as hermes_turn_router

app_gui.app.include_router(hermes_turn_router)

if __name__ == "__main__":
    app_gui.main()
