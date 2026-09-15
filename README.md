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
A client integration can render TokenTotals telemetry in its own working context. An illustrative shape is:

```text
🟢 Status: In Budget | Today: ~$0.42 / $10.00 | Thread: ~$0.08
🤖 Requested Model: <provider-model-id>
📊 Turn Estimate: ~$0.0006 | Estimate Status: complete / incomplete
💾 Observed Cache / Thinking / Tool Details: <when exposed by provider telemetry>
ℹ️ Pricing Basis: TokenTotals provider registry verified <date>
```

The values above are illustrative UI copy, not a live pricing snapshot. Runtime calculations use the versioned provider registries and the telemetry actually available for each request.

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

* **The 24-Hour Reporting Lag:** Cloud providers can report account usage on a different cadence than a local request stream. A local pacing meter gives you an additional near-real-time signal while work is running.
* **In-Flight Streams Bypass Caps:** Provider-side controls and active request behavior can differ; TokenTotals applies its own preflight pacing check before forwarding a request.
* **Multi-Tool Blindspot:** When running multiple scripts and tools sharing API credentials, a local proxy can provide one local estimated-spend view for traffic routed through it.

---

## 🛡️ The Solution: TokenTotals

TokenTotals runs as a silent, featherweight daemon in your system tray on `http://127.0.0.1:8080`. 

Point your IDE, agent framework, or scripts to `http://127.0.0.1:8080/v1` instead of calling the model endpoint directly. 

```
[ Cursor / Windsurf / Python Scripts / Agent Swarms ]
                       │
                       ▼ (Calls http://127.0.0.1:8080/v1)
            ┌─────────────────────┐
            │  TokenTotals Proxy   │ ──► 1. Pre-flight token estimate & budget audit
            │   (Local on your PC) │ ──► 2. Checks Daily Cap ($10.00) & Thread Spend
            └─────────────────────┘ ──► 3. Preserves the explicitly requested model/provider
                       │
                       ▼ (Forwarded if the local pacing gate allows it)
             [ OpenAI / Anthropic / Google Gemini / other LiteLLM-supported providers ]
```

TokenTotals intentionally does **not** silently replace the model or provider requested by the client. Pricing data alone cannot establish equivalent capabilities, tool or modality support, credentials, context limits, provider policy, or output behavior. Model selection remains with the user or calling application.

---

## ✨ Key Features

### 1. 🛑 The Advisory Budget Threshold & Alert
* Before a request is sent, TokenTotals calculates a best-effort input-side preflight estimate and compares it with the configured local daily threshold.
* If the request would exceed that local threshold, TokenTotals rejects it before the upstream completion call and marks the local state locked.
* A topmost desktop modal can require **`"I UNDERSTAND"`** or **`[ +$5 Quick Boost ]`** to resume.

### 2. 🚦 Traffic Light Glanceable Tray Icon
* 🟢 **Green "T":** Under 75% of daily budget.
* 🟡 **Amber "T":** 75%–99% of budget.
* 🔴 **Red "T":** Local estimated-spend threshold reached / locked.

### 3. 📊 Built-In Web Dashboard
Left-click the tray icon or visit `http://127.0.0.1:8080/dashboard` in your browser to view:
* Live Spend Fuel Gauge & remaining dollar headroom.
* Per-thread/task spend tracking.
* 1-Click configuration copy for all major IDEs.
* Direct receipts and links to provider-published pricing documentation.

### 4. 🔒 Localhost-Only Architecture
* **No TokenTotals SaaS Telemetry:** No TokenTotals user account or secondary analytics service is required by the local runtime.
* **Local Proxy Boundary:** The application listens on loopback and forwards permitted requests to the selected upstream provider through LiteLLM.
* **100% Free & Open Source:** Licensed under **GNU GPLv3**.

---

## 🚀 Quickstart

### 1. Run the Executable (Windows)
Download the latest TokenTotals Windows release, unzip it, and run the TokenTotals executable.

A green "T" will appear in your system tray, and the proxy will start listening on the configured local port.

### 2. Configure Your Tools

#### Cursor / VS Code:
1. Open your client settings.
2. Locate its OpenAI-compatible Base URL setting.
3. Set the Base URL to:
   ```
   http://127.0.0.1:8080/v1
   ```
4. Configure the appropriate provider/API credentials required by the client and upstream model.

#### Python / OpenAI-compatible client:
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

The `model` field is required. TokenTotals does not infer a default model.

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

## 💵 Pricing Architecture: Versioned Provider Rules, Not a Second Billing Portal

TokenTotals keeps provider-specific machine-readable pricing rules under [`pricing/`](pricing/). Those registries—not a hand-maintained comparison table in this README—are the repo-contained pricing source used by the dedicated OpenAI, Anthropic, and Google/Gemini calculators.

Current registry files:

* [`pricing/openai_registry.json`](pricing/openai_registry.json)
* [`pricing/anthropic_registry.json`](pricing/anthropic_registry.json)
* [`pricing/google_registry.json`](pricing/google_registry.json)

Each registry records its verification date, provider documentation sources, modeled scope, model aliases/rates, and relevant exceptions. The calculators combine those rules with observable response telemetry. If a billing-relevant dimension cannot be resolved, TokenTotals prefers an explicitly incomplete estimate over fabricated precision.

For a provider outside the dedicated engines, preflight may use an **exact model key** from the pinned LiteLLM catalog as a disclosed secondary estimate. If no defensible preflight price exists, the request is rejected rather than assigned a universal fallback rate.

See [MODEL_COMPARISON_MATRIX.md](MODEL_COMPARISON_MATRIX.md) for a human-readable comparison of the **billing mechanics** TokenTotals models across providers. It intentionally does not duplicate another static model-price leaderboard.

---

## 🤝 Open Source Community: Fork It & Make It Yours!

TokenTotals is released under the **GNU General Public License v3.0 (GPLv3)**. 

We encourage developers, researchers, and community builders to:
* **Fork the repo** and experiment with your own custom local rules.
* **Build custom adapters** for local LLMs (Ollama, LM Studio, vLLM).
* **Craft your own telemetry dashboards** and share your widgets with the community.
* **Submit PRs** to expand provider support and add new safety circuit-breaker triggers.

---

## ⚖️ Operational Scope & Billing Disclaimer

> **IMPORTANT: TokenTotals is an Observability & Pacing Governor, Not an Upstream Account Portal or Billing Mirror.**

1. **No Account or Credit Line Access:** TokenTotals does **NOT** query, read, or interface with your credit card, bank account, or internal provider billing portal. It does not know the authoritative remaining provider credit/balance from a proxied request.
2. **Local Best-Effort Estimation:** Dollar metrics such as Today's Spend and Thread Spend are locally computed estimates based on billing-relevant telemetry available to the proxy, combined with versioned provider-published pricing references and known provider-specific rules. They can differ from final invoices because providers may apply cached/cache-write pricing, processing tiers, long-context rules, hosted-tool charges, batch modes, regional or account-specific pricing, negotiated discounts, credits, taxes, delayed or omitted telemetry, and pricing changes.
3. **Pacing & Protection, Not Invoicing:** TokenTotals is designed as a local airbag and telemetry monitor for development workflows. It does not replace, modify, or claim to reproduce provider billing statements. The provider's final invoice and account records remain authoritative.
4. **Model Integrity:** TokenTotals does not infer that a cheaper model is an equivalent substitute for the model a client requested. Automatic model/provider downgrade routing was retired; model choice remains explicit.

---

## 🔍 Use the Billing Data That Is Actually Available

LLM APIs often return important billing inputs such as token counts, cache usage, model identity, and sometimes processing metadata. Those fields are extremely useful—but they are **not necessarily the complete provider invoice model**.

A simplified normalized response may look like:

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

Provider-native telemetry can contain additional categories that must be interpreted separately. For example, Google/Gemini may expose cache, thinking, tool-use prompt, total-token, and modality-specific detail; Anthropic exposes cache read/write categories and can have geography/tier/tool particulars; OpenAI has its own cache, tier, context, modality, and hosted-tool rules.

Where a required billing component and its rate are known, the arithmetic is straightforward:

```
(billable_units / 1,000,000) x applicable_rate = estimated_component_cost
```

But modern AI pricing increasingly resembles cloud infrastructure pricing rather than a single gas-pump rate. The applicable cost may depend on multiple categories and modifiers: uncached input, cached input, cache writes, output/reasoning tokens, service or processing tier, long-context thresholds, hosted tools, batch processing, regional or account pricing, negotiated contracts, credits, taxes, and provider-side adjustments.

**That is the job TokenTotals is designed to do:** observe the telemetry that is available, apply versioned provider pricing rules and known modifiers, show the resulting estimate and its assumptions, and avoid inventing precision when a billing dimension is missing.

Think of it more like an AWS-style near-real-time cost meter than a clone of the provider's accounts-receivable system. The estimate can become very close when the telemetry and rules are complete; the provider's invoice remains the final authority.

> *Developers deserve a better local fuel gauge while AI systems are running.*

TokenTotals exists to provide that local fuel gauge.

---

## 🏛️ Government, Defense & Enterprise

TokenTotals' localhost-only architecture can be useful in environments where adding a separate cloud-hosted FinOps/observability service is undesirable or infeasible. Any deployment must still perform its own security, compliance, authorization, and accreditation review.

Potential use cases include:
* **Budget Accountability:** Local per-task cost estimates and attribution for AI development/pilot workflows routed through the proxy.
* **Compliance-Sensitive Environments:** Avoiding an additional TokenTotals-operated telemetry SaaS while still using the selected upstream model provider.
* **Restricted Observability Topologies:** A local monitoring layer where the authorized provider endpoint is reachable but an additional observability SaaS is not approved.

### Commercial Enterprise Licensing
TokenTotals is free and open-source under GPLv3. Organizations requiring different licensing, support, or documentation can contact QuietFireAI.

📧 **Contact:** quietfireai@gmail.com  
🔗 **ORCID:** [0009-0000-1375-1725](https://orcid.org/0009-0000-1375-1725)

## 📜 License & Trust

Distributed under the **GNU General Public License v3.0 (GPLv3)**. See `LICENSE` for details.

Built by **QuietFireAI**. Support independent open-source AI safety tools at:  
☕ [buymeacoffee.com/jeffphillips](https://buymeacoffee.com/jeffphillips)
