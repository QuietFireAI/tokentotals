const ENGINE_BASES = [
  "http://127.0.0.1:8080",
  "http://localhost:8080"
];

async function engineFetch(path, options = {}) {
  let lastError = null;
  for (const base of ENGINE_BASES) {
    try {
      return await fetch(`${base}${path}`, { cache: "no-store", ...options });
    } catch (error) {
      lastError = error;
    }
  }
  throw lastError || new Error("TokenTotals engine unavailable");
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
    engineFetch("/dashboard")
      .then((r) => sendResponse({ ok: r.ok, status: r.status }))
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
