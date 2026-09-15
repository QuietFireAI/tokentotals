# 🛡️ TokenTotals by QuietFireAI

> **The Local, Open-Source Airbag for AI Developers & Autonomous Agents.**  
> *Real-time cost estimation, budget notification, and advisory alerts, local zero-egress proxying, and real-time cost telemetry for Cursor, Windsurf, VS Code, and Python agent swarms.*

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Localhost Only](https://img.shields.io/badge/Security-Zero--Egress%20Localhost-brightgreen.svg)]()
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey.svg)]()


> [!IMPORTANT]
> **Operational Scope & Liability Disclaimer:** TokenTotals is an independent developer cost calculator, real-time telemetry estimator, and local notification daemon. It calculates estimated spend from available telemetry, provider-published pricing references, and known provider-specific billing rules. TokenTotals is **not a billing mirror**, does **not** guarantee invoice-exact third-party vendor billing alignment, and does not guarantee absolute network-level traffic blocking under all operating system configurations. Users remain responsible for monitoring their direct cloud provider accounts and final provider invoices.

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
ℹ️ Current Pricing: In $0.15 / Out $0.60 per 1M | Public Sync: 2026-09-09
```

### 3. 📊 The Dash (Localhost Web Dashboard)
Visit `http://127.0.0.1:8080/dashboard` in your browser for:
* Live Spend Fuel Gauge & dollar headroom.
* Per-thread/task spend tracking.
* 1-Click configuration copy for Cursor, VS Code, and Python.
* Provider pricing reference links and local verification receipts.

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
            │  TokenTotals Proxy   │ ──► 1. Pre-flight token estimate & budget audit
            │   (Local on your PC) │ ──► 2. Checks Daily Cap ($10.00) & Thread Spend
            └─────────────────────┘ ──► 3. Preserves the explicitly requested model/provider
                       │
                       ▼ (Forwarded directly if under budget)
             [ OpenAI / Anthropic / Google Gemini ]
```

TokenTotals intentionally does **not** silently replace the model or provider requested by the client. Pricing data alone cannot establish equivalent capabilities, tool or modality support, credentials, context limits, provider policy, or output behavior. Model selection remains with the user or calling application.

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
* 1-Click configuration copy for all major IDEs.
* Direct receipts and links to provider-published pricing documentation.

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
    "warning_threshold_pct": 75
}
```

* `daily_budget_limit_usd`: Your local daily estimated-spend threshold used by TokenTotals' pacing logic. It is not the provider's billing limit.
* `port`: Local port to bind the proxy server.
* `warning_threshold_pct`: Percentage of the local daily threshold at which the tray indicator changes to caution status.

Older local config files may still contain an `auto_economy_mode` key from earlier releases. Current TokenTotals ignores that retired key and does not automatically remap requested models.

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

> **IMPORTANT: TokenTotals is an Observability & Pacing Governor, Not an Upstream Account Portal or Billing Mirror.**

1. **No Account or Credit Line Access:** TokenTotals does **NOT** query, read, or interface with your credit card, bank account, or internal provider billing portals (e.g. OpenAI Billing Dashboard or Anthropic Console). We do not touch your actual account balances or credits.
2. **Local Best-Effort Estimation:** Dollar metrics such as Today's Spend and Thread Spend are locally computed estimates based on billing-relevant telemetry available to the proxy, combined with versioned provider-published pricing references and known provider-specific rules. They can differ from final invoices because providers may apply cached/cache-write pricing, processing tiers, long-context rules, hosted-tool charges, batch modes, regional or account-specific pricing, negotiated discounts, credits, taxes, delayed or omitted telemetry, and pricing changes.
3. **Pacing & Protection, Not Invoicing:** TokenTotals is designed as a local airbag and telemetry monitor for development workflows. It does not replace, modify, or claim to reproduce provider billing statements. The provider's final invoice and account records remain authoritative.
4. **Model Integrity:** TokenTotals does not infer that a cheaper model is an equivalent substitute for the model a client requested. Automatic model/provider downgrade routing was retired; model choice remains explicit.


---

---


---

## 📊 Standardized Cross-Platform Pricing Comparison (Developer API Stack)

TokenTotals includes dated, standardized comparison examples across **Anthropic**, **OpenAI**, and **Google**. These examples are useful for relative cost comparison; they are not runtime billing mirrors and are not permanent price guarantees.

### Example Turn Cost (10,000 Input / 2,000 Output Tokens)

| Provider | Model | Tier | Example Turn Estimate | Multiplier vs. Baseline |
| :--- | :--- | :--- | :--- | :--- |
| **OpenAI** | OpenAI o1 | Frontier | **$0.2700** | **200.0x** |
| **Anthropic** | Claude 3.7 Sonnet | Frontier | **$0.0600** | **44.4x** |
| **OpenAI** | GPT-4o | Workhorse | **$0.0450** | **33.3x** |
| **Google** | Gemini 2.5 Pro | Frontier | **$0.0325** | **24.1x** |
| **OpenAI** | o3-mini | Reasoning | **$0.0198** | **14.7x** |
| **Anthropic** | Claude 3.5 Haiku | Economy | **$0.0160** | **11.9x** |
| **OpenAI** | GPT-4o-mini | Economy | **$0.0027** | **2.0x** |
| **Google** | Gemini 2.0 Flash | Workhorse | **$0.0018** | **1.33x** |
| **Google** | Gemini 2.0 Flash-Lite | Economy | **$0.00135** | **1.0x (Baseline)** |

*For assumptions and the dated snapshot boundary, see [MODEL_COMPARISON_MATRIX.md](MODEL_COMPARISON_MATRIX.md).*


## 🔍 Use the Billing Data That Is Actually Available

LLM APIs often return important billing inputs such as token counts, cache usage, model identity, and sometimes processing metadata. Those fields are extremely useful—but they are **not necessarily the complete provider invoice model**.

A simplified response may look like:

```json
{
  "usage": {
    "prompt_tokens": 34521,
    "completion_tokens": 1847,
    "prompt_tokens_details": {
      "cached_tokens": 32768
    }
  }
}
```

Where the required inputs are known, the arithmetic is deterministic:

```
(tokens / 1,000,000) x applicable_rate = estimated_component_cost
```

But modern AI pricing increasingly resembles cloud infrastructure pricing rather than a single gas-pump rate. The applicable cost may depend on multiple categories and modifiers: uncached input, cached input, cache writes, output/reasoning tokens, service or processing tier, long-context thresholds, hosted tools, batch processing, regional or account pricing, negotiated contracts, credits, taxes, and provider-side adjustments.

**That is the job TokenTotals is designed to do:** observe the telemetry that is available, apply versioned provider pricing rules and known modifiers, show the resulting estimate and its assumptions, and avoid inventing precision when a billing dimension is missing.

Think of it more like an AWS-style near-real-time cost meter than a clone of the provider's accounts-receivable system. The estimate can become very close when the telemetry and rules are complete; the provider's invoice remains the final authority.

> *The frontier AI labs raised billions to build systems that can write poetry, pass professional exams, and design software. Developers still deserve a better fuel gauge while those systems are running.*

TokenTotals exists to provide that local fuel gauge.

---

## 🏛️ Government, Defense & Enterprise

TokenTotals' localhost-only architecture is designed for environments where cloud-based FinOps tools may be prohibited or infeasible:

### Why Government & Defense May Need This:
* **Budget Accountability:** Agencies running AI pilots can benefit from local per-task cost estimates and attribution without sending additional telemetry to a separate FinOps service.
* **Compliance-Sensitive Environments:** A local architecture can reduce the amount of operational telemetry sent to additional third-party observability services, although each deployment must still complete its own security, compliance, authorization, and accreditation review.
* **Restricted Networks:** Where a permitted model endpoint is reachable but external observability SaaS is not, a local loopback proxy can provide an additional local monitoring layer.

### Commercial Enterprise Licensing:
TokenTotals is free and open-source (GPLv3) for individual developers and open-source projects.

For **government contractors, federal system integrators, and enterprise teams** that require proprietary licensing, SLA-backed support, compliance documentation, and audit trail exports:

📧 **Contact:** quietfireai@gmail.com  
🔗 **ORCID:** [0009-0000-1375-1725](https://orcid.org/0009-0000-1375-1725)

## 📜 License & Trust

Distributed under the **GNU General Public License v3.0 (GPLv3)**. See `LICENSE` for details.

Built by **QuietFireAI**. Support independent open-source AI safety tools at:  
☕ [buymeacoffee.com/jeffphillips](https://buymeacoffee.com/jeffphillips)
