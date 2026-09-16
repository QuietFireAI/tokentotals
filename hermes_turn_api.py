"""Local API surface used by the TokenTotals Hermes observer plugin."""

from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse

import hermes_evidence_store
import hermes_turn_ingest
import turn_receipt
import turn_receipt_terminal

router = APIRouter()


@router.post("/api/hermes/turn")
async def post_hermes_turn(payload: dict):
    try:
        result = hermes_turn_ingest.ingest_hermes_turn(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    receipt = turn_receipt.by_id(result["turn_id"])
    if receipt is None:
        raise HTTPException(status_code=500, detail="Hermes turn settled but receipt was not found")
    evidence = hermes_evidence_store.read(result["turn_id"])
    return {
        **result,
        "receipt_id": receipt["receipt_id"],
        "receipt_text_standard": turn_receipt_terminal.render_text(receipt, "standard", evidence=evidence),
        "receipt_text_expanded": turn_receipt_terminal.render_text(receipt, "expanded", evidence=evidence),
    }


@router.get("/api/hermes/turn/{receipt_id}/receipt.txt", response_class=PlainTextResponse)
async def get_hermes_receipt_text(receipt_id: str, mode: str = "standard"):
    try:
        receipt = turn_receipt.by_id(receipt_id)
        if receipt is None:
            raise HTTPException(status_code=404, detail="receipt not found")
        evidence = hermes_evidence_store.read(receipt_id)
        return turn_receipt_terminal.render_text(receipt, mode, evidence=evidence)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/api/hermes/turn/{receipt_id}/evidence")
async def get_hermes_evidence(receipt_id: str):
    evidence = hermes_evidence_store.read(receipt_id)
    if evidence is None:
        raise HTTPException(status_code=404, detail="Hermes evidence not found")
    return evidence
