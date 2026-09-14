# 🛡️ TokenTotals by QuietFireAI

> **The Local, Open-Source Airbag for AI Developers & Autonomous Agents.**  
> *Hard-stop budget protection, local zero-egress proxying, and cost-optimization advisory for Cursor, Windsurf, VS Code, and Python agent swarms.*

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Zero Egress](https://img.shields.io/badge/Security-Zero--Egress%20Localhost-brightgreen.svg)]()
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey.svg)]()

---

## 💥 The Problem: The "$400 Morning Surprise"

If you build with AI agents (Cursor Composer, Claude Code, CrewAI, AutoGen, or custom LangChain swarms), you know the nightmare:
An agent enters a recursive reasoning loop or a retry storm while you are away from your desk. 

* **The 24-Hour Reporting Lag:** Cloud providers (OpenAI, Anthropic) delay their billing dashboards by 1 to 24 hours. By the time you get the warning email, your credit card has already been billed hundreds of dollars.
* **In-Flight Streams Bypass Caps:** Soft provider spend limits rarely terminate an active streaming generation mid-sentence.
* **Multi-Tool Blindspot:** When running 5 different scripts and tools sharing one API key, there is no single dashboard on your machine tracking your total burn rate.

---

## 🛡️ The Solution: TokenTotals

TokenTotals runs as a silent, featherweight daemon in your system tray on `http://127.0.0.1:8080`. 

Point your IDE, agent framework, or scripts to `http://127.0.0.1:8080/v1` instead of calling `api.openai.com` directly. 

```
[ Cursor / Windsurf / Python Scripts / Agent Swarms ]
                       │
                       ▼ (Calls http://127.0.0.1:8080/v1)
            ┌─────────────────────┐
            │  TokenTotals Proxy   │ ──► 1. Pre-flight BPE token count & budget audit
            │   (Local on your PC) │ ──► 2. Checks Daily Cap ($10.00) & Thread Spend
            └─────────────────────┘ ──► 3. Calculates Potential Savings vs Flash/Mini
                       │
                       ▼ (Forwarded directly if under budget)
             [ OpenAI / Anthropic / Google Gemini ]
```

---

## ✨ Key Features

### 1. 🛑 The "Dead Man's Switch" Hard Stop
* The microsecond a request would breach your daily limit (default: \$10.00), outgoing traffic is **hard-frozen** before provider bandwidth is consumed.
* An un-ignorable, topmost desktop modal pops up with an audio alert.
* Requires typing **`"I UNDERSTAND"`** or clicking **`[ +$5 Quick Boost ]`** to unlock.

### 2. 🚦 Traffic Light Glanceable Tray Icon
* 🟢 **Green "T":** Under 75% of daily budget (Cruising safely).
* 🟡 **Amber "T":** 75%–99% of budget (Heads up, heavy agent usage today).
* 🔴 **Red "T":** 100% Breached / Locked (Circuit breaker engaged, zero egress).

### 3. 📊 Built-In Web Dashboard
Left-click the tray icon or visit `http://127.0.0.1:8080/dashboard` in your browser to view:
* Live Spend Fuel Gauge & remaining dollar headroom.
* Per-thread/task spend tracking.
* **Potential Savings Opportunity Meter:** Identifies when flagship models (GPT-4o) were used for routine/short queries that could have used lighter models for ~90% savings.
* 1-Click configuration copy for all major IDEs.
* Direct receipts and links to official provider pricing documentation.

### 4. 🔒 Zero-Egress Architecture
* **Zero Telemetry:** No tracking, no user accounts, no external analytics.
* **Direct Encryption:** HTTPS requests travel directly from `127.0.0.1` to the vendor's API. No middleman servers ever touch your keys.
* **100% Free & Open Source:** Licensed under **GNU GPLv3**.

---

## 🚀 Quickstart

### 1. Run the Executable (Windows)
Download the latest `TokenTotals_Windows_v2.4.zip` from Releases, unzip, and run:
`TokenTotals_QuietFireAI.exe`

A green "T" will appear in your system tray, and the proxy will start listening on port 8080.

### 2. Configure Your Tools

#### Cursor / VS Code:
1. Open Cursor Settings (`Ctrl + ,` or `Cmd + ,`).
2. Search for `OpenAI Base URL`.
3. Set the Base URL to:
   ```
   http://127.0.0.1:8080/v1
   ```
4. Enter your regular OpenAI / Anthropic API key as usual.

#### Python / LangChain:
```python
from openai import OpenAI

client = OpenAI(
    base_url="http://127.0.0.1:8080/v1",
    api_key="your-api-key-here"
)

response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Hello world"}]
)
```

---

## ⚙️ Configuration (`~/.tokentotals/config.json`)

```json
{
    "daily_budget_limit_usd": 10.0,
    "port": 8080,
    "auto_economy_mode": false,
    "warning_threshold_pct": 75
}
```

* `daily_budget_limit_usd`: Your hard spending cap for the calendar day.
* `port`: Local port to bind the proxy server.
* `auto_economy_mode`: If set to `true`, automatically remaps routine/simple prompts to `gpt-4o-mini` or `gemini-2.0-flash`. (Default: `false` - advisory only).

---


---

## 📊 The Live Telemetry View (Included in Every Turn & Dashboard)

TokenTotals provides deep, un-obfuscated visibility into your AI session health across both the Web Dashboard and your development chat:

```text
🟢 Status: In Budget | Today: $0.42 / $10.00 | Thread: $0.08  
📊 Turn: ~$0.0910 (🧠 1.2k think / 💬 380 out) | 💾 Cache Savings: ~95%  
⚡ Velocity: ~208k tok/turn (16.2M total) | 📈 Session Total: $13.23 USD (78 turns)  
🪟 Context Window: 33.46% (350.8k / 1M max limit) | 🤖 Model: Gemini 3.7 Flash  
ℹ️ Pricing: $0.15 In / $0.60 Out per 1M | [Pricing Chart & Docs](https://github.com/QuietFireAI/TokenTotals#pricing)
```

---

## 🤝 Open Source Community: Fork It & Make It Yours!

TokenTotals is released under the **GNU General Public License v3.0 (GPLv3)**. 

We encourage developers, researchers, and community builders to:
* **Fork the repo** and experiment with your own custom local heuristic rules.
* **Build custom adapters** for local LLMs (Ollama, LM Studio, vLLM).
* **Craft your own telemetry dashboards** and share your widgets with the community.
* **Submit PRs** to expand provider support and add new safety circuit-breaker triggers.


---

## ⚖️ Operational Scope & Billing Disclaimer

> **IMPORTANT: TokenTotals is an Observability & Pacing Governor, Not an Upstream Account Portal.**

1. **No Account or Credit Line Access:** TokenTotals does **NOT** query, read, or interface with your credit card, bank account, or internal provider billing portals (e.g. OpenAI Billing Dashboard or Anthropic Console). We do not touch your actual account balances or credits.
2. **Local Contextual Estimation:** All dollar metrics (Today's Spend, Thread Spend, Potential Savings) are **locally computed mathematical estimates** based on the raw token payloads passing through this local proxy, calculated against official published vendor pricing catalogs.
3. **Pacing & Protection, Not Invoicing:** TokenTotals acts as an on-the-wire airbag and telemetry monitor for your development workflow. It does not replace or modify your official end-of-month provider billing statements.

## 📜 License & Trust

Distributed under the **GNU General Public License v3.0 (GPLv3)**. See `LICENSE` for details.

Built by **QuietFireAI**. Support independent open-source AI safety tools at:  
☕ [buymeacoffee.com/jeffphillips](https://buymeacoffee.com/jeffphillips)
