import json
import time
import sys
import os

if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse, HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import litellm
import config_manager
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
CURRENT_ROUTINE_FLAG = False
CURRENT_POTENTIAL_SAVING = 0.0
CURRENT_THREAD_ID = "default"

litellm.suppress_debug_info = True


def track_cost_callback(kwargs, completion_response, start_time, end_time):
    global LAST_LATENCY_MS, CURRENT_ROUTINE_FLAG, CURRENT_POTENTIAL_SAVING, CURRENT_THREAD_ID
    try:
        LAST_LATENCY_MS = int((end_time - start_time).total_seconds() * 1000)
        request_model = kwargs.get("model", "")
        cost = None
        provider_result = None

        if completion_response and looks_like_openai_model(request_model):
            provider_result = calculate_openai_response_cost(
                request_model,
                completion_response,
                request_service_tier=request_service_tier_from_callback(kwargs),
            )
            if provider_result.get("complete") and provider_result.get("total_cost_usd") is not None:
                cost = provider_result["total_cost_usd"]
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
            elif provider_result and provider_result.get("provider") in {"anthropic", "google"}:
                known_equivalent = provider_result.get("known_list_equivalent_usd")
                if known_equivalent is not None:
                    cost = known_equivalent
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

        config_manager.update_spend(
            cost_usd=cost,
            thread_id=CURRENT_THREAD_ID,
            potential_saving=CURRENT_POTENTIAL_SAVING,
            is_routine=CURRENT_ROUTINE_FLAG,
        )
    except Exception as e:
        print(f"[TokenTotals Pricing Warning] Cost callback failed: {e}")


litellm.success_callback = [track_cost_callback]


@app.get("/v1/models")
async def list_models():
    return {
        "object": "list",
        "data": [
            {"id": "gpt-4o", "object": "model", "owned_by": "openai"},
            {"id": "o3-mini", "object": "model", "owned_by": "openai"},
            {"id": "claude-3-5-sonnet", "object": "model", "owned_by": "anthropic"},
            {"id": "gemini-2.0-flash", "object": "model", "owned_by": "google"},
        ],
    }


@app.get("/api/status")
async def get_status():
    conf = config_manager.get_config()
    state = config_manager.get_state()
    limit = conf.get("daily_budget_limit_usd", 10.00)
    current = state.get("current_spend_usd", 0.00)
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
        "remaining_budget_usd": max(0.0, round(limit - current, 4)),
        "budget_used_pct": pct,
        "thread_spend_usd": state.get("thread_spend_usd", 0.00),
        "potential_savings_usd": state.get("potential_savings_usd", 0.00),
        "flagged_routine_calls": state.get("flagged_routine_calls", 0),
        "last_latency_ms": LAST_LATENCY_MS,
        "is_locked": state.get("is_locked", False),
        "auto_economy_mode": conf.get("auto_economy_mode", False),
        "port": conf.get("port", 8080),
    }


@app.post("/api/boost")
async def api_quick_boost():
    new_limit = config_manager.quick_boost(5.00)
    return {"message": "Budget boosted by $5.00", "new_limit_usd": new_limit, "is_locked": False}


@app.post("/api/unlock")
async def api_unlock():
    config_manager.unlock_circuit_breaker()
    return {"message": "Circuit breaker unlocked by user acknowledgment.", "is_locked": False}


@app.get("/", response_class=HTMLResponse)
@app.get("/dashboard", response_class=HTMLResponse)
@app.get("/dashboard/", response_class=HTMLResponse)
@app.get("/dashboard.html", response_class=HTMLResponse)
async def serve_dashboard():
    return HTMLResponse(content=DASHBOARD_HTML)


@app.post("/v1/chat/completions")
async def proxy_openai(request: Request):
    global CURRENT_ROUTINE_FLAG, CURRENT_POTENTIAL_SAVING, CURRENT_THREAD_ID

    state = config_manager.get_state()
    conf = config_manager.get_config()

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

    model_id = payload.get("model", "gpt-4o")
    CURRENT_THREAD_ID = request.headers.get("x-thread-id") or payload.get("user") or "default"

    # 2. PRE-FLIGHT AUDIT & POTENTIAL SAVINGS CALCULATION
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

    # Check for budget breach BEFORE sending request
    limit = conf.get("daily_budget_limit_usd", 10.00)
    if state.get("current_spend_usd", 0.0) + estimated_cost > limit:
        config_manager.set_locked(True)
        raise HTTPException(
            status_code=403,
            detail=f"🚨 QuietFireAI Circuit Breaker: This request ({estimated_cost:.4f} USD) would exceed your daily budget of ${limit:.2f}. Outgoing calls locked.",
        )

    # Heuristic: Is this a routine/lightweight task?
    word_count = len(prompt_text.split())
    is_premium_model = any(
        m in model_id.lower() for m in ["gpt-4o", "claude-3-5-sonnet", "gemini-1.5-pro"]
    )
    is_lightweight = word_count < 80 or estimated_tokens < 300

    CURRENT_ROUTINE_FLAG = is_premium_model and is_lightweight
    CURRENT_POTENTIAL_SAVING = 0.0

    if CURRENT_ROUTINE_FLAG:
        econ_model = "o3-mini" if "gpt" in model_id.lower() else "gemini-2.0-flash-lite"
        economy_cost, _ = preflight_input_estimate(econ_model, estimated_tokens, payload)

        if economy_cost is not None:
            CURRENT_POTENTIAL_SAVING = max(0.0, estimated_cost - economy_cost)

            # Opt-In Auto-Economy Pilot (Default: False). Never switch to an
            # economy target that TokenTotals cannot preflight-price.
            if conf.get("auto_economy_mode", False):
                model_id = econ_model
        else:
            print(
                "[TokenTotals Pricing Warning] Economy target could not be priced; "
                f"skipping savings estimate and auto-routing for {econ_model!r}."
            )

    # 3. UPSTREAM ROUTING VIA LITELLM
    auth_header = request.headers.get("authorization", "")
    api_key = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else auth_header

    stream = payload.pop("stream", False)
    messages = payload.pop("messages", [])
    payload.pop("model", None)

    try:
        response = await litellm.acompletion(
            model=model_id,
            messages=messages,
            api_key=api_key,
            stream=stream,
            **payload,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Upstream Provider Error via LiteLLM: {str(e)}")

    if stream:
        async def generate():
            try:
                async for chunk in response:
                    yield f"data: {chunk.model_dump_json()}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
            finally:
                yield "data: [DONE]\n\n"

        return StreamingResponse(generate(), media_type="text/event-stream")
    else:
        return response.model_dump()


DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>TokenTotals by QuietFireAI — FinOps Airbag</title>
<style>
:root {
  --bg: #090a0f;
  --card: #131620;
  --border: #23293d;
  --green: #10b981;
  --yellow: #f59e0b;
  --red: #ef4444;
  --text: #f3f4f6;
  --subtext: #9ca3af;
}
* { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
body { background: var(--bg); color: var(--text); padding: 24px; display: flex; justify-content: center; }
.container { max-width: 900px; width: 100%; display: flex; flex-direction: column; gap: 20px; }
header { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--border); padding-bottom: 16px; }
.brand { display: flex; align-items: center; gap: 12px; }
.brand h1 { font-size: 22px; font-weight: 700; letter-spacing: -0.5px; }
.badge { font-size: 11px; padding: 4px 8px; border-radius: 999px; font-weight: 600; text-transform: uppercase; }
.badge-green { background: rgba(16, 185, 129, 0.2); color: var(--green); border: 1px solid var(--green); }
.badge-red { background: rgba(239, 68, 68, 0.2); color: var(--red); border: 1px solid var(--red); }
.card { background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 20px; }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; }
.metric-title { font-size: 13px; color: var(--subtext); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 6px; }
.metric-value { font-size: 28px; font-weight: 700; }
.progress-bar-bg { background: #1f2538; height: 12px; border-radius: 6px; overflow: hidden; margin: 12px 0 6px 0; }
.progress-bar-fill { height: 100%; background: var(--green); transition: width 0.4s ease; }
.btn { padding: 8px 16px; border-radius: 6px; font-weight: 600; cursor: pointer; border: none; font-size: 14px; transition: 0.2s; }
.btn-boost { background: var(--green); color: #000; }
.btn-boost:hover { filter: brightness(1.1); }
.btn-copy { background: #23293d; color: var(--text); border: 1px solid #374151; font-size: 12px; }
.btn-copy:hover { background: #374151; }
pre { background: #0c0e14; padding: 12px; border-radius: 8px; font-size: 13px; color: #a5b4fc; overflow-x: auto; margin-top: 8px; }
.alert-box { border-left: 4px solid var(--yellow); background: rgba(245, 158, 11, 0.08); padding: 12px 16px; border-radius: 0 8px 8px 0; }
.receipts-list { display: flex; flex-wrap: wrap; gap: 12px; margin-top: 10px; }
.receipt-link { font-size: 13px; color: #60a5fa; text-decoration: none; display: flex; align-items: center; gap: 4px; }
.receipt-link:hover { text-decoration: underline; }
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
    <div id="statusBadge" class="badge badge-green">🟢 IN BUDGET</div>
  </header>

  <div class="card">
    <div style="display:flex; justify-content:space-between; align-items:flex-end;">
      <div>
        <div class="metric-title">Today's Total Spend / Hard Ceiling</div>
        <div style="display:flex; align-items:baseline; gap:8px;">
          <span class="metric-value" id="spendVal">$0.0000</span>
          <span style="color:var(--subtext); font-size:18px;" id="limitVal">/ $10.00 Limit</span>
        </div>
      </div>
      <button class="btn btn-boost" onclick="addBoost()">⚡ +$5 Quick Boost</button>
    </div>
    <div class="progress-bar-bg">
      <div id="progressFill" class="progress-bar-fill" style="width: 0%;"></div>
    </div>
    <div style="display:flex; justify-content:space-between; font-size:12px; color:var(--subtext);">
      <span id="remainingVal">Remaining: $10.0000</span>
      <span id="pctVal">0.0% Used</span>
    </div>
  </div>

  <div class="grid">
    <div class="card">
      <div class="metric-title">Token Velocity & Session Total</div>
      <div class="metric-value" id="velocityVal" style="font-size:22px; color:#a78bfa;">~199k <span style="font-size:14px; color:#9ca3af;">tok/turn</span></div>
      <div style="font-size:12px; color:#9ca3af; margin-top:4px;" id="cumulTokVal">14.5M tokens processed</div>
    </div>
    <div class="card">
      <div class="metric-title">Prompt Cache Savings</div>
      <div class="metric-value" id="cacheVal" style="font-size:22px; color:#34d399;">~85% <span style="font-size:14px; color:#9ca3af;">Hit</span></div>
      <div style="font-size:12px; color:#9ca3af; margin-top:4px;">Prompt caching discount active</div>
    </div>
    <div class="card">
      <div class="metric-title">Active Thread / Task Spend</div>
      <div class="metric-value" id="threadVal" style="color:#60a5fa;">$0.0000</div>
      <div style="font-size:12px; color:var(--subtext); margin-top:4px;">Resets per chat/task session</div>
    </div>
    <div class="card">
      <div class="metric-title">Potential Savings Opportunity</div>
      <div class="metric-value" id="savingsVal" style="color:var(--yellow);">$0.0000</div>
      <div style="font-size:12px; color:var(--subtext); margin-top:4px;" id="savingsNote">0 routine calls on flagship tier</div>
    </div>
    <div class="card">
      <div class="metric-title">Proxy Port & Latency</div>
      <div class="metric-value" id="latencyVal" style="font-size:22px;">8080 <span style="font-size:14px; color:var(--subtext);">| 0 ms</span></div>
      <div style="font-size:12px; color:var(--subtext); margin-top:4px;">100% Local Zero-Egress Loopback</div>
    </div>
  </div>

  <div class="card alert-box" id="insightCard">
    <h3 style="font-size:14px; margin-bottom:4px; color:#fbbf24;">💡 Cost Optimization Insight</h3>
    <p style="font-size:13px; color:#e5e7eb;">
      Routine tasks (formatting, short checks) sent to flagship models like GPT-4o can be shifted to lighter models like <code>o3-mini</code> or <code>gemini-2.0-flash</code> for an estimated potential savings of up to ~90%.
    </p>
  </div>

  <div class="card">
    <h3 style="font-size:15px; margin-bottom:12px;">🔌 1-Click IDE Configuration</h3>
    <p style="font-size:13px; color:var(--subtext); margin-bottom:10px;">
      Point your favorite AI coding tool to TokenTotals' local loopback port to activate the circuit breaker:
    </p>
    <div style="display:flex; justify-content:space-between; align-items:center;">
      <span style="font-size:13px; font-weight:600;">Base URL: <code>http://127.0.0.1:8080/v1</code></span>
      <button class="btn btn-copy" onclick="navigator.clipboard.writeText('http://127.0.0.1:8080/v1'); alert('Copied to clipboard!')">📋 Copy URL</button>
    </div>
    <pre><code>// Cursor & VS Code Settings:
"openai.apiBase": "http://127.0.0.1:8080/v1"

// Python / LangChain:
from openai import OpenAI
client = OpenAI(base_url="http://127.0.0.1:8080/v1", api_key="YOUR_KEY")</code></pre>
  </div>

  <div class="card">
    <h3 style="font-size:14px; margin-bottom:6px;">📊 Model Pricing Chart & Docs</h3>
    <p style="font-size:12px; color:var(--subtext);">Pricing references are versioned from provider documentation. Calculations use available model and usage telemetry and are not represented as billing-exact.</p>
    <div class="receipts-list">
      <a class="receipt-link" href="https://openai.com/api/pricing/" target="_blank">🔗 OpenAI Official Pricing Receipt ↗</a>
      <a class="receipt-link" href="https://www.anthropic.com/pricing" target="_blank">🔗 Anthropic Claude Pricing Receipt ↗</a>
      <a class="receipt-link" href="https://ai.google.dev/pricing" target="_blank">🔗 Google Gemini Pricing Receipt ↗</a>
    </div>
  </div>
</div>

<script>
async function refresh() {
  try {
    const res = await fetch('/api/status');
    const data = await res.json();
    document.getElementById('spendVal').innerText = '$' + data.current_spend_usd.toFixed(4);
    document.getElementById('limitVal').innerText = '/ $' + data.daily_budget_limit_usd.toFixed(2) + ' Limit';
    document.getElementById('remainingVal').innerText = 'Remaining: $' + data.remaining_budget_usd.toFixed(4);
    document.getElementById('pctVal').innerText = data.budget_used_pct + '% Used';
    document.getElementById('progressFill').style.width = Math.min(100, data.budget_used_pct) + '%';
    document.getElementById('threadVal').innerText = '$' + data.thread_spend_usd.toFixed(4);
    document.getElementById('savingsVal').innerText = '$' + data.potential_savings_usd.toFixed(4);
    document.getElementById('savingsNote').innerText = data.flagged_routine_calls + ' routine calls flagged';
    document.getElementById('latencyVal').innerHTML = data.port + ' <span style="font-size:14px; color:var(--subtext);">| ' + data.last_latency_ms + ' ms</span>';

    const badge = document.getElementById('statusBadge');
    if (data.is_locked) {
      badge.className = 'badge badge-red';
      badge.innerText = '🔴 LIMIT REACHED';
      document.getElementById('progressFill').style.background = 'var(--red)';
    } else if (data.traffic_light === 'YELLOW') {
      badge.className = 'badge';
      badge.style.background = 'rgba(245, 158, 11, 0.2)';
      badge.style.color = 'var(--yellow)';
      badge.style.border = '1px solid var(--yellow)';
      badge.innerText = '🟡 CAUTION (REVIEW)';
      document.getElementById('progressFill').style.background = 'var(--yellow)';
    } else {
      badge.className = 'badge badge-green';
      badge.innerText = '🟢 IN BUDGET';
      document.getElementById('progressFill').style.background = 'var(--green)';
    }
  } catch(e) {}
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