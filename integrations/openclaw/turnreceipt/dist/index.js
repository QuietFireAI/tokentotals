import { definePluginEntry } from "openclaw/plugin-sdk/plugin-entry";

const callsByRun = new Map();
const attachedRuns = new Set();
const attachedOrder = [];
const inflightRuns = new Set();
let preferredEngineBase = null;

const MAX_TRACKED_RUNS = 1024;
const MAX_ATTACHED_RUNS = 2048;

function cleanText(value, limit = 512) {
  return String(value ?? "").trim().slice(0, limit);
}

function finiteNumber(value) {
  return typeof value === "number" && Number.isFinite(value) ? value : undefined;
}

function nonnegativeInteger(value) {
  const numeric = finiteNumber(value);
  return numeric === undefined ? undefined : Math.max(0, Math.trunc(numeric));
}

function compactUsage(raw) {
  if (!raw || typeof raw !== "object") return undefined;
  const result = {};
  const input = nonnegativeInteger(raw.input);
  const output = nonnegativeInteger(raw.output);
  const cacheRead = nonnegativeInteger(raw.cacheRead);
  const cacheWrite = nonnegativeInteger(raw.cacheWrite);
  const total = nonnegativeInteger(raw.total);
  if (input !== undefined) result.input = input;
  if (output !== undefined) result.output = output;
  if (cacheRead !== undefined) result.cache_read = cacheRead;
  if (cacheWrite !== undefined) result.cache_write = cacheWrite;
  if (total !== undefined) result.total = total;
  return Object.keys(result).length ? result : undefined;
}

function runCalls(runId) {
  let calls = callsByRun.get(runId);
  if (!calls) {
    calls = new Map();
    callsByRun.set(runId, calls);
    while (callsByRun.size > MAX_TRACKED_RUNS) {
      const oldest = callsByRun.keys().next().value;
      callsByRun.delete(oldest);
    }
  }
  return calls;
}

function rememberStarted(event) {
  const runId = cleanText(event?.runId);
  const callId = cleanText(event?.callId, 256);
  if (!runId || !callId) return;
  runCalls(runId).set(callId, {
    call_id: callId,
    provider: cleanText(event.provider, 128),
    model: cleanText(event.model, 256),
    api: cleanText(event.api, 128) || undefined,
    transport: cleanText(event.transport, 128) || undefined,
  });
}

function rememberEnded(event) {
  const runId = cleanText(event?.runId);
  const callId = cleanText(event?.callId, 256);
  if (!runId || !callId) return;
  const calls = runCalls(runId);
  const existing = calls.get(callId) ?? {};
  calls.set(callId, {
    ...existing,
    call_id: callId,
    provider: cleanText(event.provider, 128) || existing.provider,
    model: cleanText(event.model, 256) || existing.model,
    api: cleanText(event.api, 128) || existing.api,
    transport: cleanText(event.transport, 128) || existing.transport,
    duration_ms: nonnegativeInteger(event.durationMs),
    outcome: cleanText(event.outcome, 64) || undefined,
    error_category: cleanText(event.errorCategory, 128) || undefined,
    failure_kind: cleanText(event.failureKind, 128) || undefined,
    upstream_request_id_hash: cleanText(event.upstreamRequestIdHash, 256) || undefined,
  });
}

function callsFor(runId) {
  return Array.from(callsByRun.get(runId)?.values() ?? []);
}

function markAttached(runId) {
  attachedRuns.add(runId);
  attachedOrder.push(runId);
  while (attachedOrder.length > MAX_ATTACHED_RUNS) {
    const oldest = attachedOrder.shift();
    if (oldest) attachedRuns.delete(oldest);
  }
  callsByRun.delete(runId);
}

function resolveMode(pluginConfig) {
  return pluginConfig?.mode === "expanded" ? "expanded" : "standard";
}

function configuredEngineBase(pluginConfig) {
  const raw = cleanText(pluginConfig?.engineUrl, 1024).replace(/\/+$/, "");
  if (!raw) return undefined;
  try {
    const parsed = new URL(raw);
    if (parsed.protocol !== "http:") return undefined;
    if (parsed.hostname !== "127.0.0.1" && parsed.hostname !== "localhost") return undefined;
    return parsed.origin;
  } catch {
    return undefined;
  }
}

function engineCandidates(pluginConfig) {
  const configured = configuredEngineBase(pluginConfig);
  if (configured) return [configured];
  const candidates = [];
  if (preferredEngineBase) candidates.push(preferredEngineBase);
  for (let port = 8080; port <= 8089; port += 1) {
    const base = `http://127.0.0.1:${port}`;
    if (!candidates.includes(base)) candidates.push(base);
  }
  return candidates;
}

async function postTurn(pluginConfig, payload) {
  let lastError;
  for (const base of engineCandidates(pluginConfig)) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 1500);
    try {
      const response = await fetch(`${base}/api/openclaw/turn`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(payload),
        signal: controller.signal,
      });
      if (!response.ok) {
        throw new Error(`TokenTotals returned HTTP ${response.status}`);
      }
      const body = await response.json();
      preferredEngineBase = base;
      return body;
    } catch (error) {
      lastError = error;
      if (preferredEngineBase === base) preferredEngineBase = null;
    } finally {
      clearTimeout(timer);
    }
  }
  throw lastError ?? new Error("TokenTotals engine unavailable");
}

function buildTurnPayload(event, ctx) {
  const usageState = event.usageState;
  const runId = cleanText(event.runId ?? ctx?.runId);
  const sessionKey = cleanText(event.sessionKey ?? ctx?.sessionKey, 1024);
  if (!runId || !sessionKey || !usageState) return undefined;

  const payload = {
    run_id: runId,
    session_key: sessionKey,
    session_id: cleanText(usageState.sessionId) || undefined,
    provider: cleanText(usageState.provider, 128) || undefined,
    model: cleanText(usageState.model, 256) || undefined,
    resolved_ref: cleanText(usageState.resolvedRef, 512) || undefined,
    requested: cleanText(usageState.requested, 512) || undefined,
    usage: compactUsage(usageState.usage),
    last_usage: compactUsage(usageState.lastUsage),
    runtime_turn_usd: finiteNumber(usageState.turnUsd),
    duration_ms: nonnegativeInteger(usageState.durationMs),
    context_token_budget: nonnegativeInteger(usageState.contextTokenBudget),
    context_used_tokens: nonnegativeInteger(usageState.contextUsedTokens),
    reasoning_effort: cleanText(usageState.reasoningEffort, 64) || undefined,
    fast_mode: typeof usageState.fastMode === "boolean" ? usageState.fastMode : undefined,
    fallback_used: typeof usageState.fallbackUsed === "boolean" ? usageState.fallbackUsed : undefined,
    auth_mode: cleanText(usageState.authMode, 64) || undefined,
    override_source: cleanText(usageState.overrideSource, 128) || undefined,
    model_calls: callsFor(runId),
  };

  return payload;
}

function appendReceiptPresentation(payload, receiptText) {
  // Preserve the model-authored payload.text exactly. The receipt is added as
  // host presentation metadata so OpenClaw can render it beneath the answer or
  // degrade it to deterministic fallback text on channels without native cards.
  const priorPresentation = payload?.presentation;
  const priorBlocks = Array.isArray(priorPresentation?.blocks) ? priorPresentation.blocks : [];
  const blocks = [
    ...priorBlocks,
    ...(priorBlocks.length ? [{ type: "divider" }] : []),
    { type: "context", text: receiptText },
  ];
  return {
    ...payload,
    presentation: {
      ...(priorPresentation ?? {}),
      blocks,
    },
  };
}

export default definePluginEntry({
  id: "turnreceipt",
  name: "TurnReceipt",
  description: "TokenTotals Turn Receipts for OpenClaw",
  register(api) {
    api.on("model_call_started", (event) => {
      rememberStarted(event);
    });

    api.on("model_call_ended", (event) => {
      rememberEnded(event);
    });

    api.on(
      "reply_payload_sending",
      async (event, ctx) => {
        if (event.kind !== "final") return;
        const turn = buildTurnPayload(event, ctx);
        if (!turn) return;
        const runId = turn.run_id;
        if (attachedRuns.has(runId) || inflightRuns.has(runId)) return;

        inflightRuns.add(runId);
        try {
          const settled = await postTurn(api.pluginConfig, turn);
          const mode = resolveMode(api.pluginConfig);
          const receiptText =
            mode === "expanded"
              ? settled.receipt_text_expanded
              : settled.receipt_text_standard;
          if (!receiptText) return;
          markAttached(runId);
          return { payload: appendReceiptPresentation(event.payload, String(receiptText)) };
        } catch (error) {
          console.warn(`TurnReceipt: OpenClaw turn ${runId} was not receipted: ${String(error)}`);
          return;
        } finally {
          inflightRuns.delete(runId);
        }
      },
      { timeoutMs: 5000 },
    );
  },
});
