# 🛡️ TokenTotals by QuietFireAI

> **The Local, Open-Source Airbag for AI Developers & Autonomous Agents.**  
> *Real-time cost estimation, budget notification, and advisory alerts, local zero-egress proxying, and real-time cost telemetry for Cursor, Windsurf, VS Code, and Python agent swarms.*

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Localhost Only](https://img.shields.io/badge/Security-Zero--Egress%20Localhost-brightgreen.svg)]()
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey.svg)]()


> [!IMPORTANT]
> **Operational Scope & Liability Disclaimer:** TokenTotals is an independent developer cost calculator, real-time telemetry estimator, and local notification daemon. It calculates estimated spend based on published provider rates and notifies developers when custom threshold limits are met. TokenTotals **does not** guarantee exact third-party vendor billing alignment, nor does it guarantee absolute network-level traffic blocking under all operating system configurations. Users remain solely responsible for monitoring their direct cloud provider accounts.

---

## 👁️ Three Ways You Stay Protected: The Look, The Hook, & The Dash

TokenTotals surfaces real-time cost transparency and budget enforcement everywhere you work:

### 1. 🚦 The Look (Glanceable System Tray Icon)
* 🟢 **Green "T":** In Budget (Cruising safely).
* 🟡 **Amber "T":** 75%–99% of daily budget (Heads up, heavy agent usage today).
* 🔴 **Red "T":** 100% Limit Reached / Budget Threshold Alert Engaged (Desktop modal alert requiring `"I UNDERSTAND"` or `[ +$5 Quick Boost ]`).

### 2. 🪝 The Hook (Turn-by-Turn Chat Telemetry Badge)
Every single developer turn or agent interaction renders a clean, live telemetry badge directly in your working context:

```text
🟢 Status: In Budget | Today: $0.42 / $10.00 | Thread: $0.08
📊 🤖 Model: Gemini 3.7 Flash (gemini-3.7-flash)
📊 Turn: ~$0.0006 (🧠 42 think / 💬 610 out) | 💾 Cache Savings: ~95%
⚡ Velocity: ~262.1k tok/turn (28.8M total) | 📈 Session Total: $22.68 USD (109 turns)
🪟 Context Window: 42.84% (449.2k / 1M max limit)
ℹ️ Pricing Verification: In $0.15 / Out $0.60 per 1M | Public Sync: 2026-09-09
```

### 3. 📊 The Dash (Localhost Web Dashboard)
Visit `http://127.0.0.1:8080/dashboard` in your browser for:
* Live Spend Fuel Gauge & dollar headroom.
* Per-thread/task spend tracking.
* 1-Click configuration copy for Cursor, VS Code, and Python.
* Verified provider pricing documentation receipts.

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

### 1. 🛑 The Advisory Budget Threshold & Alert
* The microsecond a request would breach your daily limit (default: \$10.00), TokenTotals triggers an advisory pause and pops an un-ignorable desktop notification alert.
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
* **Potential Savings Opportunity Meter:** Identifies when flagship models (GPT-5) were used for routine/short queries that could have used lighter models for ~90% savings.
* 1-Click configuration copy for all major IDEs.
* Direct receipts and links to official provider pricing documentation.

### 4. 🔒 Localhost-Only Architecture
* **Zero Telemetry:** No tracking, no user accounts, no external analytics.
* **Direct Encryption:** HTTPS requests travel directly from `127.0.0.1` to the vendor's API. No middleman servers ever touch your keys.
* **100% Free & Open Source:** Licensed under **GNU GPLv3**.

---

## 🚀 Quickstart

### 1. Run the Executable (Windows)
Download the latest `TokenTotals_Windows_v2.8.zip` from Releases, unzip, and run:
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
* `auto_economy_mode`: If set to `true`, automatically remaps routine/simple prompts to `o3-mini` or `gemini-2.0-flash`. (Default: `false` - advisory only).

---



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


---

---


---

## 📊 Standardized Cross-Platform Pricing Comparison (Developer API Stack)

TokenTotals normalizes all LLM costs across **Anthropic** (**Claude 3.7 Sonnet**), **OpenAI** (**o1** / **GPT-5** / **GPT-5-mini**), and **Google** (**Gemini 3.6 / 3.7 Flash** / **Gemini 2.5 Pro**):

### Standard Turn Cost (10,000 Input / 2,000 Output Tokens)

| Provider | Model | Tier | Standard Turn Cost | Multiplier vs. Baseline |
| :--- | :--- | :--- | :--- | :--- |
| **OpenAI** | OpenAI o1 | Frontier | **$0.2700** | **200.0x** |
| **Anthropic** | Claude 3.7 Sonnet | Frontier | **$0.0600** | **44.4x** |
| **OpenAI** | OpenAI GPT-5 | Workhorse | **$0.0450** | **33.3x** |
| **Google** | Gemini 2.5 Pro | Frontier | **$0.0325** | **24.1x** |
| **Google** | Gemini 3.6 / 3.7 Flash | Workhorse | **$0.0150** | **11.1x** |
| **Anthropic** | Claude 3.5 Haiku | Economy | **$0.0160** | **11.8x** |
| **OpenAI** | OpenAI GPT-5-mini | Economy | **$0.0027** | **2.0x** |
| **Google** | Gemini 2.0 Flash-Lite | Economy | **$0.00135** | **1.0x (Baseline)** |

*For complete details, see [MODEL_COMPARISON_MATRIX.md](MODEL_COMPARISON_MATRIX.md).*


## 🔍 The Data Was There All Along

Every single API response from OpenAI, Anthropic, and Google already contains everything you need to calculate your exact spend in real time:

```json
// What the API already returns in EVERY response:
{
  "usage": {
    "prompt_tokens": 34521,        // <-- They KNEW how many tokens you sent
    "completion_tokens": 1847,     // <-- They KNEW how many they generated
    "prompt_tokens_details": {
      "cached_tokens": 32768       // <-- They KNEW you were being cached at 90% discount
    }
  }
}
```

The pricing per million tokens is published on their public websites. The math is grade-school multiplication:

```
(tokens / 1,000,000) x price_per_million = your_cost
```

**That is all TokenTotals does.** It reads the numbers the providers were already sending you, multiplies by their own published prices, and shows you the running total they chose not to.

> *The frontier AI labs raised $50 billion to build Artificial General Intelligence that can write poetry, pass the bar exam, and design microchips... but somehow, none of them built a gas gauge.*

TokenTotals exists because an independent developer got tired of waiting.

---

## 🏛️ Government, Defense & Enterprise

TokenTotals' localhost-only architecture is uniquely suited for environments where cloud-based FinOps tools are prohibited or infeasible:

### Why Government & Defense Need This:
* **OMB Budget Accountability:** Federal agencies running AI pilots on GPT-5 or Claude for document processing, intelligence analysis, or citizen services face Congressional audit scrutiny on every line item. TokenTotals provides per-task cost attribution without transmitting classified or sensitive data off-machine.
* **FedRAMP & FISMA Compliance:** Cloud SaaS FinOps tools (Portkey, Helicone, Langfuse) require years of security certification before deployment in federal environments. A local, zero-egress tool that never transmits data off the machine sails through compliance review.
* **Air-Gapped & Classified Networks (SCIFs):** Defense and intelligence community workloads on air-gapped networks literally *cannot* use cloud dashboards. A local loopback proxy is the only architecture that works.

### Commercial Enterprise Licensing:
TokenTotals is free and open-source (GPLv3) for individual developers and open-source projects.

For **government contractors, federal system integrators, and enterprise teams** that require proprietary licensing, SLA-backed support, compliance documentation, and audit trail exports:

📧 **Contact:** quietfireai@gmail.com  
🔗 **ORCID:** [0009-0000-1375-1725](https://orcid.org/0009-0000-1375-1725)

## 📜 License & Trust

Distributed under the **GNU General Public License v3.0 (GPLv3)**. See `LICENSE` for details.

Built by **QuietFireAI**. Support independent open-source AI safety tools at:  
☕ [buymeacoffee.com/jeffphillips](https://buymeacoffee.com/jeffphillips)
