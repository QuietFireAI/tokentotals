"""Desktop entrypoint with external Turn Receipt surface router enabled."""

import app_gui
from external_turn_api import router as external_turn_router

app_gui.app.include_router(external_turn_router)

if __name__ == "__main__":
    app_gui.main()
