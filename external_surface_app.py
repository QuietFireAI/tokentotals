"""FastAPI application wiring for external Turn Receipt surfaces.

Keeps the existing proxy_server application intact and adds only the external-turn
router required by browser/host adapters.
"""

from proxy_server import app
from external_turn_ingest import router as external_turn_router


app.include_router(external_turn_router)
