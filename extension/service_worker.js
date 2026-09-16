const ENGINE_BASES = [];
for (let port = 8080; port <= 8089; port += 1) {
  ENGINE_BASES.push(`http://127.0.0.1:${port}`);
}

let resolvedEngineBase = null;

async function engineFetch(path, options = {}) {
  const candidates = resolvedEngineBase
    ? [resolvedEngineBase, ...ENGINE_BASES.filter((base) => base !== resolvedEngineBase)]
    : ENGINE_BASES;
  let lastError = null;

  for (const base of candidates) {
    try {
      const response = await fetch(`${base}${path}`, { cache: "no-store", ...options });
      // A reachable TokenTotals endpoint may legitimately return 4xx; remember
      // the port once TCP/HTTP succeeds so later calls remain on one engine.
      resolvedEngineBase = base;
      return response;
    } catch (error) {
      lastError = error;
    }
  }
  throw lastError || new Error("TokenTotals engine unavailable on ports 8080-8089");
}

async function fetchRenderedReceipt(receiptId, mode = "standard") {
  const id = String(receiptId || "").trim();
  if (!id) throw new Error("receiptId is required");
  const selected = mode === "expanded" ? "expanded" : "standard";
  const response = await engineFetch(
    `/api/turn-receipt/${encodeURIComponent(id)}/render?mode=${encodeURIComponent(selected)}`
  );
  if (response.status === 404) return { status: "pending" };
  if (!response.ok) throw new Error(`TokenTotals renderer returned HTTP ${response.status}`);
  return { status: "ready", html: await response.text() };
}

async function ingestExternalTurn(payload) {
  const response = await engineFetch("/api/external-turn", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload || {})
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(body.detail || `External-turn ingest returned HTTP ${response.status}`);
  }
  return body;
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (!message || typeof message !== "object") return;

  if (message.type === "TT_ENGINE_HEALTH") {
    engineFetch("/api/status")
      .then((r) => sendResponse({ ok: r.ok, status: r.status, base: resolvedEngineBase }))
      .catch((e) => sendResponse({ ok: false, error: String(e) }));
    return true;
  }

  if (message.type === "TT_RENDER_RECEIPT") {
    fetchRenderedReceipt(message.receiptId, message.mode)
      .then(sendResponse)
      .catch((e) => sendResponse({ status: "error", error: String(e) }));
    return true;
  }

  if (message.type === "TT_INGEST_EXTERNAL_TURN") {
    ingestExternalTurn(message.payload)
      .then(sendResponse)
      .catch((e) => sendResponse({ status: "error", error: String(e) }));
    return true;
  }
});
