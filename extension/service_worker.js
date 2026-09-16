const ENGINE_BASES = ["http://127.0.0.1:8080", "http://localhost:8080"];

async function engineFetch(path, options = {}) {
  let lastError;
  for (const base of ENGINE_BASES) {
    try {
      return await fetch(`${base}${path}`, {cache: "no-store", ...options});
    } catch (error) {
      lastError = error;
    }
  }
  throw lastError || new Error("TokenTotals engine unavailable");
}

async function renderReceipt(receiptId, mode = "standard") {
  const id = String(receiptId || "").trim();
  if (!id) throw new Error("receiptId required");
  const selected = mode === "expanded" ? "expanded" : "standard";
  const response = await engineFetch(`/api/turn-receipt/${encodeURIComponent(id)}/render?mode=${selected}`);
  if (response.status === 404) return {status: "pending"};
  if (!response.ok) throw new Error(`renderer HTTP ${response.status}`);
  return {status: "ready", html: await response.text()};
}

async function ingestExternalTurn(payload) {
  const response = await engineFetch("/api/external-turn", {
    method: "POST",
    headers: {"content-type": "application/json"},
    body: JSON.stringify(payload)
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`external ingest HTTP ${response.status}: ${detail}`);
  }
  return await response.json();
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (!message || typeof message !== "object") return;
  if (message.type === "TT_RENDER_RECEIPT") {
    renderReceipt(message.receiptId, message.mode).then(sendResponse).catch(error => sendResponse({status:"error", error:String(error)}));
    return true;
  }
  if (message.type === "TT_INGEST_EXTERNAL_TURN") {
    ingestExternalTurn(message.payload).then(sendResponse).catch(error => sendResponse({status:"error", error:String(error)}));
    return true;
  }
  if (message.type === "TT_ENGINE_HEALTH") {
    engineFetch("/api/status").then(r => sendResponse({ok:r.ok,status:r.status})).catch(error => sendResponse({ok:false,error:String(error)}));
    return true;
  }
});
