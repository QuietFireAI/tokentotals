import os
import json
import time
import urllib.request
import threading
from datetime import datetime, date
from pathlib import Path
from config_manager import APP_DIR, get_state, save_state

PRICING_FILE = APP_DIR / "model_prices.json"
REMOTE_PRICING_URL = "https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json"

def fetch_live_pricing():
    """Fetch live pricing catalog from upstream registry and persist locally."""
    try:
        req = urllib.request.Request(
            REMOTE_PRICING_URL, 
            headers={"User-Agent": "TokenTotals-FinOps/2.5 (Zero-Egress-Localhost)"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode('utf-8'))
                with open(PRICING_FILE, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2)
                
                # Update last sync timestamp in state
                state = get_state()
                state["last_pricing_sync"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                save_state(state)
                print(f"[TokenTotals Sync] Successfully updated live pricing catalog ({len(data)} models) at {state['last_pricing_sync']}")
                return True
    except Exception as e:
        print(f"[TokenTotals Sync Warning] Could not fetch live remote pricing: {e}. Using cached catalog.")
        return False

def get_pricing_catalog():
    """Return local cached pricing catalog or fallback to LiteLLM bundled catalog."""
    if PRICING_FILE.exists():
        try:
            with open(PRICING_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    
    # Fallback to LiteLLM bundled cost dictionary
    try:
        import litellm
        return litellm.model_cost
    except Exception:
        return {}

def _sync_loop():
    """Background daemon thread running daily auto-sync every 24 hours."""
    while True:
        fetch_live_pricing()
        # Sleep 24 hours (86,400 seconds)
        time.sleep(86400)

def start_daily_sync_daemon():
    """Start the background daily sync thread."""
    state = get_state()
    last_sync = state.get("last_pricing_sync")
    should_fetch = False
    
    if not last_sync or not PRICING_FILE.exists():
        should_fetch = True
    else:
        try:
            last_date = datetime.strptime(last_sync, "%Y-%m-%d %H:%M:%S").date()
            if last_date < date.today():
                should_fetch = True
        except Exception:
            should_fetch = True
            
    if should_fetch:
        t_init = threading.Thread(target=fetch_live_pricing, daemon=True)
        t_init.start()

    t_daemon = threading.Thread(target=_sync_loop, daemon=True)
    t_daemon.start()

if __name__ == "__main__":
    fetch_live_pricing()
