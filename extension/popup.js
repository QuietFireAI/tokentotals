const status = document.getElementById("status");

async function check() {
  status.textContent = "Checking local TokenTotals…";
  try {
    const result = await chrome.runtime.sendMessage({type: "TT_ENGINE_HEALTH"});
    status.textContent = result?.ok
      ? `TokenTotals engine found at ${result.base}. Receipts can settle locally.`
      : "TokenTotals engine not found on ports 8080-8089.";
  } catch (error) {
    status.textContent = `TokenTotals check failed: ${String(error)}`;
  }
}

document.getElementById("check").addEventListener("click", check);
check();
