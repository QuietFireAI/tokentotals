"""Local API used by the TokenTotals OpenClaw plugin."""

from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse

import openclaw_evidence_store
import openclaw_turn_ingest
import turn_receipt
import turn_receipt_terminal

router = APIRouter()


@router.post("/api/openclaw/turn")
async def post_openclaw_turn(payload: dict):
    try:
        result = openclaw_turn_ingest.ingest_openclaw_turn(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    receipt = turn_receipt.by_id(result["turn_id"])
    if receipt is None:
        raise HTTPException(status_code=500, detail="OpenClaw turn settled but receipt was not found")
    evidence = openclaw_evidence_store.read(result["turn_id"])
    return {
        **result,
        "receipt_id": receipt["receipt_id"],
        "receipt_text_standard": turn_receipt_terminal.render_text(receipt, "standard", evidence=evidence),
        "receipt_text_expanded": turn_receipt_terminal.render_text(receipt, "expanded", evidence=evidence),
    }


@router.get("/api/openclaw/turn/{receipt_id}/receipt.txt", response_class=PlainTextResponse)
async def get_openclaw_receipt_text(receipt_id: str, mode: str = "standard"):
    try:
        receipt = turn_receipt.by_id(receipt_id)
        if receipt is None:
            raise HTTPException(status_code=404, detail="receipt not found")
        evidence = openclaw_evidence_store.read(receipt_id)
        return turn_receipt_terminal.render_text(receipt, mode, evidence=evidence)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/api/openclaw/turn/{receipt_id}/evidence")
async def get_openclaw_evidence(receipt_id: str):
    evidence = openclaw_evidence_store.read(receipt_id)
    if evidence is None:
        raise HTTPException(status_code=404, detail="OpenClaw evidence not found")
    return evidence
