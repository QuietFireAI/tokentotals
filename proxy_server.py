import json
import os
import sys
from typing import Any

if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse

try:
    import litellm
except ImportError as exc:
    raise RuntimeError(
        "TokenTotals requires LiteLLM. Install dependencies with: pip install -r requirements.txt"
    ) from exc

import config_manager
from pricing_engine import (
    UnknownModelPrice,
    affordable_output_tokens,
    calculate_cost,
    estimate_text_tokens,
    list_models as pricing_models,
    load_catalog,
    resolve_model,
)

app = FastAPI(title="TokenTotals by QuietFireAI")
litellm.suppress_debug_info = True
LAST_LATENCY_MS = 0


def _usage_value(usage: Any, *names: str) -> int:
    if usage is None:
        return 0
    for name in names:
        if isinstance(usage, dict) and name in usage:
            try:
                return int(usage.get(name) or 0)
            except Exception:
                continue
        value = getattr(usage, name, None)
        if value is not None:
            try:
                return int(value or 0)
            except Exception:
                continue
    return 0


def _usage_from_response(response: Any):
    usage = getattr(response, "usage", None)
    if usage is None and isinstance(response, dict):
        usage = response.get("usage")
    input_tokens = _usage_value(usage, "prompt_tokens", "input_tokens")
    output_tokens = _usage_value(usage, "completion_tokens", "output_tokens")
    if input_tokens or output_tokens:
        return input_tokens, output_tokens
    return None


def _economy_model_for(provider: str) -> str | None:
    return {
        "OpenAI": "gpt-5.6-luna",
        "Anthropic": "claude-haiku-4.5",
        "Google": "gemini-3.1-flash-lite",
    }.get(provider)


def _require_ack(payload: dict, expected: str, field: str = "acknowledgement"):
    value = str(payload.get(field, "")).strip().upper()
    if value != expected.upper():
        raise HTTPException(status_code=400, detail=f"Type exactly '{expected}' to continue.")


def _requested_output_bound(payload: dict) -> int | None:
    """Return the largest caller-supplied output ceiling.

    Clients/providers use both max_tokens and max_completion_tokens. If both are
    present, reserving against the smaller one can under-reserve if a downstream path
    honors the larger field, so the budget gate always uses the largest valid bound.
    """
    bounds = []
    for field in ("max_tokens", "max_completion_tokens"):
        value = payload.get(field)
        if value is None:
            continue
        try:
            parsed = int(value)
        except Exception:
            raise HTTPException(status_code=400, detail=f"{field} must be an integer")
        if parsed <= 0:
            raise HTTPException(status_code=400, detail=f"{field} must be positive")
        bounds.append(parsed)
    return max(bounds) if bounds else None


@app.get("/v1/models")
async def list_models():
    data = []
    for model_id, record in pricing_models().items():
        data.append(
            {
                "id": model_id,
                "object": "model",
                "owned_by": str(record.get("provider", "unknown")).lower(),
            }
        )
    return {"object": "list", "data": data}


@app.get("/api/status")
async def get_status():
    conf = config_manager.get_config()
    state = config_manager.get_state()
    limit = float(conf.get("daily_budget_limit_usd", 10.00))
    current = float(state.get("current_spend_usd", 0.00))
    pct = round((current / limit * 100), 1) if limit > 0 else 0
    traffic_light = "GREEN"
    if state.get("is_locked"):
        traffic_light = "RED"
    elif pct >= conf.get("warning_threshold_pct", 75):
        traffic_light = "YELLOW"
    return {
        "status": "LOCKED" if state.get("is_locked") else "ACTIVE",
        "traffic_light": traffic_light,
        "current_spend_usd": current,
        "daily_budget_limit_usd": limit,
        "remaining_budget_usd": max(0.0, round(limit - current, 6)),
        "budget_used_pct": pct,
        "thread_spend_usd": float(state.get("thread_spend_usd", 0.00)),
        "potential_savings_usd": float(state.get("potential_savings_usd", 0.00)),
        "flagged_routine_calls": int(state.get("flagged_routine_calls", 0)),
        "total_requests": int(state.get("total_requests", 0)),
        "unreconciled_streams": int(state.get("unreconciled_streams", 0)),
        "last_latency_ms": LAST_LATENCY_MS,
        "is_locked": bool(state.get("is_locked", False)),
        "auto_economy_mode": bool(conf.get("auto_economy_mode", False)),
        "port": int(conf.get("port", 8080)),
        "pricing_verified_at": load_catalog().get("verified_at"),
    }


@app.post("/api/boost")
async def api_quick_boost(request: Request):
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    _require_ack(payload, "BOOST $5")
    new_limit = config_manager.quick_boost(5.00)
    return {"message": "Budget boosted by $5.00", "new_limit_usd": new_limit, "is_locked": False}


@app.post("/api/unlock")
async def api_unlock(request: Request):
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    _require_ack(payload, "I UNDERSTAND")
    config_manager.unlock_circuit_breaker()
    return {"message": "Circuit breaker unlocked by verified user acknowledgment.", "is_locked": False}


@app.get("/", response_class=HTMLResponse)
@app.get("/dashboard", response_class=HTMLResponse)
@app.get("/dashboard/", response_class=HTMLResponse)
@app.get("/dashboard.html", response_class=HTMLResponse)
async def serve_dashboard():
    return HTMLResponse(content=DASHBOARD_HTML)


@app.post("/v1/chat/completions")
async def proxy_openai(request: Request):
    global LAST_LATENCY_MS
    state = config_manager.get_state()
    conf = config_manager.get_config()
    if state.get("is_locked", False):
        raise HTTPException(status_code=403, detail="QuietFireAI Emergency Shutdown: daily budget gate is locked.")
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="JSON payload must be an object")

    model_id = str(payload.get("model") or "").strip()
    if not model_id:
        raise HTTPException(status_code=400, detail="A model is required")
    try:
        requested_pricing = resolve_model(model_id)
    except UnknownModelPrice as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    thread_id = request.headers.get("x-thread-id") or payload.get("user") or "default"
    messages = payload.get("messages", [])
    prompt_text = json.dumps(messages, ensure_ascii=False, separators=(",", ":"))
    estimated_input_tokens = estimate_text_tokens(prompt_text, model_id)

    word_count = len(prompt_text.split())
    is_lightweight = word_count < 80 or estimated_input_tokens < 300
    provider = requested_pricing.get("provider")
    economy_model = _economy_model_for(provider)
    is_routine = bool(
        is_lightweight
        and economy_model
        and economy_model != requested_pricing.get("canonical_model")
    )

    routed_model = model_id
    pricing = requested_pricing
    if is_routine and conf.get("auto_economy_mode", False) and economy_model:
        routed_model = economy_model
        try:
            pricing = resolve_model(routed_model)
        except UnknownModelPrice as exc:
            raise HTTPException(
                status_code=422,
                detail=(
                    "Auto-economy routing selected a model without verified pricing. "
                    f"No upstream call was sent. {exc}"
                ),
            )
        estimated_input_tokens = estimate_text_tokens(prompt_text, routed_model)

    limit = float(conf.get("daily_budget_limit_usd", 10.00))
    current = float(state.get("current_spend_usd", 0.0))
    remaining = max(0.0, limit - current)
    input_guard = calculate_cost(pricing, estimated_input_tokens, 0, conservative=True)
    remaining_after_input = remaining - input_guard["input_cost_usd"]
    if remaining_after_input <= 0:
        config_manager.set_locked(True)
        raise HTTPException(status_code=403, detail="Circuit breaker: conservative input reservation alone would exceed the remaining daily budget.")

    requested_output = _requested_output_bound(payload)
    if requested_output is None:
        affordable = affordable_output_tokens(pricing, remaining_after_input)
        configured_default = max(1, int(conf.get("default_max_output_tokens", 4096)))
        reserved_output_tokens = min(configured_default, affordable)
        if reserved_output_tokens < 1:
            config_manager.set_locked(True)
            raise HTTPException(status_code=403, detail="Circuit breaker: no output budget remains.")
        payload["max_tokens"] = reserved_output_tokens
    else:
        reserved_output_tokens = requested_output

    reserved = calculate_cost(
        pricing,
        estimated_input_tokens,
        reserved_output_tokens,
        conservative=True,
    )["total_cost_usd"]

    potential_saving = 0.0
    if is_routine and economy_model:
        try:
            econ_pricing = resolve_model(economy_model)
            requested_estimate_tokens = estimate_text_tokens(prompt_text, model_id)
            requested_reserved = calculate_cost(
                requested_pricing,
                requested_estimate_tokens,
                reserved_output_tokens,
                conservative=True,
            )["total_cost_usd"]
            econ_estimate_tokens = estimate_text_tokens(prompt_text, economy_model)
            econ_reserved = calculate_cost(
                econ_pricing,
                econ_estimate_tokens,
                reserved_output_tokens,
                conservative=True,
            )["total_cost_usd"]
            potential_saving = max(0.0, requested_reserved - econ_reserved)
        except UnknownModelPrice:
            potential_saving = 0.0

    accepted, _ = config_manager.try_reserve_spend(
        reserved,
        thread_id=thread_id,
        potential_saving=potential_saving,
        is_routine=is_routine,
    )
    if not accepted:
        raise HTTPException(
            status_code=403,
            detail=(
                f"Circuit breaker: worst-case reservation ${reserved:.6f} for routed model "
                f"'{routed_model}' would exceed the daily budget of ${limit:.2f}. "
                "No upstream call was sent."
            ),
        )

    auth_header = request.headers.get("authorization", "")
    api_key = auth_header.replace("Bearer ", "", 1) if auth_header.startswith("Bearer ") else auth_header
    stream = bool(payload.pop("stream", False))
    messages = payload.pop("messages", [])
    payload.pop("model", None)

    import time
    started = time.perf_counter()
    try:
        response = await litellm.acompletion(
            model=routed_model,
            messages=messages,
            api_key=api_key,
            stream=stream,
            **payload,
        )
    except Exception as exc:
        config_manager.reconcile_reserved_spend(reserved, 0.0, thread_id=thread_id)
        raise HTTPException(status_code=502, detail=f"Upstream Provider Error via LiteLLM: {exc}")
    finally:
        LAST_LATENCY_MS = int((time.perf_counter() - started) * 1000)

    if not stream:
        usage_pair = _usage_from_response(response)
        if usage_pair:
            actual = calculate_cost(
                pricing,
                usage_pair[0],
                usage_pair[1],
                conservative=False,
            )["total_cost_usd"]
            config_manager.reconcile_reserved_spend(reserved, actual, thread_id=thread_id)
        return response.model_dump() if hasattr(response, "model_dump") else response

    async def generate():
        usage_pair = None
        try:
            async for chunk in response:
                candidate = _usage_from_response(chunk)
                if candidate:
                    usage_pair = candidate
                if hasattr(chunk, "model_dump_json"):
                    body = chunk.model_dump_json()
                elif isinstance(chunk, dict):
                    body = json.dumps(chunk)
                else:
                    body = json.dumps({"chunk": str(chunk)})
                yield f"data: {body}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"
        finally:
            if usage_pair:
                actual = calculate_cost(
                    pricing,
                    usage_pair[0],
                    usage_pair[1],
                    conservative=False,
                )["total_cost_usd"]
                config_manager.reconcile_reserved_spend(reserved, actual, thread_id=thread_id)
            else:
                config_manager.mark_unreconciled_stream(1)
            yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><title>TokenTotals by QuietFireAI</title>
<style>:root{--bg:#090a0f;--card:#131620;--border:#23293d;--green:#10b981;--yellow:#f59e0b;--text:#f3f4f6;--sub:#9ca3af}*{box-sizing:border-box;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}body{margin:0;background:var(--bg);color:var(--text);padding:24px}.container{max-width:900px;margin:auto;display:grid;gap:18px}.card{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:20px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:16px}.label{font-size:12px;color:var(--sub);text-transform:uppercase}.value{font-size:28px;font-weight:700;margin-top:5px}.badge{font-size:12px;font-weight:700}.btn{border:0;border-radius:6px;padding:9px 14px;font-weight:700;cursor:pointer;background:var(--green)}.muted{color:var(--sub);font-size:12px}a{color:#60a5fa}</style></head>
<body><div class="container"><div class="card"><div style="display:flex;justify-content:space-between;align-items:center"><h2 style="margin:0">TokenTotals <span class="muted">by QuietFireAI</span></h2><span id="status" class="badge">LOADING</span></div></div>
<div class="card"><div class="label">Estimated / Reserved Spend</div><div class="value"><span id="spend">$0.000000</span> <span class="muted" id="limit">/ $10.00</span></div><div class="muted" id="remaining">Remaining: $10.00</div></div>
<div class="grid"><div class="card"><div class="label">Active Thread Spend</div><div class="value" id="thread">$0.000000</div></div><div class="card"><div class="label">Requests Today</div><div class="value" id="requests">0</div></div><div class="card"><div class="label">Potential Savings (estimate)</div><div class="value" id="savings">$0.000000</div></div><div class="card"><div class="label">Pricing Receipt Date</div><div class="value" style="font-size:20px" id="pricingDate">—</div></div><div class="card"><div class="label">Unreconciled Streams</div><div class="value" id="unreconciled">0</div><div class="muted">Worst-case reservation retained when final usage is unavailable.</div></div><div class="card"><div class="label">Proxy</div><div class="value" style="font-size:20px" id="proxy">127.0.0.1:8080</div><div class="muted">Local listener; upstream provider traffic still leaves this machine.</div></div></div>
<div class="card"><div class="label">Budget Control</div><p class="muted">Quick Boost requires an explicit acknowledgement and raises today's limit by $5.</p><button class="btn" onclick="addBoost()">+ $5 Quick Boost</button></div>
<div class="card"><div class="label">Pricing receipts</div><p><a href="https://developers.openai.com/api/docs/pricing" target="_blank">OpenAI</a> · <a href="https://platform.claude.com/docs/en/about-claude/pricing" target="_blank">Anthropic</a> · <a href="https://cloud.google.com/gemini-enterprise-agent-platform/generative-ai/pricing" target="_blank">Google Cloud</a></p></div></div>
<script>async function refresh(){try{const r=await fetch('/api/status');const d=await r.json();document.getElementById('spend').innerText='$'+d.current_spend_usd.toFixed(6);document.getElementById('limit').innerText='/ $'+d.daily_budget_limit_usd.toFixed(2);document.getElementById('remaining').innerText='Remaining: $'+d.remaining_budget_usd.toFixed(6);document.getElementById('thread').innerText='$'+d.thread_spend_usd.toFixed(6);document.getElementById('requests').innerText=d.total_requests;document.getElementById('savings').innerText='$'+d.potential_savings_usd.toFixed(6);document.getElementById('pricingDate').innerText=d.pricing_verified_at||'UNKNOWN';document.getElementById('unreconciled').innerText=d.unreconciled_streams;document.getElementById('proxy').innerText='127.0.0.1:'+d.port+' | '+d.last_latency_ms+' ms';document.getElementById('status').innerText=d.is_locked?'🔴 LOCKED':(d.traffic_light==='YELLOW'?'🟡 CAUTION':'🟢 IN BUDGET');}catch(e){}}async function addBoost(){const phrase=prompt("Type BOOST $5 to increase today's limit:");if(phrase!=="BOOST $5")return;const r=await fetch('/api/boost',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({acknowledgement:phrase})});if(!r.ok){alert('Boost rejected');}refresh();}setInterval(refresh,2000);refresh();</script></body></html>"""


if __name__ == "__main__":
    import uvicorn
    conf = config_manager.get_config()
    uvicorn.run(app, host="127.0.0.1", port=int(conf.get("port", 8080)))