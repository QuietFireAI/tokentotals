# 📊 TokenTotals Developer API Pricing Comparison Snapshot

TokenTotals uses provider-published pricing information, available API telemetry, and provider-specific billing rules to produce **best-effort cost estimates**. It is not a billing mirror and does not claim invoice-exact alignment.

Provider pricing increasingly behaves like cloud infrastructure pricing: model families, cached and uncached tokens, cache writes, processing tiers, long-context rules, hosted tools, negotiated rates, credits, taxes, and other conditions can change what is ultimately billed. TokenTotals therefore treats pricing as **versioned reference data**, not a permanent constant.

> **Snapshot date:** 2026-09-15  
> This file is a human-readable comparison snapshot. Runtime provider registries and observed telemetry are the calculation inputs where supported. Re-verify rates and rules before relying on this table after its snapshot date.

---

## 🎯 Reference Developer API Pricing Snapshot

| Tier | Anthropic | OpenAI | Google | Primary Use Cases |
| :--- | :--- | :--- | :--- | :--- |
| **Frontier / Advanced** | **Claude 3.7 Sonnet**<br>`$3.00` In / `$15.00` Out | **OpenAI o1**<br>`$15.00` In / `$60.00` Out | **Gemini 2.5 Pro**<br>`$1.25` In / `$10.00` Out | Complex architecture design, deep multi-step reasoning, synthesis |
| **Workhorse / Standard** | **Claude 3.5 Sonnet**<br>`$3.00` In / `$15.00` Out | **GPT-4o**<br>`$2.50` In / `$10.00` Out | **Gemini 2.0 Flash**<br>`$0.10` In / `$0.40` Out | General code writing, refactoring, daily agent execution |
| **Reasoning Workhorse** | — | **o3-mini**<br>`$1.10` In / `$4.40` Out | — | Specialized code generation, math, structured logic |
| **Economy / High-Speed** | **Claude 3.5 Haiku**<br>`$0.80` In / `$4.00` Out | **GPT-4o-mini**<br>`$0.15` In / `$0.60` Out | **Gemini 2.0 Flash-Lite**<br>`$0.075` In / `$0.30` Out | Formatting, quick search, classification, simple linting |

These headline rates are intentionally simplified for cross-platform comparison. They do **not** represent every billing dimension or account-specific condition.

---

## 💡 Standardized Example Turn (10,000 Input / 2,000 Output Tokens)

For a deliberately simplified comparison case with 10,000 uncached input tokens, 2,000 output tokens, no cache-write charge, no hosted-tool charge, no long-context uplift, no special processing tier, and no account-specific pricing:

$$\text{Estimated Turn Cost} = \left(\frac{10,000}{1,000,000} \times \text{Input Rate}\right) + \left(\frac{2,000}{1,000,000} \times \text{Output Rate}\right)$$

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

## Estimation boundary

A TokenTotals calculation is only as complete as the billing-relevant information available at that moment. Depending on provider and model, relevant dimensions can include uncached input, cached input, cache-write tokens, output/reasoning tokens, service or processing tier, context-length rules, hosted tools, batch processing, regional or account pricing, negotiated contracts, credits, taxes, and provider-side adjustments.

The arithmetic itself is deterministic once those inputs are known. **The estimate should never be presented as a mirror of the provider's final invoice.**
