# 🛡️ TokenTotals by QuietFireAI

> **The Local, Open-Source Turn-Receipt & Pacing Layer for AI Developers & Autonomous Agents.**  
> *Turn Receipts. Show Your Math. Missing Is Not Zero.*

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Local Control Plane](https://img.shields.io/badge/Security-Local%20Control%20Plane-brightgreen.svg)]()
[![Desktop](https://img.shields.io/badge/Desktop-Windows-lightgrey.svg)]()

> [!IMPORTANT]
> **Operational Scope & Liability Disclaimer:** TokenTotals is an independent developer cost calculator, real-time telemetry estimator, and local notification daemon. It calculates estimated spend from available telemetry, provider-published pricing references, and known provider-specific billing rules. TokenTotals is **not a billing mirror**, does **not** guarantee invoice-exact third-party vendor billing alignment, and does not guarantee absolute network-level traffic blocking under all operating system configurations. Users remain responsible for monitoring their direct cloud provider accounts and final provider invoices.

---

## 🔬 Open Turn Receipts That Show Their Work

TokenTotals is an **independent, open-source information layer** for telemetry legitimately exposed through supported model-provider APIs, SDKs, and response metadata. TokenTotals does not own that telemetry and does not need private provider access to use it. It normalizes the pieces, preserves them turn by turn, applies documented pricing mechanics, reconciles what does and does not add up, and shows the arithmetic.

The ingredients have often been available to software. TokenTotals' premise is simple: **if the numbers are available to the application, the person generating—and paying for—the call should be able to understand them too.**

A few examples of the actual math behind a TokenTotals turn receipt:

```text
estimated_component_cost
    = (billable_units / 1,000,000)
    × applicable_rate_per_million
```

```text
reconciliation_delta_tokens
    = provider_reported_total_tokens
    - reconstructed_total_tokens

unclassified_tokens
    = max(0, reconciliation_delta_tokens)
```

```text
classified_token_share_pct
    = ((provider_reported_total_tokens - unclassified_tokens)
       / provider_reported_total_tokens)
    × 100
```

That last percentage describes **token-classification coverage, not invoice accuracy**. TokenTotals keeps those concepts separate on purpose.

The full proof sheet documents both **metrics calculated today** and **additional metrics already calculable from the current local ledger but intentionally not surfaced yet**, with prerequisites, formulas, coverage rules, and explicit boundaries for what TokenTotals will not claim.

➡️ **[Open the full Calculation Transparency proof sheet →](CALCULATION_TRANSPARENCY.md)**  
➡️ **[Challenge or improve a formula →](CONTRIBUTING.md)**  
➡️ **[Inspect verification receipts—including failures →](archive/verification-receipts/)**

### Why a Turn Receipt is different

TokenTotals is deliberately **not** trying to become a full tracing, evals, routing, or enterprise-observability suite. Its unit of explanation is narrower: **the completed LLM turn**.

A TokenTotals Turn Receipt is designed to answer:

> **What happened on this turn, what did the provider actually expose, what did TokenTotals derive from it, what could not be established, and can I verify the arithmetic myself?**

That means the receipt can place the following facts side by side instead of collapsing them into a single opaque usage or dollar number:

* **provider-reported total tokens** versus **TokenTotals reconstructed total tokens**;
* the resulting **unclassified / residual token count** when those totals do not reconcile;
* an explicit basis for telemetry fields: **observed, derived, or unavailable**;
* an explicit **cost basis**: complete provider-registry calculation, disclosed fallback, known list-equivalent, or unavailable;
* the **component arithmetic** and provider pricing rule used to construct the estimate;
* a **local append-only turn record** rather than a transient display value;
* mixed-provider and mixed-model history without discarding the surrounding thread; and
* a direct path from the displayed metric to the documented formula and testable assumptions behind it.

**Observability and Turn Receipts can coexist.** If another system already handles routing, traces, evals, or production monitoring, TokenTotals can remain a local receipt-and-pacing layer focused on making the economics and telemetry of each routed turn inspectable.

The distinction is intentional: **TokenTotals does not merely display telemetry; it shows whether the available telemetry explains itself.**

---

## 👁️ Three Ways You Stay Informed: The Look, The Hook, & The Dash

TokenTotals surfaces real-time cost telemetry and local pacing state where you work:

### 1. 🚦 The Look (Glanceable System Tray Icon)
* 🟢 **Green "T":** Below the configured local pacing threshold.
* 🟡 **Amber "T":** Near the configured local pacing threshold.
* 🔴 **Red "T":** Local pacing threshold reached / new requests routed through TokenTotals are locally paused until acknowledged or the local threshold is changed.

The traffic light describes **TokenTotals' local pacing state**. It does not mean the provider has approved, rejected, or measured your remaining account funds.

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
The dashboard is wired directly into the local FastAPI runtime. The server exposes `/`, `/dashboard`, `/dashboard/`, and `/dashboard.html`; the Windows tray opens the configured local dashboard automatically.

With the default port, visit:

```text
http://127.0.0.1:8080/dashboard
```

The dashboard shows posted local estimated spend, in-flight preflight estimates, local pacing-threshold state, Turn Notice configuration, latest-turn telemetry, and mixed-model thread telemetry where available.

---

## 💥 The Problem: The "$400 Morning Surprise"

If you build with AI agents (Cursor Composer, Claude Code, CrewAI, AutoGen, or custom LangChain swarms), a recursive reasoning loop, retry storm, or unexpectedly large request can continue consuming provider resources while you are away from your desk.

* **Provider reporting cadence:** Cloud providers can report account usage on a different cadence than a local request stream. A local pacing meter gives you an additional near-real-time signal while work is running.
* **In-flight concurrency:** TokenTotals applies its own preflight pacing check and reserves the known preflight estimate before forwarding a routed request so simultaneous requests do not independently reuse the same known local threshold capacity.
* **Multi-tool visibility:** When multiple scripts and tools route through the same TokenTotals daemon, the local proxy can provide one local estimated-spend and telemetry view for that routed traffic.

---

## 🛡️ The Solution: TokenTotals

TokenTotals runs locally and listens on loopback. The Windows desktop runtime starts the proxy in the background and exposes the local dashboard on the configured port.

Point your IDE, agent framework, or scripts to the TokenTotals local `/v1` endpoint instead of calling the model endpoint directly.

```
[ Cursor / Windsurf / Python Scripts / Agent Swarms ]
                       │
                       ▼ (Calls TokenTotals local /v1 endpoint)
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
* 🔴 **Red "T":** Local pacing threshold reached / new TokenTotals-routed requests locally paused.

### 3. 🧾 Append-Only Local Turn Telemetry Ledger
Completed TokenTotals-routed turns are written to a local runtime append-only JSONL ledger at `~/.tokentotals/turns.jsonl`.

A lot of the raw ingredients have been sitting in provider response telemetry for years: token counts, cache details, model identity, usage metadata, and processing information. The problem is that those ingredients are often exposed as developer plumbing rather than presented back as a readable per-turn cost receipt in the working context.

**The data is often there. The usable receipt usually isn't. TokenTotals makes one.**

The ledger is deliberately **telemetry-only**. Its writer accepts a whitelisted schema rather than arbitrary request/callback objects. It does not persist prompt text, response text, API keys, or hidden reasoning content.

Where the selected provider exposes or TokenTotals can defensibly derive the field, a turn can preserve:

* requested, canonical, and provider-observed model identifiers as separate values;
* provider and pricing-registry verification date;
* input, uncached input, cached input, cache-write/create, output, reasoning/thinking, and tool-input token categories;
* modality token detail and supported server-tool counters when exposed;
* provider-reported total tokens, TokenTotals reconstructed total, and any unclassified/residual tokens required to reconcile the two;
* latency and requested/observed service-tier information where available;
* **estimated cost components, the component arithmetic inputs/rates used by the pricing engine, total turn estimate, estimate completeness, and explicit cost basis** (`provider_registry_complete`, LiteLLM fallback, known list-equivalent, or unavailable); and
* cumulative local/thread estimated spend after settlement.

**Missing is not zero.** A zero token count means zero was actually observed or defensibly derived. If the provider did not expose a category, the ledger keeps that category unavailable rather than manufacturing `0`.

**One thread can contain multiple models.** Historical summaries are derived from the ledger and preserve separate turn/token/estimated-cost totals per model/provider without resetting the thread when the caller changes models mid-conversation.

The ledger's runtime write path is append-only, but it is an ordinary file owned by the local user; it is not represented as immutable or tamper-evident storage.

For the exact arithmetic behind TokenTotals-derived metrics—including preflight estimates, component costs, cache share, reconciliation deltas, output rate, average/median/P95 turn size, coverage, local pacing totals, and admission checks—see [`CALCULATION_TRANSPARENCY.md`](CALCULATION_TRANSPARENCY.md).

### 4. 🔒 Local Control Plane
* **No TokenTotals SaaS Telemetry:** No TokenTotals user account or secondary analytics service is required by the local runtime.
* **Loopback Boundary:** The application listens on loopback and forwards permitted requests to the selected upstream provider through LiteLLM.
* **Upstream Egress Exists:** permitted provider requests necessarily leave localhost and reach the selected provider.
* **100% Free & Open Source:** Licensed under **GNU GPLv3**.

---

## 🚀 Quickstart

### 1. Run the Windows Desktop Runtime
The current desktop application is Windows-specific. `app_gui.py` uses Windows runtime facilities, and TokenTotals does not currently claim a validated macOS or Linux desktop release.

Download the current Windows release when available, unzip it, and run the TokenTotals executable.

A green `T` appears in the system tray and the local proxy starts on the configured port. The default is `8080`.

If the configured port is already occupied, the desktop runtime searches `8080` through `8089` for an available port and saves the selected port back to `~/.tokentotals/config.json`. The tray's **Open Web Dashboard** action always opens the configured port.

### 2. Confirm the Local Dashboard
From the tray, choose **Open Web Dashboard**. With the default port, the address is:

```text
http://127.0.0.1:8080/dashboard
```

If TokenTotals selected a different port, use the port stored in `~/.tokentotals/config.json`.

### 3. Configure Your Client
Use the same configured port for the OpenAI-compatible base URL:

```text
http://127.0.0.1:8080/v1
```

If the runtime selected a different port, replace `8080` accordingly.

For Cursor / VS Code or another compatible client:

1. Open the client's settings.
2. Locate its OpenAI-compatible Base URL setting.
3. Point it to the TokenTotals local `/v1` URL.
4. Configure the provider/API credentials required by that client and upstream model.
5. Send an explicit model ID. TokenTotals does not infer a default model.

#### Python / OpenAI-compatible client

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

### 4. Verify Telemetry
After a completed TokenTotals-routed turn, the local runtime can expose:

```text
GET /api/telemetry/thread?thread_id=<id>
```

and the dashboard renders the normalized presentation object rather than reading the raw ledger directly.

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

See [`CALCULATION_TRANSPARENCY.md`](CALCULATION_TRANSPARENCY.md) for the arithmetic behind every current TokenTotals-derived presentation metric, and [MODEL_COMPARISON_MATRIX.md](MODEL_COMPARISON_MATRIX.md) for a human-readable comparison of the **billing mechanics** TokenTotals models across providers.

---

## 🤝 Open Source Community: Fork It & Make It Yours!

TokenTotals is released under the **GNU General Public License v3.0 (GPLv3)**.

We encourage developers, researchers, and community builders to:
* **Fork the repo** and experiment with your own custom local rules.
* **Build custom adapters** for local LLMs (Ollama, LM Studio, vLLM).
* **Craft your own telemetry dashboards** and share your widgets with the community.
* **Submit PRs** to expand provider support, telemetry normalization, pricing mechanics, and local pacing triggers.

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

Where a required billing component and its rate are known, the basic arithmetic is straightforward:

```text
(billable_units / 1,000,000) × applicable_rate = estimated_component_cost
```

Modern AI pricing increasingly resembles cloud infrastructure pricing rather than a single gas-pump rate. The applicable cost may depend on multiple categories and modifiers: uncached input, cached input, cache writes, output/reasoning tokens, service or processing tier, long-context thresholds, hosted tools, batch processing, regional or account pricing, negotiated contracts, credits, taxes, and provider-side adjustments.

**That is the job TokenTotals is designed to do:** observe the telemetry that is available, apply versioned provider pricing rules and known modifiers, show the resulting estimate and its assumptions, and avoid inventing precision when a billing dimension is missing.

And because this is open-source cost tooling, TokenTotals should be able to **show its work**. The formulas used for every current derived presentation metric are documented in [`CALCULATION_TRANSPARENCY.md`](CALCULATION_TRANSPARENCY.md) so developers can check the arithmetic themselves.

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

### Commercial, Licensing & Acquisition Inquiries
TokenTotals is free and open-source under GPLv3. Organizations requiring different licensing, support, documentation, partnership discussions, or acquisition conversations can contact QuietFireAI.

📧 **Contact:** support@quietfireAI.com  
🔗 **ORCID:** [0009-0000-1375-1725](https://orcid.org/0009-0000-1375-1725)

## 📜 License & Trust

Distributed under the **GNU General Public License v3.0 (GPLv3)**. See `LICENSE` for details.

Built by **QuietFireAI**. Support independent open-source AI telemetry and pacing work at:  
☕ [buymeacoffee.com/jeffphillips](https://buymeacoffee.com/jeffphillips)