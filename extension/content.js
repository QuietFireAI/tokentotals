(() => {
  const PROVIDER = location.hostname === "gemini.google.com" ? "google" : location.hostname === "claude.ai" ? "anthropic" : location.hostname === "chatgpt.com" ? "openai" : null;
  if (!PROVIDER) return;

  const telemetryEvents = [];
  const attached = new WeakSet();

  document.addEventListener("turnreceipt:telemetry", event => {
    const detail = event.detail;
    if (!detail || typeof detail !== "object") return;
    telemetryEvents.push(detail);
    while (telemetryEvents.length > 50) telemetryEvents.shift();
  });

  const SELECTORS = {
    openai: [
      'section[data-turn="assistant"]',
      '[data-message-author-role="assistant"]'
    ],
    google: [
      '.model-response',
      '[data-test-id="model-response"]'
    ],
    anthropic: [
      '.font-claude-response',
      '[data-testid="assistant-message"]'
    ]
  };

  function candidates() {
    const seen = new Set();
    const result = [];
    for (const selector of SELECTORS[PROVIDER] || []) {
      for (const node of document.querySelectorAll(selector)) {
        if (!seen.has(node)) {
          seen.add(node);
          result.push(node);
        }
      }
    }
    return result;
  }

  function stableId(node) {
    let current = node;
    for (let depth = 0; current && depth < 6; depth += 1, current = current.parentElement) {
      for (const name of ["data-message-id", "data-turn-id", "data-response-id", "id"]) {
        const value = current.getAttribute?.(name);
        if (value && value.length >= 8 && value.length <= 256) return value;
      }
    }
    return null;
  }

  function threadId() {
    const path = location.pathname.split("/").filter(Boolean);
    return path[path.length - 1] || "current";
  }

  function modelFromTelemetry(telemetry) {
    const queue = [telemetry];
    while (queue.length) {
      const value = queue.shift();
      if (!value || typeof value !== "object") continue;
      for (const [key, child] of Object.entries(value)) {
        if (["model", "modelVersion", "model_version"].includes(key) && typeof child === "string" && child.trim()) return child.trim();
        if (child && typeof child === "object") queue.push(child);
      }
    }
    return null;
  }

  function usageFromTelemetry(telemetry) {
    if (!telemetry || typeof telemetry !== "object") return null;
    if (telemetry.usageMetadata && typeof telemetry.usageMetadata === "object") return telemetry.usageMetadata;
    if (telemetry.usage_metadata && typeof telemetry.usage_metadata === "object") return telemetry.usage_metadata;
    if (telemetry.usage && typeof telemetry.usage === "object") return telemetry.usage;
    for (const child of Object.values(telemetry)) {
      if (child && typeof child === "object") {
        const found = usageFromTelemetry(child);
        if (found) return found;
      }
    }
    return null;
  }

  function sourceIdFromTelemetry(telemetry) {
    const preferred = ["turn_id", "turnId", "response_id", "responseId", "message_id", "messageId"];
    const queue = [telemetry];
    while (queue.length) {
      const value = queue.shift();
      if (!value || typeof value !== "object") continue;
      for (const key of preferred) {
        const child = value[key];
        if ((typeof child === "string" || typeof child === "number") && String(child).trim()) return String(child).trim();
      }
      for (const child of Object.values(value)) if (child && typeof child === "object") queue.push(child);
    }
    return null;
  }

  function matchingTelemetry(nodeId) {
    const cutoff = Date.now() - 120000;
    for (let i = telemetryEvents.length - 1; i >= 0; i -= 1) {
      const event = telemetryEvents[i];
      if (event.captured_at < cutoff) break;
      const telemetry = event.telemetry || {};
      const tid = sourceIdFromTelemetry(telemetry);
      if (nodeId && tid && (nodeId.includes(tid) || tid.includes(nodeId))) return event;
    }
    // Time proximity alone is not enough for exact-turn settlement.
    return null;
  }

  function createHost(node, stateText) {
    const existing = node.nextElementSibling;
    if (existing?.classList?.contains("turnreceipt-host")) return existing;
    const host = document.createElement("div");
    host.className = "turnreceipt-host";
    host.style.cssText = "margin:8px 0 18px;max-width:760px;font:11px 'Courier New',monospace;color:#666";
    host.textContent = stateText;
    node.insertAdjacentElement("afterend", host);
    return host;
  }

  async function process(node) {
    if (attached.has(node)) return;
    const nodeId = stableId(node);
    if (!nodeId) return; // exact-turn identity is mandatory

    const event = matchingTelemetry(nodeId);
    if (!event) return; // do not correlate by timing guess

    const usage = usageFromTelemetry(event.telemetry);
    const model = modelFromTelemetry(event.telemetry);
    const sourceTurnId = sourceIdFromTelemetry(event.telemetry) || nodeId;
    if (!model) return;

    attached.add(node);
    const host = createHost(node, "Settling Turn Receipt…");

    const ingest = await chrome.runtime.sendMessage({
      type: "TT_INGEST_EXTERNAL_TURN",
      payload: {
        provider: PROVIDER,
        model,
        source_turn_id: sourceTurnId,
        source_thread_id: threadId(),
        surface: location.hostname,
        usage: usage || {},
        response_metadata: {model}
      }
    });

    if (!ingest || ingest.status === "error" || !ingest.receipt_id) {
      host.textContent = "Turn Receipt unavailable.";
      return;
    }

    const rendered = await chrome.runtime.sendMessage({
      type: "TT_RENDER_RECEIPT",
      receiptId: ingest.receipt_id,
      mode: "standard"
    });

    if (rendered?.status === "ready") {
      host.innerHTML = rendered.html;
      return;
    }
    host.textContent = "Turn Receipt unavailable.";
  }

  let timer = null;
  const observer = new MutationObserver(() => {
    clearTimeout(timer);
    timer = setTimeout(() => candidates().forEach(node => process(node).catch(() => {})), 250);
  });
  observer.observe(document.documentElement, {subtree:true, childList:true, attributes:true});
  candidates().forEach(node => process(node).catch(() => {}));
})();
