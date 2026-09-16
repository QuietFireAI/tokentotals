const status = document.getElementById("status");
document.getElementById("health").addEventListener("click", async () => {
  status.textContent = "Checking local TokenTotals engine…";
  const result = await chrome.runtime.sendMessage({type: "TT_ENGINE_HEALTH"});
  status.textContent = result?.ok ? "Local TokenTotals engine is reachable." : `Engine unavailable${result?.error ? `: ${result.error}` : ""}`;
});
