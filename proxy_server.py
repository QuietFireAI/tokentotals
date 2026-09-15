import json
import math
import time
import sys
import os
import uuid

if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse, HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import litellm
import config_manager
import turn_ledger
import telemetry_view
import turn_notice
from openai_pricing import (
    calculate_openai_response_cost,
    estimate_openai_input_cost,
    looks_like_openai_model,
)
from anthropic_pricing import (
    calculate_anthropic_response_cost,
    looks_like_anthropic_model,
    resolve_anthropic_model,
)
from google_pricing import (
    calculate_google_response_cost,
    estimate_google_input_cost,
    infer_google_platform,
    looks_like_google_model,
)
from runtime_model_catalog import registered_model_entries


def estimate_text_tokens(text, model_id):
    """Preflight token estimate using pinned LiteLLM tokenization when available."""
    try:
        count = int(litellm.token_counter(model=model_id, text=text))
        return max(1, count)
    except Exception:
        # Deliberately a local heuristic only. This is not a billing counter.
        return max(1, len(text) // 4)


def litellm_catalog_input_estimate(model_id, estimated_tokens):
    """Exact-key fallback for providers without a TokenTotals provider engine."""
    catalog = getattr(litellm, "model_cost", {}) or {}
    record = catalog.get(model_id)
    if not isinstance(record, dict):
        return None

    rate = record.get("input_cost_per_token")
    if rate is None:
        return None
    try:
        rate = float(rate)
        tokens = max(0, int(estimated_tokens or 0))
    except (TypeError, ValueError):
        return None
    if rate < 0:
        return None
    return tokens * rate


def callback_param(kwargs, key):
    value = kwargs.get(key)
    if value is not None:
        return value
    for container_name in ("litellm_params", "optional_params"):
        container = kwargs.get(container_name) or {}
        if isinstance(container, dict) and container.get(key) is not None:
            return container.get(key)
    return None


def request_service_tier_from_callback(kwargs):
    return callback_param(kwargs, "service_tier")


def google_request_feature_hints_from_callback(kwargs):
    """Recover billable Google server-tool hints even if response normalization drops them."""
    hints = set()
    if callback_param(kwargs, "web_search_options") is not None:
        hints.add("google_search")

    tools = callback_param(kwargs, "tools") or []
    if isinstance(tools, dict):
        tools = [tools]
    for tool in tools:
        if not isinstance(tool, dict):
            continue
        for key in tool:
            normalized = str(key).replace("-", "_").lower()
            if normalized in {"googlesearch", "google_search", "google_search_retrieval"}:
                hints.add("google_search")
            elif normalized in {"googlemaps", "google_maps"}:
                hints.add("google_maps")
            elif normalized in {"urlcontext", "url_context"}:
                hints.add("url_context")
            elif normalized in {"filesearch", "file_search"}:
                hints.add("file_search")
    return sorted(hints)


def anthropic_preflight_input_estimate(model_id, estimated_tokens, payload):
    """Best-effort preflight input estimate; actual spend uses response telemetry."""
    record = resolve_anthropic_model(model_id)
    if not record:
        return None

    speed = str(payload.get("speed") or "standard").lower()
    if speed == "fast":
        rates = record.get("fast_rates")
        if not rates:
            return None
    elif speed == "standard":
        rates = record.get("rates") or {}
    else:
        return None

    base_rate = rates.get("base_input")
    if base_rate is None:
        return None

    geo_multiplier = 1.0
    if record.get("supports_inference_geo"):
        geo = payload.get("inference_geo")
        if geo is not None:
            geo_name = str(geo).lower()
            if geo_name == "us":
                geo_multiplier = float(record.get("inference_geo_us_multiplier") or 1.1)
            elif geo_name != "global":
                return None
        else:
            # Workspace defaults can choose US-only inference. For the circuit
            # breaker, use the highest known first-party geography multiplier so
            # an unresolved default does not silently under-estimate input spend.
            geo_multiplier = max(1.0, float(record.get("inference_geo_us_multiplier") or 1.0))

    return (max(0, estimated_tokens) / 1_000_000.0) * float(base_rate) * geo_multiplier


def preflight_input_estimate(model_id, estimated_tokens, payload):
    """Return (cost, source) without inventing a cross-provider price."""
    if looks_like_openai_model(model_id):
        result = estimate_openai_input_cost(
            model_id,
            estimated_tokens,
            service_tier=payload.get("service_tier"),
        )
        cost = result.get("total_cost_usd")
        return cost, "openai_registry" if cost is not None else "openai_registry_unresolved"

    if looks_like_anthropic_model(model_id):
        cost = anthropic_preflight_input_estimate(model_id, estimated_tokens, payload)
        return cost, "anthropic_registry" if cost is not None else "anthropic_registry_unresolved"

    if looks_like_google_model(model_id):
        result = estimate_google_input_cost(
            model_id,
            estimated_tokens,
            service_tier=payload.get("service_tier"),
        )
        cost = result.get("total_cost_usd")
        return cost, "google_registry" if cost is not None else "google_registry_unresolved"

    fallback = litellm_catalog_input_estimate(model_id, estimated_tokens)
    if fallback is not None:
        print(
            "[TokenTotals Pricing Warning] No repo-contained provider engine matched "
            f"{model_id!r}; using the exact-model input rate from pinned LiteLLM "
            "as a secondary preflight estimate."
        )
        return fallback, "litellm_catalog_fallback"

    return None, "unpriced"


app = FastAPI(title="TokenTotals by QuietFireAI")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

LAST_LATENCY_MS = 0
THREAD_METADATA_KEY = "tokentotals_thread_id"
RESERVATION_METADATA_KEY = "tokentotals_reservation_id"

litellm.suppress_debug_info = True


def callback_metadata_value(kwargs, key, default=None):
    """Read server-owned TokenTotals metadata from LiteLLM callback containers."""
    containers = []
    for container_name in ("litellm_params", "optional_params"):
        container = kwargs.get(container_name)
        if isinstance(container, dict):
            containers.append(container)
    containers.append(kwargs)

    for container in containers:
        for metadata_name in ("litellm_metadata", "metadata"):
            metadata = container.get(metadata_name)
            if not isinstance(metadata, dict):
                continue
            value = metadata.get(key)
            if value is not None and str(value).strip():
                return str(value).strip()
    return default


def callback_thread_id(kwargs):
    """Read TokenTotals' request-local thread ID from LiteLLM callback metadata."""
    return callback_metadata_value(kwargs, THREAD_METADATA_KEY, "default")


def callback_reservation_id(kwargs):
    """Read TokenTotals' request-local preflight reservation ID."""
    return callback_metadata_value(kwargs, RESERVATION_METADATA_KEY)


def track_cost_callback(kwargs, completion_response, start_time, end_time):
    global LAST_LATENCY_MS
    try:
        LAST_LATENCY_MS = int((end_time - start_time).total_seconds() * 1000)
        request_model = kwargs.get("model", "")
        thread_id = callback_thread_id(kwargs)
        reservation_id = callback_reservation_id(kwargs)
        cost = None
        ledger_cost = None
        cost_basis = "unavailable"
        estimate_complete = False
        provider_result = None

        if completion_response and looks_like_openai_model(request_model):
            provider_result = calculate_openai_response_cost(
                request_model,
                completion_response,
                request_service_tier=request_service_tier_from_callback(kwargs),
            )
            if provider_result.get("complete") and provider_result.get("total_cost_usd") is not None:
                cost = provider_result["total_cost_usd"]
                ledger_cost = cost
                cost_basis = "provider_registry_complete"
                estimate_complete = True
            else:
                print(
                    "[TokenTotals Pricing Warning] OpenAI telemetry could not be fully priced "
                    f"from the verified registry: {provider_result.get('notes', [])}. "
                    "Falling back to LiteLLM response_cost when available."
                )

        elif completion_response and looks_like_anthropic_model(request_model):
            provider_result = calculate_anthropic_response_cost(
                request_model,
                completion_response,
                processing_mode="standard",
                inference_geo_hint=callback_param(kwargs, "inference_geo"),
                service_tier_hint=request_service_tier_from_callback(kwargs),
                speed_hint=callback_param(kwargs, "speed"),
                platform="claude_api",
            )
            if provider_result.get("complete") and provider_result.get("total_cost_usd") is not None:
                cost = provider_result["total_cost_usd"]
                ledger_cost = cost
                cost_basis = "provider_registry_complete"
                estimate_complete = True
            else:
                print(
                    "[TokenTotals Pricing Warning] Anthropic telemetry could not be fully priced "
                    f"from the verified registry: {provider_result.get('notes', [])}. "
                    "Falling back to LiteLLM response_cost when available."
                )

        elif completion_response and looks_like_google_model(request_model):
            provider_result = calculate_google_response_cost(
                request_model,
                completion_response,
                request_service_tier=request_service_tier_from_callback(kwargs),
                processing_mode="standard",
                platform=infer_google_platform(request_model),
                request_feature_hints=google_request_feature_hints_from_callback(kwargs),
            )
            if provider_result.get("complete") and provider_result.get("total_cost_usd") is not None:
                cost = provider_result["total_cost_usd"]
                ledger_cost = cost
                cost_basis = "provider_registry_complete"
                estimate_complete = True
            else:
                print(
                    "[TokenTotals Pricing Warning] Google/Gemini telemetry could not be fully priced "
                    f"from the verified registry: {provider_result.get('notes', [])}. "
                    "Falling back to LiteLLM response_cost when available."
                )

        if cost is None:
            litellm_cost = kwargs.get("response_cost", 0.0) or 0.0
            if litellm_cost:
                cost = litellm_cost
                ledger_cost = cost
                cost_basis = "litellm_response_cost_fallback"
            elif provider_result and provider_result.get("provider") in {"anthropic", "google"}:
                known_equivalent = provider_result.get("known_list_equivalent_usd")
                if known_equivalent is not None:
                    cost = known_equivalent
                    ledger_cost = cost
                    cost_basis = "known_list_equivalent"
                    provider_name = "Anthropic" if provider_result.get("provider") == "anthropic" else "Google/Gemini"
                    print(
                        "[TokenTotals Pricing Warning] LiteLLM supplied no response_cost; "
                        f"recording {provider_name} known list-equivalent estimate instead of $0. "
                        "This value is incomplete and is not an invoice mirror."
                    )
                else:
                    cost = 0.0
            else:
                cost = 0.0

        state_after = config_manager.update_spend(
            cost_usd=cost,
            thread_id=thread_id,
            reservation_id=reservation_id,
        )

        # Turn Notice is a derived notification event, not accounting state. It is
        # evaluated from the same settled estimate and stays independent of ledger I/O.
        if completion_response is not None and reservation_id and ledger_cost is not None:
            try:
                conf = config_manager.get_config()
                turn_notice.evaluate_and_publish(
                    stage="completed",
                    estimated_cost_usd=ledger_cost,
                    threshold_usd=conf.get("turn_notice_threshold_usd"),
                    thread_id=thread_id,
                    turn_id=reservation_id,
                    model_id=request_model,
                    cost_basis=cost_basis,
                    estimate_complete=estimate_complete,
                )
            except Exception as notice_error:
                print(f"[TokenTotals Turn Notice Warning] Completed notice failed: {notice_error}")

        # Only TokenTotals-routed requests carry a stable server-owned reservation
        # ID. Use it as the durable turn ID so duplicate callbacks cannot create
        # duplicate ledger history. Direct/foreign callbacks without that identity
        # still settle local spend but are not written as ambiguous ledger turns.
        if completion_response is not None and reservation_id:
            try:
                record = turn_ledger.build_turn_record(
                    turn_id=reservation_id,
                    thread_id=thread_id,
                    requested_model_id=request_model,
                    completion_response=completion_response,
                    provider_result=provider_result,
                    estimated_cost_usd=ledger_cost,
                    cost_basis=cost_basis,
                    estimate_complete=estimate_complete,
                    start_time=start_time,
                    end_time=end_time,
                    requested_service_tier=request_service_tier_from_callback(kwargs),
                    state_after=state_after,
                )
                turn_ledger.append_turn(record)
            except Exception as ledger_error:
                print(f"[TokenTotals Ledger Warning] Turn ledger append failed: {ledger_error}")
    except Exception as e:
        print(f"[TokenTotals Pricing Warning] Cost callback failed: {e}")


litellm.success_callback = [track_cost_callback]


@app.get("/v1/models")
async def list_models():
    return {
        "object": "list",
        "data": registered_model_entries(),
    }


@app.get("/api/status")
async def get_status():
    conf = config_manager.get_config()
    state = config_manager.get_state()
    pacing = config_manager.get_pacing_snapshot()
    limit = conf.get("daily_budget_limit_usd", 10.00)
    current = state.get("current_spend_usd", 0.00)
    committed = pacing.get("committed_spend_usd", current)
    pct = round((committed / limit * 100), 1) if limit > 0 else 0
    posted_pct = round((current / limit * 100), 1) if limit > 0 else 0
    inflight = pacing.get("inflight_reserved_usd", 0.0)

    traffic_light = "GREEN"
    if state.get("is_locked"):
        traffic_light = "RED"
    elif pct >= conf.get("warning_threshold_pct", 75):
        traffic_light = "YELLOW"

    return {
        "status": "LOCKED" if state.get("is_locked") else "ACTIVE",
        "traffic_light": traffic_light,
        # Neutral presentation names. Legacy budget_* fields remain below for API
        # compatibility until a dedicated migration removes them.
        "posted_estimated_spend_usd": current,
        "inflight_preflight_estimate_usd": inflight,
        "combined_local_estimate_usd": committed,
        "pacing_threshold_usd": limit,
        "posted_threshold_pct": posted_pct,
        "combined_threshold_pct": pct,
        "active_thread_id": str(state.get("active_thread_id") or "default"),
        "current_spend_usd": current,
        "inflight_reserved_usd": inflight,
        "committed_spend_usd": committed,
        "daily_budget_limit_usd": limit,
        "remaining_budget_usd": pacing.get("available_budget_usd", max(0.0, round(limit - current, 4))),
        "budget_used_pct": posted_pct,
        "budget_committed_pct": pct,
        "thread_spend_usd": state.get("thread_spend_usd", 0.00),
        "last_latency_ms": LAST_LATENCY_MS,
        "is_locked": state.get("is_locked", False),
        "port": conf.get("port", 8080),
    }


@app.get("/api/telemetry/thread")
async def get_thread_telemetry(thread_id: str):
    key = str(thread_id).strip()
    if not key:
        raise HTTPException(status_code=400, detail="thread_id must be non-empty")
    try:
        view = telemetry_view.thread_view(key)
    except turn_ledger.LedgerCorruptionError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"TokenTotals turn ledger is corrupt: {exc}",
        )
    if view is None:
        raise HTTPException(
            status_code=404,
            detail=f"No TokenTotals turn telemetry exists for thread '{key}'.",
        )
    return view


@app.get("/api/turn-notice")
async def get_turn_notice(thread_id: str = None):
    conf = config_manager.get_config()
    threshold = turn_notice.normalize_threshold(conf.get("turn_notice_threshold_usd"))
    key = None
    if thread_id is not None:
        key = str(thread_id).strip()
        if not key:
            raise HTTPException(status_code=400, detail="thread_id must be non-empty when supplied")
    return {
        "enabled": threshold is not None,
        "reminder_threshold_usd": threshold,
        "scope": "thread" if key is not None else "global",
        "thread_id": key,
        "notice": turn_notice.latest_notice(key),
    }


@app.post("/api/turn-notice/config")
async def set_turn_notice_config(request: Request):
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")
    if not isinstance(payload, dict) or "reminder_threshold_usd" not in payload:
        raise HTTPException(status_code=400, detail="reminder_threshold_usd is required")

    raw_value = payload.get("reminder_threshold_usd")
    if raw_value is None:
        threshold = None
    else:
        if isinstance(raw_value, bool) or not isinstance(raw_value, (int, float)):
            raise HTTPException(
                status_code=400,
                detail="reminder_threshold_usd must be a positive number or null to disable",
            )
        threshold = float(raw_value)
        if not math.isfinite(threshold) or threshold <= 0:
            raise HTTPException(
                status_code=400,
                detail="reminder_threshold_usd must be a positive number or null to disable",
            )

    conf = config_manager.get_config()
    conf["turn_notice_threshold_usd"] = threshold
    config_manager.save_config(conf)
    return {
        "enabled": threshold is not None,
        "reminder_threshold_usd": threshold,
        "meaning": "local per-turn reminder threshold; not a provider account balance or spending authorization",
    }


@app.post("/api/boost")
async def api_quick_boost():
    new_limit = config_manager.quick_boost(5.00)
    return {"message": "Local pacing threshold increased by $5.00", "new_limit_usd": new_limit, "is_locked": False}


@app.post("/api/unlock")
async def api_unlock():
    config_manager.unlock_circuit_breaker()
    return {"message": "Local pacing lock cleared by user acknowledgment.", "is_locked": False}


@app.get("/", response_class=HTMLResponse)
@app.get("/dashboard", response_class=HTMLResponse)
@app.get("/dashboard/", response_class=HTMLResponse)
@app.get("/dashboard.html", response_class=HTMLResponse)
async def serve_dashboard():
    return HTMLResponse(content=DASHBOARD_HTML)


@app.post("/v1/chat/completions")
async def proxy_openai(request: Request):
    state = config_manager.get_state()

    # 1. HARD DEAD MAN'S SWITCH CHECK
    if state.get("is_locked", False):
        raise HTTPException(
            status_code=403,
            detail="🛑 QuietFireAI Emergency Shutdown: Daily budget cap reached. Outgoing calls are HARD-LOCKED to protect your card. Acknowledge in the desktop popup or dashboard to resume.",
        )

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    model_id = payload.get("model")
    if not isinstance(model_id, str) or not model_id.strip():
        raise HTTPException(
            status_code=400,
            detail="TokenTotals requires an explicit non-empty model ID; no default model is inferred.",
        )
    model_id = model_id.strip()
    thread_id = request.headers.get("x-thread-id") or payload.get("user") or "default"
    thread_id = str(thread_id).strip() or "default"

    # 2. PRE-FLIGHT AUDIT
    # This is deliberately an estimate. Actual post-response provider accounting
    # uses observed usage telemetry whenever the dedicated provider engine can
    # fully reconstruct the applicable public pricing mechanics.
    prompt_text = json.dumps(payload.get("messages", []))
    estimated_tokens = estimate_text_tokens(prompt_text, model_id)
    estimated_cost, preflight_source = preflight_input_estimate(model_id, estimated_tokens, payload)

    if estimated_cost is None:
        raise HTTPException(
            status_code=422,
            detail=(
                "TokenTotals Pricing Unavailable: no defensible preflight input price "
                f"is available for model '{model_id}' (source={preflight_source}). "
                "The request was not sent upstream."
            ),
        )

    # Atomically reserve the known preflight estimate before the provider call.
    # This prevents concurrent requests from independently spending the same local
    # headroom. It does not claim to predict response-dependent output/tool cost.
    reservation_id = uuid.uuid4().hex
    reservation = config_manager.reserve_preflight_budget(
        reservation_id,
        estimated_cost,
        thread_id=thread_id,
    )
    if not reservation.get("accepted"):
        reason = reservation.get("reason")
        limit = reservation.get("daily_budget_limit_usd", 0.0)
        if reason == "inflight_headroom":
            raise HTTPException(
                status_code=429,
                detail=(
                    "TokenTotals Pacing Hold: available local headroom is temporarily "
                    "reserved by other in-flight requests. This request was not sent "
                    "upstream; retry after those requests settle."
                ),
            )
        if reason == "locked":
            raise HTTPException(
                status_code=403,
                detail="🛑 QuietFireAI Emergency Shutdown: local pacing is locked.",
            )
        raise HTTPException(
            status_code=403,
            detail=(
                f"🚨 QuietFireAI Circuit Breaker: This request ({estimated_cost:.4f} USD) "
                f"would exceed your daily budget of ${limit:.2f}. Outgoing calls locked."
            ),
        )

    # The preflight Turn Notice only exists after pacing admission. It describes
    # the input-side estimate; it is not a claim about the final turn or account.
    try:
        conf = config_manager.get_config()
        turn_notice.evaluate_and_publish(
            stage="preflight",
            estimated_cost_usd=estimated_cost,
            threshold_usd=conf.get("turn_notice_threshold_usd"),
            thread_id=thread_id,
            turn_id=reservation_id,
            model_id=model_id,
            cost_basis=preflight_source,
            estimate_complete=False,
        )
    except Exception as notice_error:
        print(f"[TokenTotals Turn Notice Warning] Preflight notice failed: {notice_error}")

    # TokenTotals does not silently substitute models or providers. Pricing data
    # alone does not establish capability, tool/modality support, credentials,
    # provider-policy compatibility, or equivalent output behavior.

    # 3. UPSTREAM ROUTING VIA LITELLM
    auth_header = request.headers.get("authorization", "")
    api_key = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else auth_header

    stream = payload.pop("stream", False)
    messages = payload.pop("messages", [])
    payload.pop("model", None)
    # litellm_metadata is reserved for TokenTotals' request-local callback
    # attribution and pacing reconciliation. Do not let client input replace it.
    payload.pop("litellm_metadata", None)

    try:
        response = await litellm.acompletion(
            model=model_id,
            messages=messages,
            api_key=api_key,
            stream=stream,
            litellm_metadata={
                THREAD_METADATA_KEY: thread_id,
                RESERVATION_METADATA_KEY: reservation_id,
            },
            **payload,
        )
    except Exception as e:
        config_manager.release_preflight_reservation(reservation_id)
        raise HTTPException(status_code=502, detail=f"Upstream Provider Error via LiteLLM: {str(e)}")

    if stream:
        async def generate():
            try:
                async for chunk in response:
                    yield f"data: {chunk.model_dump_json()}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
            finally:
                # Normally the LiteLLM success callback settles the reservation.
                # If a stream aborts before that callback occurs, do not strand
                # ephemeral pacing headroom indefinitely.
                config_manager.release_preflight_reservation(reservation_id)
                yield "data: [DONE]\n\n"

        return StreamingResponse(generate(), media_type="text/event-stream")
    else:
        return response.model_dump()


DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>TokenTotals by QuietFireAI — Local AI Cost Telemetry</title>
<style>
:root {
  --bg: #090a0f;
  --card: #131620;
  --border: #23293d;
  --green: #10b981;
  --yellow: #f59e0b;
  --red: #ef4444;
  --blue: #60a5fa;
  --text: #f3f4f6;
  --subtext: #9ca3af;
}
* { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
body { background: var(--bg); color: var(--text); padding: 24px; display: flex; justify-content: center; }
.container { max-width: 1000px; width: 100%; display: flex; flex-direction: column; gap: 20px; }
header { display: flex; justify-content:space-between; align-items:center; border-bottom:1px solid var(--border); padding-bottom:16px; }
.brand { display:flex; align-items:center; gap:12px; }
.brand h1 { font-size:22px; font-weight:700; letter-spacing:-0.5px; }
.badge { font-size:11px; padding:4px 8px; border-radius:999px; font-weight:600; text-transform:uppercase; }
.badge-green { background:rgba(16,185,129,0.2); color:var(--green); border:1px solid var(--green); }
.badge-red { background:rgba(239,68,68,0.2); color:var(--red); border:1px solid var(--red); }
.card { background:var(--card); border:1px solid var(--border); border-radius:12px; padding:20px; }
.grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(240px,1fr)); gap:16px; }
.metric-title { font-size:13px; color:var(--subtext); text-transform:uppercase; letter-spacing:0.5px; margin-bottom:6px; }
.metric-value { font-size:28px; font-weight:700; }
.subtle { font-size:12px; color:var(--subtext); line-height:1.5; }
.progress-bar-bg { background:#1f2538; height:12px; border-radius:6px; overflow:hidden; margin:12px 0 6px 0; }
.progress-bar-fill { height:100%; background:var(--green); transition:width 0.4s ease; }
.btn { padding:8px 16px; border-radius:6px; font-weight:600; cursor:pointer; border:none; font-size:14px; transition:0.2s; }
.btn-boost { background:var(--green); color:#000; }
.btn-boost:hover { filter:brightness(1.1); }
.btn-copy, .btn-secondary { background:#23293d; color:var(--text); border:1px solid #374151; font-size:12px; }
.btn-copy:hover, .btn-secondary:hover { background:#374151; }
input[type=number] { background:#0c0e14; color:var(--text); border:1px solid #374151; border-radius:6px; padding:8px 10px; width:130px; }
pre { background:#0c0e14; padding:12px; border-radius:8px; font-size:13px; color:#a5b4fc; overflow-x:auto; margin-top:8px; }
.receipts-list { display:flex; flex-wrap:wrap; gap:12px; margin-top:10px; }
.receipt-link { font-size:13px; color:var(--blue); text-decoration:none; display:flex; align-items:center; gap:4px; }
.receipt-link:hover { text-decoration:underline; }
.data-row { display:flex; justify-content:space-between; gap:16px; padding:7px 0; border-bottom:1px solid rgba(55,65,81,0.45); font-size:13px; }
.data-row:last-child { border-bottom:none; }
.data-label { color:var(--subtext); }
.data-value { text-align:right; overflow-wrap:anywhere; }
.model-row { padding:9px 0; border-bottom:1px solid rgba(55,65,81,0.45); font-size:13px; }
.model-row:last-child { border-bottom:none; }
.notice-box { margin-top:12px; background:#0c0e14; border:1px solid #374151; border-radius:8px; padding:12px; }
</style>
</head>
<body>
<div class="container">
  <header>
    <div class="brand">
      <svg width="28" height="28" viewBox="0 0 64 64"><rect x="12" y="12" width="40" height="12" fill="#10b981"/><rect x="26" y="24" width="12" height="28" fill="#10b981"/></svg>
      <div>
        <h1>TokenTotals <span style="font-size:14px; font-weight:normal; color:var(--subtext);">by QuietFireAI</span></h1>
      </div>
    </div>
    <div id="statusBadge" class="badge badge-green">🟢 BELOW LOCAL THRESHOLD</div>
  </header>

  <div class="card">
    <div style="display:flex; justify-content:space-between; align-items:flex-end; gap:16px; flex-wrap:wrap;">
      <div>
        <div class="metric-title">Posted Local Estimate / Pacing Threshold</div>
        <div style="display:flex; align-items:baseline; gap:8px; flex-wrap:wrap;">
          <span class="metric-value" id="spendVal">$0.0000</span>
          <span style="color:var(--subtext); font-size:18px;" id="limitVal">/ $10.00 Local Pacing Threshold</span>
        </div>
      </div>
      <button class="btn btn-boost" onclick="addBoost()">⚡ Raise Local Threshold +$5</button>
    </div>
    <div class="progress-bar-bg">
      <div id="progressFill" class="progress-bar-fill" style="width: 0%;"></div>
    </div>
    <div style="display:flex; justify-content:space-between; gap:12px; flex-wrap:wrap; font-size:12px; color:var(--subtext);">
      <span id="remainingVal">Combined local estimate: $0.0000</span>
      <span id="pctVal">0.0% of local threshold</span>
    </div>
  </div>

  <div class="grid">
    <div class="card">
      <div class="metric-title">Active Thread Local Estimate</div>
      <div class="metric-value" id="threadVal" style="color:var(--blue);">$0.0000</div>
      <div class="subtle" id="threadIdVal">Thread: default</div>
    </div>
    <div class="card">
      <div class="metric-title">Proxy Port & Last Observed Latency</div>
      <div class="metric-value" id="latencyVal" style="font-size:22px;">8080 <span style="font-size:14px; color:var(--subtext);">| 0 ms</span></div>
      <div class="subtle">Local loopback control plane; permitted requests still egress to the selected upstream provider</div>
    </div>
  </div>

  <div class="card">
    <div style="display:flex; justify-content:space-between; gap:16px; align-items:flex-start; flex-wrap:wrap;">
      <div>
        <h3 style="font-size:15px; margin-bottom:6px;">🔔 Turn Notice</h3>
        <div class="subtle" id="noticeStatus">Disabled until you set a per-turn reminder threshold.</div>
      </div>
      <div style="display:flex; gap:8px; align-items:center; flex-wrap:wrap;">
        <label class="subtle" for="noticeThresholdInput">USD per-turn reminder</label>
        <input id="noticeThresholdInput" type="number" min="0.000001" step="0.0001" placeholder="0.2500">
        <button class="btn btn-secondary" onclick="setTurnNoticeThreshold()">Set Reminder</button>
        <button class="btn btn-secondary" onclick="disableTurnNotice()">Disable</button>
      </div>
    </div>
    <div class="notice-box">
      <div id="noticeMessage" style="font-size:14px;">No Turn Notice fired for the active thread.</div>
      <div class="subtle" id="noticeMeta" style="margin-top:6px;">A Turn Notice is a local estimate reminder, not provider-account clearance.</div>
    </div>
  </div>

  <div class="card">
    <h3 style="font-size:15px; margin-bottom:12px;">📈 Latest Turn & Thread Telemetry</h3>
    <div id="telemetryEmpty" class="subtle">No completed turn telemetry yet for the active thread.</div>
    <div id="telemetryContent" style="display:none;">
      <div class="grid">
        <div>
          <div class="data-row"><span class="data-label">Model / Provider</span><span class="data-value" id="telemetryModel">Unavailable</span></div>
          <div class="data-row"><span class="data-label">Turn estimate</span><span class="data-value" id="telemetryCost">Unavailable</span></div>
          <div class="data-row"><span class="data-label">Pricing basis</span><span class="data-value" id="telemetryBasis">Unavailable</span></div>
          <div class="data-row"><span class="data-label">Registry verified</span><span class="data-value" id="telemetryRegistry">Unavailable</span></div>
          <div class="data-row"><span class="data-label">Latency / output rate</span><span class="data-value" id="telemetryTiming">Unavailable</span></div>
        </div>
        <div>
          <div class="data-row"><span class="data-label">Input tokens</span><span class="data-value" id="tokenInput">Unavailable</span></div>
          <div class="data-row"><span class="data-label">Cached input</span><span class="data-value" id="tokenCached">Unavailable</span></div>
          <div class="data-row"><span class="data-label">Uncached input</span><span class="data-value" id="tokenUncached">Unavailable</span></div>
          <div class="data-row"><span class="data-label">Cache write/create</span><span class="data-value" id="tokenCacheWrite">Unavailable</span></div>
          <div class="data-row"><span class="data-label">Output tokens</span><span class="data-value" id="tokenOutput">Unavailable</span></div>
          <div class="data-row"><span class="data-label">Reasoning / thinking</span><span class="data-value" id="tokenReasoning">Unavailable</span></div>
          <div class="data-row"><span class="data-label">Tool input</span><span class="data-value" id="tokenTool">Unavailable</span></div>
          <div class="data-row"><span class="data-label">Residual / unclassified</span><span class="data-value" id="tokenResidual">Unavailable</span></div>
        </div>
      </div>
      <div class="notice-box" style="margin-top:14px;">
        <div id="threadSummary" style="font-size:13px;">Thread summary unavailable.</div>
        <div id="cacheShare" class="subtle" style="margin-top:6px;">Cache share unavailable.</div>
      </div>
      <h4 style="font-size:13px; margin:16px 0 4px;">Models used in this thread</h4>
      <div id="modelsBreakdown"></div>
    </div>
  </div>

  <div class="card">
    <h3 style="font-size:15px; margin-bottom:12px;">🔌 1-Click IDE Configuration</h3>
    <p class="subtle" style="margin-bottom:10px;">
      Point your AI coding tool to TokenTotals' local loopback port to use the local pacing and telemetry layer:
    </p>
    <div style="display:flex; justify-content:space-between; align-items:center; gap:12px; flex-wrap:wrap;">
      <span style="font-size:13px; font-weight:600;">Base URL: <code>http://127.0.0.1:8080/v1</code></span>
      <button class="btn btn-copy" onclick="navigator.clipboard.writeText('http://127.0.0.1:8080/v1'); alert('Copied to clipboard!')">📋 Copy URL</button>
    </div>
    <pre><code>// Cursor & VS Code Settings:
"openai.apiBase": "http://127.0.0.1:8080/v1"

// Python / OpenAI-compatible client:
from openai import OpenAI
client = OpenAI(base_url="http://127.0.0.1:8080/v1", api_key="YOUR_KEY")</code></pre>
  </div>

  <div class="card">
    <h3 style="font-size:14px; margin-bottom:6px;">📊 Model Pricing & Docs</h3>
    <p class="subtle">Pricing references are versioned from provider documentation. Calculations use available model and usage telemetry and are not represented as billing-exact.</p>
    <div class="receipts-list">
      <a class="receipt-link" href="https://openai.com/api/pricing/" target="_blank">🔗 OpenAI Official Pricing Documentation ↗</a>
      <a class="receipt-link" href="https://www.anthropic.com/pricing" target="_blank">🔗 Anthropic Claude Pricing Documentation ↗</a>
      <a class="receipt-link" href="https://ai.google.dev/pricing" target="_blank">🔗 Google Gemini Pricing Documentation ↗</a>
    </div>
  </div>
</div>

<script>
function usd(value, digits=4) {
  return value === null || value === undefined ? 'Unavailable' : '$' + Number(value).toFixed(digits);
}

function tokenMetric(metric) {
  if (!metric || metric.value === null || metric.value === undefined) return 'Unavailable';
  const basis = metric.basis && metric.basis !== 'unavailable' ? ' (' + metric.basis + ')' : '';
  return Number(metric.value).toLocaleString() + basis;
}

function summaryTokenValue(metric) {
  if (!metric || metric.sum === null || metric.sum === undefined) return 'Unavailable';
  return Number(metric.sum).toLocaleString() + ' (' + metric.coverage + ', ' + metric.observed_turns + '/' + metric.total_turns + ' turns)';
}

function safeModel(turn) {
  if (!turn || !turn.model) return 'Unavailable';
  return turn.model.canonical || turn.model.observed || turn.model.requested || 'Unavailable';
}

function renderTelemetry(data) {
  const empty = document.getElementById('telemetryEmpty');
  const content = document.getElementById('telemetryContent');
  if (!data || !data.latest_turn) {
    empty.style.display = 'block';
    content.style.display = 'none';
    return;
  }
  empty.style.display = 'none';
  content.style.display = 'block';

  const turn = data.latest_turn;
  document.getElementById('telemetryModel').textContent = safeModel(turn) + ' / ' + (turn.provider || 'unknown');
  const cost = turn.cost || {};
  document.getElementById('telemetryCost').textContent = cost.estimated_usd === null || cost.estimated_usd === undefined
    ? 'Unavailable'
    : usd(cost.estimated_usd) + (cost.complete ? ' (complete)' : ' (incomplete)');
  document.getElementById('telemetryBasis').textContent = cost.basis || 'Unavailable';
  document.getElementById('telemetryRegistry').textContent = cost.registry_verified_at || 'Unavailable';

  let timing = turn.latency_ms === null || turn.latency_ms === undefined ? 'Latency unavailable' : turn.latency_ms + ' ms wall-clock';
  if (turn.output_tokens_per_wall_second !== null && turn.output_tokens_per_wall_second !== undefined) {
    timing += ' | ' + turn.output_tokens_per_wall_second + ' output tok/s wall-clock';
  }
  document.getElementById('telemetryTiming').textContent = timing;

  const tokens = turn.tokens || {};
  document.getElementById('tokenInput').textContent = tokenMetric(tokens.input_tokens);
  document.getElementById('tokenCached').textContent = tokenMetric(tokens.cached_input_tokens);
  document.getElementById('tokenUncached').textContent = tokenMetric(tokens.uncached_input_tokens);
  document.getElementById('tokenCacheWrite').textContent = tokenMetric(tokens.cache_write_tokens);
  document.getElementById('tokenOutput').textContent = tokenMetric(tokens.output_tokens);
  document.getElementById('tokenReasoning').textContent = tokenMetric(tokens.reasoning_tokens);
  document.getElementById('tokenTool').textContent = tokenMetric(tokens.tool_input_tokens);
  document.getElementById('tokenResidual').textContent = tokenMetric(tokens.residual_unclassified_tokens);

  const threadCost = data.cost || {};
  const stats = data.turn_token_stats || {};
  let summary = data.turn_count + ' completed turn' + (data.turn_count === 1 ? '' : 's');
  if (threadCost.estimated_cost_usd !== null && threadCost.estimated_cost_usd !== undefined) {
    summary += ' | local estimated cost ' + usd(threadCost.estimated_cost_usd) + ' (' + threadCost.coverage + ', ' + threadCost.costed_turns + '/' + threadCost.total_turns + ' costed turns)';
  } else {
    summary += ' | local estimated cost unavailable';
  }
  if (stats.average !== null && stats.average !== undefined) {
    summary += ' | avg ' + Math.round(stats.average).toLocaleString() + ' tok/turn';
    summary += ' | median ' + Number(stats.median).toLocaleString();
    summary += ' | P95 ' + Number(stats.p95_nearest_rank).toLocaleString();
  }
  document.getElementById('threadSummary').textContent = summary;

  if (turn.cache_share) {
    document.getElementById('cacheShare').textContent = 'Observed cached-input share: ' + turn.cache_share.pct_of_input.toFixed(2) + '% (' + turn.cache_share.cached_tokens.toLocaleString() + ' / ' + turn.cache_share.input_tokens.toLocaleString() + ' input tokens). Token share is not presented as dollar savings.';
  } else {
    document.getElementById('cacheShare').textContent = 'Observed cached-input share: Unavailable.';
  }

  const models = document.getElementById('modelsBreakdown');
  models.textContent = '';
  const rows = data.by_model || [];
  if (!rows.length) {
    const row = document.createElement('div');
    row.className = 'subtle';
    row.textContent = 'No model breakdown available.';
    models.appendChild(row);
  } else {
    rows.forEach(item => {
      const row = document.createElement('div');
      row.className = 'model-row';
      const modelCost = item.cost || {};
      const totalMetric = (item.tokens || {}).provider_reported_total_tokens || (item.tokens || {}).reconstructed_total_tokens;
      let text = item.model_id + ' / ' + (item.provider || 'unknown') + ' — ' + item.turn_count + ' turn' + (item.turn_count === 1 ? '' : 's');
      text += ' — tokens ' + summaryTokenValue(totalMetric);
      if (modelCost.estimated_cost_usd !== null && modelCost.estimated_cost_usd !== undefined) {
        text += ' — estimate ' + usd(modelCost.estimated_cost_usd) + ' (' + modelCost.coverage + ')';
      } else {
        text += ' — estimate Unavailable';
      }
      row.textContent = text;
      models.appendChild(row);
    });
  }
}

function renderNotice(data) {
  const enabled = data && data.enabled;
  document.getElementById('noticeStatus').textContent = enabled
    ? 'Enabled at ' + usd(data.reminder_threshold_usd) + ' per turn. This is a local reminder threshold.'
    : 'Disabled until you set a per-turn reminder threshold.';

  const input = document.getElementById('noticeThresholdInput');
  if (document.activeElement !== input) {
    input.value = enabled ? Number(data.reminder_threshold_usd).toString() : '';
  }

  const notice = data ? data.notice : null;
  if (!notice) {
    document.getElementById('noticeMessage').textContent = 'No Turn Notice fired for the active thread.';
    document.getElementById('noticeMeta').textContent = 'A Turn Notice is a local estimate reminder, not provider-account clearance.';
    return;
  }
  document.getElementById('noticeMessage').textContent = notice.message;
  document.getElementById('noticeMeta').textContent = 'Stage: ' + notice.stage + ' | Model: ' + (notice.model_id || 'Unavailable') + ' | Basis: ' + (notice.cost_basis || 'unavailable') + ' | Estimate status: ' + (notice.estimate_complete ? 'complete' : 'incomplete/preflight');
}

async function refreshThreadSurfaces(threadId) {
  const encoded = encodeURIComponent(threadId || 'default');
  try {
    const noticeRes = await fetch('/api/turn-notice?thread_id=' + encoded);
    if (noticeRes.ok) renderNotice(await noticeRes.json());
  } catch(e) {}

  try {
    const telemetryRes = await fetch('/api/telemetry/thread?thread_id=' + encoded);
    if (telemetryRes.status === 404) {
      renderTelemetry(null);
    } else if (telemetryRes.ok) {
      renderTelemetry(await telemetryRes.json());
    }
  } catch(e) {}
}

async function refresh() {
  try {
    const res = await fetch('/api/status');
    const data = await res.json();
    document.getElementById('spendVal').textContent = usd(data.posted_estimated_spend_usd);
    document.getElementById('limitVal').textContent = '/ ' + usd(data.pacing_threshold_usd, 2) + ' Local Pacing Threshold';

    let combined = 'Combined local estimate: ' + usd(data.combined_local_estimate_usd);
    if (data.inflight_preflight_estimate_usd > 0) combined += ' (includes ' + usd(data.inflight_preflight_estimate_usd) + ' in-flight preflight estimate)';
    document.getElementById('remainingVal').textContent = combined;
    document.getElementById('pctVal').textContent = data.combined_threshold_pct.toFixed(1) + '% of local threshold';
    document.getElementById('progressFill').style.width = Math.min(100, data.combined_threshold_pct) + '%';
    document.getElementById('threadVal').textContent = usd(data.thread_spend_usd);
    document.getElementById('threadIdVal').textContent = 'Thread: ' + (data.active_thread_id || 'default');
    document.getElementById('latencyVal').innerHTML = data.port + ' <span style="font-size:14px; color:var(--subtext);">| ' + data.last_latency_ms + ' ms</span>';

    const badge = document.getElementById('statusBadge');
    if (data.is_locked) {
      badge.className = 'badge badge-red';
      badge.innerText = '🔴 LOCAL PACING THRESHOLD REACHED';
      document.getElementById('progressFill').style.background = 'var(--red)';
    } else if (data.traffic_light === 'YELLOW') {
      badge.className = 'badge';
      badge.style.background = 'rgba(245, 158, 11, 0.2)';
      badge.style.color = 'var(--yellow)';
      badge.style.border = '1px solid var(--yellow)';
      badge.innerText = '🟡 NEAR LOCAL THRESHOLD';
      document.getElementById('progressFill').style.background = 'var(--yellow)';
    } else {
      badge.className = 'badge badge-green';
      badge.innerText = '🟢 BELOW LOCAL THRESHOLD';
      document.getElementById('progressFill').style.background = 'var(--green)';
    }

    await refreshThreadSurfaces(data.active_thread_id || 'default');
  } catch(e) {}
}

async function setTurnNoticeThreshold() {
  const input = document.getElementById('noticeThresholdInput');
  const value = Number(input.value);
  if (!input.value || !Number.isFinite(value) || value <= 0) {
    alert('Enter a positive per-turn USD reminder value.');
    return;
  }
  const res = await fetch('/api/turn-notice/config', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({reminder_threshold_usd:value})
  });
  if (!res.ok) {
    const data = await res.json();
    alert(data.detail || 'Could not update Turn Notice.');
  }
  refresh();
}

async function disableTurnNotice() {
  await fetch('/api/turn-notice/config', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({reminder_threshold_usd:null})
  });
  refresh();
}

async function addBoost() {
  await fetch('/api/boost', {method:'POST'});
  refresh();
}

setInterval(refresh, 2000);
refresh();
</script>
</body>
</html>"""

if __name__ == "__main__":
    import uvicorn
    conf = config_manager.get_config()
    port = conf.get("port", 8080)
    uvicorn.run(app, host="127.0.0.1", port=port)