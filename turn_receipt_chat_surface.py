"""Local chat surface that keeps Turn Receipts in the conversation flow.

This module is presentation-only. It uses the normal TokenTotals OpenAI-compatible
proxy endpoint, then retrieves the canonical rendered receipt by the server-owned
receipt ID returned with that response. API keys are never persisted by this page.
"""

CHAT_HTML = r'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>TokenTotals — Turn Receipt Chat</title>
<style>
:root {
  --bg:#ffffff;
  --ink:#202124;
  --muted:#6b7280;
  --line:#e5e7eb;
  --soft:#f7f7f8;
  --user:#f1f5f9;
  --accent:#111827;
}
* { box-sizing:border-box; }
body {
  margin:0;
  background:var(--bg);
  color:var(--ink);
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
}
.tt-chat-shell { max-width:900px; margin:0 auto; min-height:100vh; display:flex; flex-direction:column; }
.tt-chat-topbar { position:sticky; top:0; z-index:4; background:rgba(255,255,255,.96); backdrop-filter:blur(8px); border-bottom:1px solid var(--line); padding:12px 18px; }
.tt-chat-brand { display:flex; justify-content:space-between; gap:14px; align-items:center; flex-wrap:wrap; }
.tt-chat-brand strong { font-size:15px; letter-spacing:.01em; }
.tt-chat-controls { display:flex; gap:8px; flex-wrap:wrap; align-items:center; }
.tt-chat-controls select,.tt-chat-controls input,.tt-chat-controls button {
  min-height:34px; border:1px solid #d1d5db; border-radius:7px; background:white; color:var(--ink); padding:6px 9px; font:inherit; font-size:12px;
}
.tt-chat-controls select { max-width:260px; }
.tt-chat-controls input[type=password] { width:170px; }
.tt-chat-controls button { cursor:pointer; font-weight:650; }
.tt-chat-controls button:hover { background:var(--soft); }
.tt-chat-meta { margin-top:7px; display:flex; justify-content:space-between; gap:12px; flex-wrap:wrap; font-size:10px; color:var(--muted); }
.tt-chat-transcript { flex:1; padding:26px 18px 160px; }
.tt-chat-turn { margin:0 0 30px; }
.tt-chat-user { display:flex; justify-content:flex-end; margin-bottom:16px; }
.tt-chat-user-bubble { max-width:72%; background:var(--user); border:1px solid #e2e8f0; border-radius:16px 16px 4px 16px; padding:10px 13px; white-space:pre-wrap; line-height:1.5; font-size:14px; }
.tt-chat-assistant { max-width:760px; }
.tt-chat-answer { white-space:pre-wrap; line-height:1.62; font-size:15px; margin-bottom:14px; }
.tt-chat-answer.tt-error { color:#991b1b; }
.tt-chat-receipt-slot { max-width:720px; }
.tt-chat-receipt-pending { font:11px/1.45 "Courier New",Courier,monospace; color:var(--muted); border-top:1px dashed #c9cdd3; padding:8px 0; }
.tt-chat-compose { position:fixed; left:0; right:0; bottom:0; background:linear-gradient(to top,#fff 78%,rgba(255,255,255,0)); padding:30px 18px 18px; }
.tt-chat-compose-inner { max-width:864px; margin:0 auto; border:1px solid #d1d5db; border-radius:14px; background:#fff; box-shadow:0 4px 24px rgba(0,0,0,.07); padding:9px; }
.tt-chat-compose textarea { width:100%; min-height:58px; max-height:180px; resize:vertical; border:0; outline:0; padding:8px 9px; font:14px/1.45 inherit; color:var(--ink); }
.tt-chat-compose-actions { display:flex; justify-content:space-between; align-items:center; gap:10px; }
.tt-chat-compose-note { font-size:10px; color:var(--muted); padding-left:8px; }
.tt-chat-send { border:0; border-radius:9px; background:var(--accent); color:#fff; min-width:72px; min-height:34px; padding:7px 14px; cursor:pointer; font-weight:700; }
.tt-chat-send:disabled { opacity:.45; cursor:not-allowed; }
.tt-chat-empty { color:var(--muted); font-size:13px; text-align:center; padding-top:80px; }
@media(max-width:720px) {
  .tt-chat-user-bubble { max-width:90%; }
  .tt-chat-controls { width:100%; }
  .tt-chat-controls select,.tt-chat-controls input[type=password] { flex:1 1 180px; max-width:none; width:auto; }
}
</style>
</head>
<body>
<div class="tt-chat-shell">
  <header class="tt-chat-topbar">
    <div class="tt-chat-brand">
      <strong>TokenTotals · Turn Receipt Chat</strong>
      <div class="tt-chat-controls">
        <select id="modelSelect" aria-label="Model">
          <option value="">Loading local model registry…</option>
        </select>
        <input id="apiKey" type="password" autocomplete="off" spellcheck="false" placeholder="Provider API key" aria-label="Provider API key">
        <select id="receiptMode" aria-label="Receipt display">
          <option value="standard">Standard receipt</option>
          <option value="expanded">Expanded receipt</option>
        </select>
        <button id="newThreadButton" type="button">New thread</button>
      </div>
    </div>
    <div class="tt-chat-meta">
      <span id="threadLabel">Thread: starting…</span>
      <span>API key stays in this page session and is not written to the Turn Receipt ledger.</span>
    </div>
  </header>

  <main id="transcript" class="tt-chat-transcript">
    <div id="emptyState" class="tt-chat-empty">Ask a question. The answer stays normal; its Turn Receipt appears directly beneath it.</div>
  </main>
</div>

<div class="tt-chat-compose">
  <div class="tt-chat-compose-inner">
    <textarea id="promptInput" placeholder="Message the selected model…" aria-label="Message"></textarea>
    <div class="tt-chat-compose-actions">
      <span class="tt-chat-compose-note">Enter to send · Shift+Enter for a new line</span>
      <button id="sendButton" class="tt-chat-send" type="button">Send</button>
    </div>
  </div>
</div>

<script>
const RECEIPT_HEADER = "X-TokenTotals-Receipt-ID";
const MODE_KEY = "tokentotals.receiptDisplayMode";
const transcript = document.getElementById("transcript");
const emptyState = document.getElementById("emptyState");
const promptInput = document.getElementById("promptInput");
const sendButton = document.getElementById("sendButton");
const modelSelect = document.getElementById("modelSelect");
const apiKeyInput = document.getElementById("apiKey");
const receiptMode = document.getElementById("receiptMode");
const threadLabel = document.getElementById("threadLabel");
let messages = [];
let sending = false;
let threadId = newThreadId();

function newThreadId() {
  if (globalThis.crypto && typeof globalThis.crypto.randomUUID === "function") {
    return `tt-chat-${globalThis.crypto.randomUUID()}`;
  }
  return `tt-chat-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function setThreadLabel() {
  threadLabel.textContent = `Thread: ${threadId}`;
}

function restoreReceiptMode() {
  const saved = localStorage.getItem(MODE_KEY);
  receiptMode.value = saved === "expanded" ? "expanded" : "standard";
}

async function loadModels() {
  try {
    const response = await fetch("/v1/models", {cache:"no-store"});
    if (!response.ok) throw new Error(`model registry returned ${response.status}`);
    const payload = await response.json();
    const entries = Array.isArray(payload.data) ? payload.data : [];
    modelSelect.replaceChildren();
    const first = document.createElement("option");
    first.value = "";
    first.textContent = "Choose a model from the TokenTotals registry";
    modelSelect.append(first);
    for (const entry of entries) {
      const option = document.createElement("option");
      option.value = String(entry.id || "");
      const owner = String(entry.owned_by || "provider");
      option.textContent = `${owner} · ${option.value}${entry.tokentotals_limited_availability ? " · limited availability" : ""}`;
      modelSelect.append(option);
    }
  } catch (error) {
    modelSelect.replaceChildren();
    const option = document.createElement("option");
    option.value = "";
    option.textContent = `Model registry unavailable: ${error.message}`;
    modelSelect.append(option);
  }
}

function addUserTurn(text) {
  if (emptyState) emptyState.remove();
  const turn = document.createElement("section");
  turn.className = "tt-chat-turn";
  const user = document.createElement("div");
  user.className = "tt-chat-user";
  const bubble = document.createElement("div");
  bubble.className = "tt-chat-user-bubble";
  bubble.textContent = text;
  user.append(bubble);
  const assistant = document.createElement("div");
  assistant.className = "tt-chat-assistant";
  turn.append(user, assistant);
  transcript.append(turn);
  return assistant;
}

function addAnswer(assistant, text, isError=false) {
  const answer = document.createElement("div");
  answer.className = `tt-chat-answer${isError ? " tt-error" : ""}`;
  answer.textContent = text;
  assistant.append(answer);
  return answer;
}

function addReceiptSlot(assistant, receiptId) {
  const slot = document.createElement("div");
  slot.className = "tt-chat-receipt-slot";
  slot.dataset.receiptId = receiptId;
  slot.innerHTML = '<div class="tt-chat-receipt-pending">Settling Turn Receipt…</div>';
  assistant.append(slot);
  return slot;
}

function assistantText(message) {
  if (!message) return "";
  const content = message.content;
  if (typeof content === "string") return content;
  if (Array.isArray(content)) {
    return content.map(part => {
      if (typeof part === "string") return part;
      if (part && typeof part.text === "string") return part.text;
      return JSON.stringify(part);
    }).join("\n");
  }
  if (content !== null && content !== undefined) return JSON.stringify(content, null, 2);
  return JSON.stringify(message, null, 2);
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function renderReceiptSlot(slot, mode, attempts=60) {
  const receiptId = slot.dataset.receiptId;
  if (!receiptId) return;
  slot.innerHTML = '<div class="tt-chat-receipt-pending">Settling Turn Receipt…</div>';
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    try {
      const response = await fetch(`/api/turn-receipt/${encodeURIComponent(receiptId)}/render?mode=${encodeURIComponent(mode)}`, {cache:"no-store"});
      if (response.ok) {
        // This fragment is generated by TokenTotals' escaping renderer, not by the model response.
        slot.innerHTML = await response.text();
        return;
      }
      if (response.status !== 404) {
        const detail = await response.text();
        slot.textContent = `Turn Receipt unavailable (${response.status}): ${detail}`;
        return;
      }
    } catch (error) {
      if (attempt === attempts - 1) {
        slot.textContent = `Turn Receipt retrieval failed: ${error.message}`;
        return;
      }
    }
    await sleep(250);
  }
  slot.textContent = `Turn Receipt is still settling. Receipt ID: ${receiptId}`;
}

async function rerenderAllReceipts() {
  const mode = receiptMode.value;
  const slots = Array.from(document.querySelectorAll(".tt-chat-receipt-slot[data-receipt-id]"));
  await Promise.all(slots.map(slot => renderReceiptSlot(slot, mode, 8)));
}

async function sendMessage() {
  if (sending) return;
  const text = promptInput.value.trim();
  const model = modelSelect.value.trim();
  const apiKey = apiKeyInput.value.trim();
  if (!text) return;
  if (!model) {
    promptInput.focus();
    return;
  }
  if (!apiKey) {
    apiKeyInput.focus();
    return;
  }

  sending = true;
  sendButton.disabled = true;
  promptInput.value = "";
  const assistant = addUserTurn(text);
  addAnswer(assistant, "Working…");
  const working = assistant.lastElementChild;
  messages.push({role:"user", content:text});
  transcript.scrollTo({top:transcript.scrollHeight, behavior:"smooth"});

  try {
    const response = await fetch("/v1/chat/completions", {
      method:"POST",
      headers:{
        "Content-Type":"application/json",
        "Authorization":`Bearer ${apiKey}`,
        "X-Thread-ID":threadId,
      },
      body:JSON.stringify({model, messages, stream:false}),
    });
    const body = await response.json().catch(() => ({}));
    working.remove();
    if (!response.ok) {
      const detail = body && body.detail ? body.detail : JSON.stringify(body);
      addAnswer(assistant, `Request failed (${response.status}): ${detail}`, true);
      return;
    }

    const message = body && body.choices && body.choices[0] ? body.choices[0].message : null;
    const textAnswer = assistantText(message);
    addAnswer(assistant, textAnswer || "[No text content returned by the selected model]");
    messages.push({role:"assistant", content:textAnswer});

    const receiptId = response.headers.get(RECEIPT_HEADER);
    if (receiptId) {
      const slot = addReceiptSlot(assistant, receiptId);
      await renderReceiptSlot(slot, receiptMode.value);
    } else {
      const slot = document.createElement("div");
      slot.className = "tt-chat-receipt-pending";
      slot.textContent = "No TokenTotals receipt ID was returned with this response.";
      assistant.append(slot);
    }
  } catch (error) {
    working.remove();
    addAnswer(assistant, `Request failed: ${error.message}`, true);
  } finally {
    sending = false;
    sendButton.disabled = false;
    promptInput.focus();
    transcript.scrollTo({top:transcript.scrollHeight, behavior:"smooth"});
  }
}

function resetThread() {
  messages = [];
  threadId = newThreadId();
  transcript.replaceChildren();
  const empty = document.createElement("div");
  empty.id = "emptyState";
  empty.className = "tt-chat-empty";
  empty.textContent = "New thread. Ask a question; its Turn Receipt will appear under the answer.";
  transcript.append(empty);
  setThreadLabel();
  promptInput.focus();
}

receiptMode.addEventListener("change", async () => {
  localStorage.setItem(MODE_KEY, receiptMode.value === "expanded" ? "expanded" : "standard");
  await rerenderAllReceipts();
});
document.getElementById("newThreadButton").addEventListener("click", resetThread);
sendButton.addEventListener("click", sendMessage);
promptInput.addEventListener("keydown", event => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    sendMessage();
  }
});

restoreReceiptMode();
setThreadLabel();
loadModels();
promptInput.focus();
</script>
</body>
</html>
'''
