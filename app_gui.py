import os
import sys
import threading
import time
import webbrowser
import winsound
from pathlib import Path
from PIL import Image
import pystray
import tkinter as tk
from tkinter import messagebox

if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

if hasattr(sys, '_MEIPASS'):
    sys.path.insert(0, sys._MEIPASS)

import config_manager
from proxy_server import app

GLOBAL_ICON = None
CURRENT_ICON_COLOR = "green"
LOCKOUT_WINDOW_ACTIVE = False

def get_resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def load_icon_image(name):
    path = get_resource_path(name)
    if os.path.exists(path):
        return Image.open(path)
    return Image.open(get_resource_path("icon.png"))

def is_port_in_use(port):
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0

def run_server():
    import uvicorn
    conf = config_manager.get_config()
    target_port = conf.get("port", 8080)
    
    # Fallback search if target port is occupied by an old background process
    if is_port_in_use(target_port):
        for p in range(8080, 8090):
            if not is_port_in_use(p):
                target_port = p
                break

    conf["port"] = target_port
    config_manager.save_config(conf)
    uvicorn.run(app, host="127.0.0.1", port=target_port, log_level="critical")

def show_lockout_popup():
    global LOCKOUT_WINDOW_ACTIVE
    if LOCKOUT_WINDOW_ACTIVE:
        return
    LOCKOUT_WINDOW_ACTIVE = True

    try:
        winsound.MessageBeep(winsound.MB_ICONHAND)
    except Exception:
        pass

    root = tk.Tk()
    root.title("🚨 TOKENTOTALS EMERGENCY SHUTDOWN")
    root.geometry("600x440")
    root.resizable(False, False)
    root.attributes('-topmost', True)
    root.configure(bg="#0c0e14")

    # Center window
    root.update_idletasks()
    x = (root.winfo_screenwidth() // 2) - (600 // 2)
    y = (root.winfo_screenheight() // 2) - (440 // 2)
    root.geometry(f"600x440+{x}+{y}")

    state = config_manager.get_state()
    conf = config_manager.get_config()
    spend = state.get("current_spend_usd", 0.0)
    limit = conf.get("daily_budget_limit_usd", 10.0)

    # UI Elements
    header = tk.Label(root, text="🛑 DAILY BUDGET CAP REACHED", font=("Segoe UI", 16, "bold"), fg="#ef4444", bg="#0c0e14")
    header.pack(pady=(24, 8))

    stat_text = f"Spent Today: ${spend:.4f}  /  ${limit:.2f} Daily Limit"
    sub = tk.Label(root, text=stat_text, font=("Segoe UI", 12, "bold"), fg="#f3f4f6", bg="#0c0e14")
    sub.pack(pady=4)

    desc = tk.Label(
        root,
        text="All outgoing AI API calls have been HARD-FROZEN on localhost.\nYour credit card will NOT be billed further while locked.",
        font=("Segoe UI", 10),
        fg="#9ca3af",
        bg="#0c0e14",
        justify="center"
    )
    desc.pack(pady=12)

    ack_label = tk.Label(
        root,
        text="To acknowledge this emergency cutoff, type 'I UNDERSTAND' below:",
        font=("Segoe UI", 10, "bold"),
        fg="#fbbf24",
        bg="#0c0e14"
    )
    ack_label.pack(pady=(12, 4))

    entry_var = tk.StringVar()
    entry = tk.Entry(root, textvariable=entry_var, font=("Segoe UI", 12, "bold"), justify="center", width=24)
    entry.pack(pady=6)
    entry.focus()

    btn_frame = tk.Frame(root, bg="#0c0e14")
    btn_frame.pack(pady=18)

    def do_unlock():
        if entry_var.get().strip().upper() == "I UNDERSTAND":
            config_manager.unlock_circuit_breaker()
            root.destroy()
            open_dashboard(None, None)
        else:
            messagebox.showwarning("Confirmation Required", "Please type exactly 'I UNDERSTAND' to confirm acknowledgment.", parent=root)

    def do_boost():
        config_manager.quick_boost(5.00)
        root.destroy()
        open_dashboard(None, None)

    confirm_btn = tk.Button(
        btn_frame,
        text="🔓 Confirm & Open Dashboard",
        command=do_unlock,
        font=("Segoe UI", 10, "bold"),
        bg="#1f2937",
        fg="#f3f4f6",
        padx=12,
        pady=6,
        cursor="hand2"
    )
    confirm_btn.pack(side="left", padx=8)

    boost_btn = tk.Button(
        btn_frame,
        text="⚡ +$5 Quick Boost Today",
        command=do_boost,
        font=("Segoe UI", 10, "bold"),
        bg="#10b981",
        fg="#000000",
        padx=12,
        pady=6,
        cursor="hand2"
    )
    boost_btn.pack(side="left", padx=8)

    def on_close():
        # Keep locked if user closes window without acknowledging
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()
    LOCKOUT_WINDOW_ACTIVE = False

def monitor_state_loop():
    global GLOBAL_ICON, CURRENT_ICON_COLOR
    while True:
        try:
            time.sleep(2)
            state = config_manager.get_state()
            conf = config_manager.get_config()
            limit = conf.get("daily_budget_limit_usd", 10.0)
            current = state.get("current_spend_usd", 0.0)
            pct = (current / limit * 100) if limit > 0 else 0

            # Traffic light determination
            if state.get("is_locked", False):
                target_color = "red"
                threading.Thread(target=show_lockout_popup, daemon=True).start()
            elif pct >= conf.get("warning_threshold_pct", 75):
                target_color = "yellow"
            else:
                target_color = "green"

            if target_color != CURRENT_ICON_COLOR and GLOBAL_ICON:
                CURRENT_ICON_COLOR = target_color
                GLOBAL_ICON.icon = load_icon_image(f"icon_{target_color}.png")
        except Exception:
            pass

def open_dashboard(icon, item):
    conf = config_manager.get_config()
    port = conf.get("port", 8080)
    webbrowser.open(f"http://127.0.0.1:{port}/dashboard")

def open_settings(icon, item):
    config_manager.init_files()
    os.startfile(str(config_manager.CONFIG_FILE))

def open_bmc(icon, item):
    webbrowser.open("https://buymeacoffee.com/jeffphillips")

def open_docs(icon, item):
    webbrowser.open("https://github.com/QuietFireAI/TokenTotals")

def trigger_quick_boost(icon, item):
    config_manager.quick_boost(5.00)
    if icon:
        icon.notify("Daily budget increased by $5.00", "TokenTotals Quick Boost")

def exit_action(icon, item):
    icon.stop()
    os._exit(0)

def get_status_text(item):
    state = config_manager.get_state()
    conf = config_manager.get_config()
    spend = state.get("current_spend_usd", 0.0)
    limit = conf.get("daily_budget_limit_usd", 10.0)
    if state.get("is_locked"):
        return f"🔴 Limit Reached: ${spend:.4f} / ${limit:.2f}"
    pct = (spend / limit * 100) if limit > 0 else 0
    dot = "🟡" if pct >= 75 else "🟢"
    return f"{dot} In Budget: ${spend:.4f} / ${limit:.2f}"

def on_setup(icon):
    global GLOBAL_ICON
    GLOBAL_ICON = icon
    icon.visible = True
    conf = config_manager.get_config()
    port = conf.get("port", 8080)
    icon.notify(
        f"TokenTotals Proxy Active on http://127.0.0.1:{port}\nClick icon to open Dashboard.",
        "TokenTotals Airbag Online"
    )

def main():
    threading.Thread(target=run_server, daemon=True).start()
    threading.Thread(target=monitor_state_loop, daemon=True).start()

    image = load_icon_image("icon_green.png")

    menu = pystray.Menu(
        pystray.MenuItem("TokenTotals by QuietFireAI", open_dashboard, default=True),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem(get_status_text, open_dashboard),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("📊 Open Web Dashboard", open_dashboard),
        pystray.MenuItem("⚡ +$5 Quick Boost", trigger_quick_boost),
        pystray.MenuItem("⚙️ Open Settings (config.json)", open_settings),
        pystray.MenuItem("📖 How it Works & Security", open_docs),
        pystray.MenuItem("☕ Buy Me a Coffee (buymeacoffee.com/jeffphillips)", open_bmc),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Exit", exit_action)
    )

    icon = pystray.Icon("TokenTotals", image, "TokenTotals", menu)
    icon.run(setup=on_setup)

if __name__ == "__main__":
    main()
