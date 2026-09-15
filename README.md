# 🛡️ TokenTotals by QuietFireAI

> **The Local, Open-Source Airbag for AI Developers & Autonomous Agents.**  
> *Real-time cost estimation, local pacing reminders, turn-level telemetry, and a loopback control plane for Cursor, Windsurf, VS Code, and Python agent swarms.*

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Local Control Plane](https://img.shields.io/badge/Security-Local%20Control%20Plane-brightgreen.svg)]()
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey.svg)]()


> [!IMPORTANT]
> **Operational Scope & Liability Disclaimer:** TokenTotals is an independent developer cost calculator, real-time telemetry estimator, and local notification daemon. It calculates estimated spend from available telemetry, provider-published pricing references, and known provider-specific billing rules. TokenTotals is **not a billing mirror**, does **not** guarantee invoice-exact third-party vendor billing alignment, and does not guarantee absolute network-level traffic blocking under all operating system configurations. Users remain responsible for monitoring their direct cloud provider accounts and final provider invoices.

---

## 👁️ Three Ways You Stay Informed: The Look, The Hook, & The Dash

TokenTotals surfaces real-time cost telemetry and local pacing state everywhere you work:

### 1. 🚦 The Look (Glanceable System Tray Icon)
* 🟢 **Green "T":** Below the configured local pacing threshold.
* 🟡 **Amber "T":** Near the configured local pacing threshold.
* 🔴 **Red "T":** Local pacing threshold reached / routed requests locally paused until acknowledged or the local threshold is changed.

### 2. 🪝 The Hook (Turn-by-Turn Chat Telemetry Badge)
A client integration can render TokenTotals telemetry in its own working context. An illustrative shape is:

```text
🟢 Status: Below Local Threshold | Posted Estimate: ~$0.42 / $10.00 threshold | Thread: ~$0.08
🤖 Requested Model: <provider-model-id>
📊 Turn Estimate: ~$0.0006 | Estimate Status: complete / incomplete
💾 Observed Cache / Thinking / Tool Details: <when exposed by provider telemetry>
ℹ️ Pricing Basis: TokenTotals provider registry verified <date>
```

The values above are illustrative UI copy, not a live pricing snapshot. Runtime calculations use the versioned provider registries and the telemetry actually available for each request.

### 3. 📊 The Dash (Localhost Web Dashboard)
Visit `http://127.0.0.1:8080/dashboard` in your browser for:
* Posted local estimated spend, in-flight preflight estimates, and configured local pacing-threshold state.
* Per-thread/task estimated-spend tracking.
* Turn Notice configuration and turn/thread telemetry.
* 1-Click configuration copy for Cursor, VS Code, and Python.
* Provider pricing reference links and local verification receipts.

---

## 💥 The Problem: The "$400 Morning Surprise"

If you build with AI agents (Cursor Composer, Claude Code, CrewAI, AutoGen, or custom LangChain swarms), a recursive reasoning loop, retry storm, or unexpectedly large request can continue consuming provider resources while you are away from your desk.

* **Provider reporting cadence:** Cloud providers can report account usage on a different cadence than a local request stream. A local pacing meter gives you an additional near-real-time signal while work is running.
* **In-flight concurrency:** TokenTotals applies its own preflight pacing check and reserves the known preflight estimate before forwarding a routed request so simultaneous requests do not independently reuse the same known local threshold capacity.
* **Multi-tool visibility:** When multiple scripts and tools route through the same TokenTotals daemon, the local proxy can provide one local estimated-spend and telemetry view for that routed traffic.

---

## 🛡️ The Solution: TokenTotals

TokenTotals runs as a silent, featherweight daemon in your system tray on `http://127.0.0.1:8080`. 

Point your IDE, agent framework, or scripts to `http://127.0.0.1:8080/v1` instead of calling the model endpoint directly. 

```
[ Cursor / Windsurf / Python Scripts / Agent Swarms ]
                       │
                       ▼ (Calls http://127.0.0.1:8080/v1)
            ┌─────────────────────┐
            │  TokenTotals Proxy   │ ──► 1. Pre-flight token/cost estimate
            │   (Local on your PC) │ ──► 2. Checks configured local pacing threshold
            └─────────────────────┘ ──► 3. Preserves the explicitly requested model/provider
                       │
                       ▼ (Forwarded if the local pacing gate allows it)
             [ OpenAI / Anthropic / Google Gemini / other LiteLLM-supported providers ]
```

TokenTotals intentionally does **not** silently replace the model or provider requested by the client. Pricing data alone cannot establish equivalent capabilities, tool or modality support, credentials, context limits, provider policy, or output behavior. Model selection remains with the user or calling application.

Permitted requests still leave the local machine and egress to the selected upstream provider. TokenTotals' control plane, state, ledger, and dashboard are local; TokenTotals does not require a separate TokenTotals-operated telemetry SaaS.

---

## ✨ Key Features

### 1. 🛑 Local Pacing Threshold & Turn Notice
* Before a request is sent, TokenTotals calculates a best-effort input-side preflight estimate and compares it with the configured local pacing threshold.
* If the request would exceed that threshold on its own, TokenTotals rejects that routed request before the upstream completion call and marks the local pacing state locked.
* A topmost desktop modal can require **`"I UNDERSTAND"`** or allow the user to raise the local threshold before routed requests resume.
* **Concurrent post-response accounting:** completed responses are attributed through request-local callback metadata, and local spend/state updates are serialized inside the single TokenTotals daemon so overlapping callbacks do not overwrite one another. Same-day thread totals are maintained independently even when completions arrive out of order.
* **In-flight preflight reservation:** before a permitted request is sent upstream, TokenTotals atomically reserves that request's defensible preflight estimate together with all other active reservations. Two concurrent requests can no longer independently consume the same known local threshold capacity.
* **Temporary contention is not a permanent lock:** if a request fits against posted spend but not against posted spend plus other active reservations, TokenTotals returns `429` and does not send that request upstream. Once the other request settles or fails, capacity under the configured threshold can become available again.
* **Reservation scope is deliberately limited:** the reservation is based on the cost TokenTotals can defensibly estimate before execution—currently the input-side preflight estimate. Output tokens, tools, final service tier, and other response-dependent charges can make the final turn cost higher than the reservation. Actual post-response cost is reconciled when telemetry arrives, and the local pacing state can lock if settled local estimated spend reaches the configured threshold.
* **Turn Notice:** an optional per-turn reminder can fire from a preflight or completed-turn estimate. It is a local notification, not provider-account clearance, a provider balance, or permission to spend.

### 2. 🚦 Traffic Light Glanceable Tray Icon
* 🟢 **Green "T":** Below 75% of the configured local pacing threshold.
* 🟡 **Amber "T":** At or above the configured caution percentage and below the local pacing threshold.
* 🔴 **Red "T":** Local pacing threshold reached / routed requests locally paused.

### 3. 📊 Built-In Web Dashboard
Left-click the tray icon or visit `http://127.0.0.1:8080/dashboard` in your browser to view:
* Posted local estimated spend, in-flight preflight estimate, combined local estimate, and local threshold percentage.
* Per-thread/task estimated-spend tracking.
* Latest-turn and mixed-model thread telemetry with explicit coverage.
* Turn Notice configuration.
* 1-Click configuration copy for major IDE/client workflows.
* Direct receipts and links to provider-published pricing documentation.

### 4. 🧾 Append-Only Local Turn Telemetry Ledger
Completed TokenTotals-routed turns are written to a local runtime append-only JSONL ledger at `~/.tokentotals/turns.jsonl`.

The ledger is deliberately **telemetry-only**. Its writer accepts a whitelisted schema rather than arbitrary request/callback objects. It does not persist prompt text, response text, API keys, or hidden reasoning content.

Where the selected provider exposes or TokenTotals can defensibly derive the field, a turn can preserve:

* requested, canonical, and provider-observed model identifiers as separate values;
* provider and pricing-registry verification date;
* input, uncached input, cached input, cache-write/create, output, reasoning/thinking, and tool-input token categories;
* modality token detail and supported server-tool counters when exposed;
* provider-reported total tokens, TokenTotals reconstructed total, and any unclassified/residual tokens required to reconcile the two;
* latency, requested/observed service-tier information where available;
* estimated cost components, total turn estimate, estimate completeness, and the basis used (`provider_registry_complete`, LiteLLM fallback, known list-equivalent, or unavailable); and
* cumulative local/thread estimated spend after settlement.

**Missing is not zero.** A zero token count means zero was actually observed or defensibly derived. If the provider did not expose a category, the ledger keeps that category unavailable rather than manufacturing `0`.

**One thread can contain multiple models.** Historical summaries are derived from the ledger and preserve separate turn/token/estimated-cost totals per model/provider without resetting the thread when the caller changes models mid-conversation.

The ledger's runtime write path is append-only, but it is an ordinary file owned by the local user; it is not represented as immutable or tamper-evident storage.

### 5. 🔒 Local Control Plane
* **No TokenTotals SaaS Telemetry:** No TokenTotals user account or secondary analytics service is required by the local runtime.
* **Loopback Boundary:** The application listens on loopback and forwards permitted requests to the selected upstream provider through LiteLLM.
* **Upstream Egress Exists:** permitted provider requests necessarily leave localhost and reach the selected provider.
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
    "warning_threshold_pct": 75,
    "turn_notice_threshold_usd": null
}
```

* `daily_budget_limit_usd`: legacy-compatible configuration key for TokenTotals' local daily pacing threshold. It does **not** represent the provider's billing limit, account balance, credit line, or authoritative funds remaining.
* `port`: Local port to bind the proxy server.
* `warning_threshold_pct`: Percentage of the configured local pacing threshold at which the tray indicator changes to caution status.
* `turn_notice_threshold_usd`: Optional positive local per-turn reminder value; `null` disables Turn Notice. It is not a provider-account spending authorization.

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

1. **No Account or Credit Line Access:** TokenTotals does **NOT** query, read, or interface with your credit card, bank account, or internal provider billing portal. It does not know the authoritative provider credit/balance or funds remaining from a proxied request.
2. **Local Best-Effort Estimation:** Dollar metrics such as local posted estimated spend and thread estimated spend are locally computed estimates based on billing-relevant telemetry available to the proxy, combined with versioned provider-published pricing references and known provider-specific rules. They can differ from final invoices because providers may apply cached/cache-write pricing, processing tiers, long-context rules, hosted-tool charges, batch modes, regional or account-specific pricing, negotiated discounts, credits, taxes, delayed or omitted telemetry, and pricing changes.
3. **Pacing, Not Invoicing:** TokenTotals is designed as a local pacing and telemetry layer for development workflows. Its local lock pauses **new requests routed through TokenTotals**. It does not stop direct requests outside TokenTotals, undo provider work already in flight, alter provider-side quotas, or guarantee that additional provider billing cannot occur. The provider's final invoice and account records remain authoritative.
4. **Model Integrity:** TokenTotals does not infer that a cheaper model is an equivalent substitute for the model a client requested. Automatic model/provider downgrade routing was retired; model choice remains explicit.
5. **Concurrency Scope:** Post-response accounting is serialized within the normal single local TokenTotals daemon and uses request-local callback attribution. Preflight estimates for active requests are reserved atomically inside that daemon so simultaneous requests cannot consume the same known local threshold capacity. This is not a distributed transaction system, and the reservation covers the preflight estimate rather than unknown final full-turn charges.

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

TokenTotals' local-control-plane architecture can be useful in environments where adding a separate cloud-hosted FinOps/observability service is undesirable or infeasible. Any deployment must still perform its own security, compliance, authorization, and accreditation review.

Potential use cases include:
* **Cost Accountability:** Local per-task cost estimates and attribution for AI development/pilot workflows routed through the proxy.
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
