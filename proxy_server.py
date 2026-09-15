import json
import os
import sys
from typing import Any

from runtime_compat import require_supported_python

require_supported_python()

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
    return input_tokens, output_tokens


def _message_text(messages: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for message in messages:
        content = message.get("content", "") if isinstance(message, dict) else ""
        if isinstance(content, str):
            parts.append(content)
        elif isinstance(content, list):
            for item in content:
                if isinstance(item, dict):
                    text = item.get("text")
                    if isinstance(text, str):
                        parts.append(text)
    return "\n".join(parts)


def _requested_output_tokens(body: dict[str, Any]) -> int | None:
    for field in ("max_completion_tokens", "max_tokens"):
        raw = body.get(field)
        if raw is not None:
            try:
                return max(0, int(raw))
            except (TypeError, ValueError):
                raise HTTPException(status_code=422, detail=f"{field} must be an integer")
    return None


def _economy_model_for(model: str) -> str:
    lower = model.lower()
    if lower.startswith("openai/") or lower.startswith("gpt-"):
        return "gpt-5.6-luna"
    if lower.startswith("anthropic/") or lower.startswith("claude-"):
        return "claude-haiku-4.5"
    if lower.startswith("google/") or lower.startswith("gemini-"):
        return "gemini-3.1-flash-lite"
    return model


def _require_ack(payload: dict[str, Any], expected: str) -> None:
    if payload.get("acknowledgment") != expected:
        raise HTTPException(status_code=400, detail=f"acknowledgment must be exactly: {expected}")


@app.get("/v1/models")
async def list_supported_models():
    return {
        "object": "list",
        "data": [
            {"id": record["model"], "object": "model", "owned_by": record["provider"]}
            for record in pricing_models()
        ],
    }


@app.get("/api/status")
async def api_status():
    conf = config_manager.get_config()
    catalog = load_catalog()
    return {
        "locked": bool(conf.get("locked", False)),
        "daily_spend": float(conf.get("daily_spend", 0.0)),
        "daily_budget": float(conf.get("daily_budget", 0.0)),
        "thread_spend": float(conf.get("thread_spend", 0.0)),
        "thread_budget": float(conf.get("thread_budget", 0.0)),
        "unreconciled_streams": int(conf.get("unreconciled_streams", 0)),
        "pricing_verified_at": catalog.get("verified_at"),
    }


@app.post("/api/boost")
async def api_boost(payload: dict[str, Any]):
    _require_ack(payload, "BOOST $5")
    conf = config_manager.get_config()
    conf["daily_budget"] = float(conf.get("daily_budget", 0.0)) + 5.0
    conf["locked"] = False
    config_manager.save_config(conf)
    return {"status": "ok", "daily_budget": conf["daily_budget"]}


@app.post("/api/unlock")
async def api_unlock(payload: dict[str, Any]):
    _require_ack(payload, "I UNDERSTAND")
    conf = config_manager.get_config()
    conf["locked"] = False
    config_manager.save_config(conf)
    return {"status": "ok", "message": "Circuit breaker unlocked after explicit acknowledgment."}


@app.get("/")
async def dashboard():
    conf = config_manager.get_config()
    catalog = load_catalog()
    verified = catalog.get("verified_at", "unknown")
    return HTMLResponse(
        f"""
        <!doctype html>
        <html>
          <head><title>TokenTotals</title></head>
          <body>
            <h1>TokenTotals</h1>
            <p>Local budget guard and usage estimator.</p>
            <p>Pricing verified: {verified}</p>
            <p>Pricing receipts:</p>
            <ul>
              <li><a href="https://developers.openai.com/api/docs/pricing">OpenAI</a></li>
              <li><a href="https://platform.claude.com/docs/en/about-claude/pricing">Anthropic</a></li>
              <li><a href="https://cloud.google.com/gemini-enterprise-agent-platform/generative-ai/pricing">Google</a></li>
            </ul>
            <p>Daily spend: ${float(conf.get('daily_spend', 0.0)):.4f}</p>
            <p>Daily budget: ${float(conf.get('daily_budget', 0.0)):.2f}</p>
            <p>Unreconciled streams: {int(conf.get('unreconciled_streams', 0))}</p>
          </body>
        </html>
        """
    )


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    body = await request.json()
    requested_model = str(body.get("model") or "").strip()
    if not requested_model:
        raise HTTPException(status_code=422, detail="model is required")

    conf = config_manager.get_config()
    if conf.get("locked", False):
        raise HTTPException(status_code=403, detail="TokenTotals circuit breaker is locked")

    model = requested_model
    if conf.get("auto_economy", False):
        economy = _economy_model_for(requested_model)
        if economy != requested_model:
            model = economy

    try:
        pricing = resolve_model(model)
    except UnknownModelPrice as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    messages = body.get("messages") or []
    estimated_input_tokens = estimate_text_tokens(_message_text(messages))
    requested_output_tokens = _requested_output_tokens(body)

    if requested_output_tokens is None:
        requested_output_tokens = affordable_output_tokens(
            pricing,
            estimated_input_tokens,
            float(conf.get("remaining_budget", lambda: 0.0)())
            if callable(conf.get("remaining_budget"))
            else max(0.0, min(
                float(conf.get("daily_budget", 0.0)) - float(conf.get("daily_spend", 0.0)),
                float(conf.get("thread_budget", 0.0)) - float(conf.get("thread_spend", 0.0)),
            )),
        )

    reservation = calculate_cost(
        pricing,
        estimated_input_tokens,
        requested_output_tokens,
        conservative=True,
    )["total_cost_usd"]

    reservation_result = config_manager.try_reserve_spend(reservation)
    if not reservation_result.get("ok"):
        raise HTTPException(status_code=403, detail=reservation_result.get("reason", "Budget exceeded"))

    upstream_body = dict(body)
    upstream_body["model"] = model
    if "max_completion_tokens" not in upstream_body and "max_tokens" not in upstream_body:
        upstream_body["max_tokens"] = requested_output_tokens

    try:
        response = await litellm.acompletion(**upstream_body)
    except Exception:
        config_manager.reconcile_spend(reservation, 0.0)
        raise

    if body.get("stream"):
        config_manager.mark_unreconciled_stream()
        return StreamingResponse(response, media_type="text/event-stream")

    input_tokens, output_tokens = _usage_from_response(response)
    actual_estimate = calculate_cost(pricing, input_tokens, output_tokens)["total_cost_usd"]
    config_manager.reconcile_spend(reservation, actual_estimate)
    return response


if __name__ == "__main__":
    import uvicorn

    conf = config_manager.get_config()
    uvicorn.run(app, host="127.0.0.1", port=int(conf.get("port", 8080)))
