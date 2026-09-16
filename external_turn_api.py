"""FastAPI router for same-turn evidence supplied by supported external surfaces."""

from fastapi import APIRouter, HTTPException

import external_turn_ingest
import turn_receipt

router = APIRouter()


@router.post("/api/external-turn")
async def post_external_turn(payload: dict):
    try:
        result = external_turn_ingest.ingest_external_turn(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    receipt = turn_receipt.by_id(result["turn_id"])
    if receipt is None:
        raise HTTPException(status_code=500, detail="external turn settled but receipt was not found")

    return {
        **result,
        "receipt_id": receipt["receipt_id"],
        "render_standard": f"/api/turn-receipt/{receipt['receipt_id']}/render?mode=standard",
        "render_expanded": f"/api/turn-receipt/{receipt['receipt_id']}/render?mode=expanded",
    }
