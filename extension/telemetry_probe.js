(() => {
  if (globalThis.__TURNRECEIPT_TELEMETRY_PROBE__) return;
  globalThis.__TURNRECEIPT_TELEMETRY_PROBE__ = true;

  const ALLOWED = new Set([
    "usage", "usageMetadata", "usage_metadata",
    "promptTokenCount", "prompt_token_count", "candidatesTokenCount", "candidates_token_count",
    "responseTokenCount", "response_token_count", "cachedContentTokenCount", "cached_content_token_count",
    "thoughtsTokenCount", "thoughts_token_count", "toolUsePromptTokenCount", "tool_use_prompt_token_count",
    "totalTokenCount", "total_token_count",
    "prompt_tokens", "completion_tokens", "input_tokens", "output_tokens", "total_tokens",
    "prompt_tokens_details", "completion_tokens_details", "input_tokens_details", "output_tokens_details",
    "cache_read_input_tokens", "cache_creation_input_tokens",
    "model", "modelVersion", "model_version", "service_tier",
    "conversation_id", "conversationId", "message_id", "messageId", "response_id", "responseId",
    "turn_id", "turnId"
  ]);

  function sanitize(value, depth = 0) {
    if (depth > 8 || value == null) return undefined;
    if (Array.isArray(value)) {
      const cleaned = value.map(v => sanitize(v, depth + 1)).filter(v => v !== undefined);
      return cleaned.length ? cleaned : undefined;
    }
    if (typeof value !== "object") return undefined;
    const out = {};
    for (const [key, child] of Object.entries(value)) {
      if (ALLOWED.has(key)) {
        if (child && typeof child === "object") out[key] = sanitizeAll(child, depth + 1);
        else if (["string", "number", "boolean"].includes(typeof child)) out[key] = child;
      } else if (child && typeof child === "object") {
        const nested = sanitize(child, depth + 1);
        if (nested && Object.keys(nested).length) Object.assign(out, nested);
      }
    }
    return Object.keys(out).length ? out : undefined;
  }

  function sanitizeAll(value, depth = 0) {
    if (depth > 8 || value == null) return undefined;
    if (Array.isArray(value)) return value.map(v => sanitizeAll(v, depth + 1)).filter(v => v !== undefined);
    if (typeof value !== "object") return ["string", "number", "boolean"].includes(typeof value) ? value : undefined;
    const out = {};
    for (const [key, child] of Object.entries(value)) {
      if (child && typeof child === "object") out[key] = sanitizeAll(child, depth + 1);
      else if (["string", "number", "boolean"].includes(typeof child)) out[key] = child;
    }
    return out;
  }

  function emit(source, url, candidate) {
    const payload = sanitize(candidate);
    if (!payload || !Object.keys(payload).length) return;
    document.dispatchEvent(new CustomEvent("turnreceipt:telemetry", {detail: {
      source,
      url: String(url || "").slice(0, 512),
      captured_at: Date.now(),
      telemetry: payload
    }}));
  }

  async function inspectResponse(source, url, response) {
    try {
      const clone = response.clone();
      const type = clone.headers?.get?.("content-type") || "";
      if (type.includes("json")) {
        emit(source, url, await clone.json());
        return;
      }
      const text = await clone.text();
      if (!text || text.length > 5_000_000) return;
      const trimmed = text.trim();
      if (trimmed.startsWith("{") || trimmed.startsWith("[")) {
        try { emit(source, url, JSON.parse(trimmed)); } catch (_) {}
      }
      for (const line of text.split("\n")) {
        const body = line.startsWith("data:") ? line.slice(5).trim() : line.trim();
        if (!body || (!body.startsWith("{") && !body.startsWith("["))) continue;
        try { emit(source, url, JSON.parse(body)); } catch (_) {}
      }
    } catch (_) {
      // Observation failure must never interfere with the provider page.
    }
  }

  const originalFetch = globalThis.fetch;
  if (typeof originalFetch === "function") {
    globalThis.fetch = async function(...args) {
      const response = await originalFetch.apply(this, args);
      try {
        const url = typeof args[0] === "string" ? args[0] : args[0]?.url;
        inspectResponse("fetch", url, response);
      } catch (_) {}
      return response;
    };
  }

  const originalOpen = XMLHttpRequest.prototype.open;
  const originalSend = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.open = function(method, url, ...rest) {
    this.__turnreceiptUrl = url;
    return originalOpen.call(this, method, url, ...rest);
  };
  XMLHttpRequest.prototype.send = function(...args) {
    this.addEventListener("load", () => {
      try {
        const text = typeof this.responseText === "string" ? this.responseText : "";
        if (!text || text.length > 5_000_000) return;
        const trimmed = text.trim();
        if (trimmed.startsWith("{") || trimmed.startsWith("[")) {
          try { emit("xhr", this.__turnreceiptUrl, JSON.parse(trimmed)); } catch (_) {}
        }
      } catch (_) {}
    }, {once:true});
    return originalSend.apply(this, args);
  };
})();
