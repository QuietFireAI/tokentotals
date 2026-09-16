const PORTS = [8080,8081,8082,8083,8084,8085,8086,8087,8088,8089];

async function findEngineBase() {
  for (const port of PORTS) {
    const base = `http://127.0.0.1:${port}`;
    try {
      const response = await fetch(`${base}/api/status`, {cache: "no-store"});
      if (response.ok) return base;
    } catch (_) {}
  }
  return null;
}

async function settleExternalTurn(payload) {
  const base = await findEngineBase();
  if (!base) {
    return {status: "engine_unavailable", error: "Local TokenTotals engine was not found on ports 8080-8089."};
  }
  const response = await fetch(`${base}/api/external-turns/settle/render`, {
    method: "POST",
    cache: "no-store",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(payload)
  });
  if (!response.ok) {
    return {status: "error", error: `TokenTotals returned HTTP ${response.status}`, detail: await response.text()};
  }
  const body = await response.json();
  return {status: "ready", ...body, engine_base: base};
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (!message || typeof message !== "object") return;

  if (message.type === "TT_ENGINE_HEALTH") {
    findEngineBase().then((base) => sendResponse({ok: Boolean(base), base}));
    return true;
  }

  if (message.type === "TT_SETTLE_EXTERNAL_TURN") {
    settleExternalTurn(message.payload || {})
      .then(sendResponse)
      .catch((error) => sendResponse({status: "error", error: String(error)}));
    return true;
  }
});
