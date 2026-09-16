(() => {
  const HOST_CLASS = "tt-external-receipt-host";
  const SETTLE_DELAY_MS = 1400;
  const seenElements = new WeakSet();
  let scanTimer = null;

  const SITE = (() => {
    const host = location.hostname;
    if (host === "gemini.google.com") {
      return {
        surface: "gemini_web",
        provider: "google",
        assistantSelectors: ["model-response", ".model-response", "[data-test-id='model-response']"],
        userSelectors: ["user-query", ".user-query", "[data-test-id='user-query']"],
        streamingSelectors: ["button[aria-label*='Stop' i]", "[aria-busy='true']"],
        contentSelectors: [".markdown", ".model-response-text", "message-content", "[class*='response-content']"],
        modelHints: [/Gemini\s+[\w. -]+/i, /\b(?:Flash|Pro)\b/i]
      };
    }
    if (host === "chatgpt.com") {
      return {
        surface: "chatgpt_web",
        provider: "openai",
        assistantSelectors: ["[data-message-author-role='assistant']", "[data-role='assistant']", ".agent-turn"],
        userSelectors: ["[data-message-author-role='user']", "[data-role='user']", ".user-turn"],
        streamingSelectors: ["button[data-testid='stop-button']", "button[aria-label*='Stop' i]"],
        contentSelectors: [".markdown", ".prose", "[class*='markdown']"],
        modelHints: [/GPT[-\s]?[\w.]+/i, /\bo[134](?:[-\w.]*)?/i]
      };
    }
    if (host === "claude.ai") {
      return {
        surface: "claude_web",
        provider: "anthropic",
        assistantSelectors: ["[data-testid='assistant-message']", ".font-claude-response", "[data-is-streaming]"],
        userSelectors: ["[data-testid='user-message']"],
        streamingSelectors: ["[data-is-streaming='true']", "button[aria-label*='Stop' i]"],
        contentSelectors: [".font-claude-response", ".prose", "[class*='markdown']"],
        modelHints: [/Claude\s+[\w. -]+/i]
      };
    }
    return null;
  })();

  if (!SITE) return;

  function queryAll(selectors) {
    const found = [];
    const unique = new Set();
    for (const selector of selectors) {
      try {
        for (const node of document.querySelectorAll(selector)) {
          if (!unique.has(node)) {
            unique.add(node);
            found.push(node);
          }
        }
      } catch (_) {}
    }
    return found;
  }

  function isGenerating() {
    return SITE.streamingSelectors.some((selector) => {
      try { return Boolean(document.querySelector(selector)); } catch (_) { return false; }
    });
  }

  function cleanText(node) {
    if (!node) return "";
    let target = node;
    for (const selector of SITE.contentSelectors) {
      try {
        const candidate = node.matches?.(selector) ? node : node.querySelector?.(selector);
        if (candidate) { target = candidate; break; }
      } catch (_) {}
    }
    return String(target.innerText || target.textContent || "").trim();
  }

  function closestPreviousUserText(assistant) {
    const users = queryAll(SITE.userSelectors);
    let best = null;
    for (const user of users) {
      const relation = user.compareDocumentPosition(assistant);
      if (relation & Node.DOCUMENT_POSITION_FOLLOWING) best = user;
    }
    return cleanText(best);
  }

  function threadIdentity() {
    return `${SITE.surface}:${location.pathname}${location.search}`;
  }

  function elementIdentity(element, index) {
    const attrs = [
      "data-message-id", "data-turn-id", "data-testid", "id"
    ];
    for (const name of attrs) {
      const value = element.getAttribute?.(name);
      if (value && String(value).trim()) return `${SITE.surface}:${name}:${value}`;
    }
    const text = cleanText(element);
    return `${SITE.surface}:dom:${index}:${text.slice(0, 180)}`;
  }

  function detectModel() {
    const candidates = [];
    const selectors = [
      "button[aria-label*='model' i]",
      "[data-testid*='model' i]",
      "[data-test-id*='model' i]",
      "header button",
      "main button"
    ];
    for (const selector of selectors) {
      try {
        document.querySelectorAll(selector).forEach((node) => {
          const text = String(node.innerText || node.textContent || node.getAttribute?.("aria-label") || "").trim();
          if (text) candidates.push(text);
        });
      } catch (_) {}
    }
    for (const candidate of candidates) {
      for (const pattern of SITE.modelHints) {
        const match = candidate.match(pattern);
        if (match) return match[0].trim();
      }
    }
    return "";
  }

  function hostFor(answer) {
    const next = answer.nextElementSibling;
    if (next?.classList?.contains(HOST_CLASS)) return next;
    const host = document.createElement("div");
    host.className = HOST_CLASS;
    host.dataset.turnreceiptState = "settling";
    host.textContent = "Settling Turn Receipt…";
    answer.insertAdjacentElement("afterend", host);
    return host;
  }

  async function settle(answer, index) {
    if (!answer.isConnected || seenElements.has(answer)) return;
    const answerText = cleanText(answer);
    if (!answerText) return;
    seenElements.add(answer);

    const host = hostFor(answer);
    const payload = {
      surface: SITE.surface,
      provider: SITE.provider,
      model_id: detectModel(),
      external_thread_id: threadIdentity(),
      external_turn_id: elementIdentity(answer, index),
      completed_at: new Date().toISOString(),
      visible_user_text: closestPreviousUserText(answer),
      visible_assistant_text: answerText,
      receipt_mode: "standard"
    };

    let result;
    try {
      result = await chrome.runtime.sendMessage({type: "TT_SETTLE_EXTERNAL_TURN", payload});
    } catch (error) {
      result = {status: "error", error: String(error)};
    }

    if (result?.status === "ready" && result.html) {
      // HTML is produced by TokenTotals' escaping renderer, not by provider prose.
      host.innerHTML = result.html;
      host.dataset.turnreceiptState = "ready";
      host.dataset.receiptId = result.receipt_id || "";
      return;
    }

    host.dataset.turnreceiptState = result?.status || "unavailable";
    host.innerHTML = `<div class="tt-external-receipt-unavailable">Turn Receipt unavailable — ${escapeText(result?.error || "local TokenTotals engine did not settle this turn")}</div>`;
  }

  function escapeText(value) {
    return String(value).replace(/[&<>"']/g, (char) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;"
    }[char]));
  }

  function scan() {
    if (isGenerating()) return;
    const assistants = queryAll(SITE.assistantSelectors);
    assistants.forEach((answer, index) => {
      if (answer.closest?.(`.${HOST_CLASS}`)) return;
      if (seenElements.has(answer)) return;
      window.setTimeout(() => {
        if (!isGenerating()) settle(answer, index);
      }, SETTLE_DELAY_MS);
    });
  }

  function scheduleScan() {
    clearTimeout(scanTimer);
    scanTimer = setTimeout(scan, 350);
  }

  const observer = new MutationObserver(scheduleScan);
  observer.observe(document.documentElement, {
    childList: true,
    subtree: true,
    characterData: true,
    attributes: true,
    attributeFilter: ["data-is-streaming", "aria-busy"]
  });

  window.addEventListener("popstate", scheduleScan);
  window.addEventListener("hashchange", scheduleScan);
  scheduleScan();
})();
