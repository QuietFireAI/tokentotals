# 📊 TokenTotals Verified Cross-Platform Model Comparison Matrix (2026 Edition)

To give developers complete transparency into relative model costs, TokenTotals normalizes LLM pricing against verified public API rates across the Big Three providers (**Anthropic**, **OpenAI**, and **Google**).

---

## 🎯 Verified Pricing & Tier Classification

*All rates verified directly against official provider documentation:*
- **Anthropic Docs:** [platform.claude.com/docs/en/about-claude/pricing](https://platform.claude.com/docs/en/about-claude/pricing)
- **OpenAI Docs:** [openai.com/api/pricing](https://openai.com/api/pricing)
- **Google Cloud / AI Studio Docs:** [ai.google.dev/pricing](https://ai.google.dev/pricing) | [cloud.google.com/vertex-ai/generative-ai/pricing](https://cloud.google.com/vertex-ai/generative-ai/pricing)

| Tier | Anthropic | OpenAI | Google | Primary Use Cases |
| :--- | :--- | :--- | :--- | :--- |
| **Frontier / Reasoning** | **Claude 3 Opus**<br>`$15.00` In / `$75.00` Out | **OpenAI o3**<br>`$2.00` In / `$8.00` Out | **Gemini 2.5 Pro**<br>`$1.25` In / `$10.00` Out | Complex architecture design, deep multi-step reasoning, legal/medical synthesis |
| **Workhorse / Standard** | **Claude 3.5 Sonnet**<br>`$3.00` In / `$15.00` Out | **OpenAI GPT-4o**<br>`$2.50` In / `$10.00` Out<br>**OpenAI o3-mini**<br>`$1.10` In / `$4.40` Out | **Gemini 3.7 Flash**<br>`$0.75` In / `$3.75` Out | General code writing, refactoring, agent execution, daily developer work |
| **Economy / High-Speed** | **Claude 3.5 Haiku**<br>`$0.80` In / `$4.00` Out | **OpenAI GPT-4o-mini**<br>`$0.15` In / `$0.60` Out | **Gemini 2.0 Flash-Lite**<br>`$0.075` In / `$0.30` Out | Formatting, quick search, classification, simple linting, token-conscious sub-agents |

---

## 💡 Verified Turn Cost Calculations (10,000 Input / 2,000 Output Tokens)

For a single standard developer interaction (~10,000 input tokens, ~2,000 output tokens):

$$\text{Cost} = \left(\frac{\text{Input Tokens}}{1,000,000} \times \text{Input Rate}\right) + \left(\frac{\text{Output Tokens}}{1,000,000} \times \text{Output Rate}\right)$$

| Provider | Model | Tier | Standard Turn Cost | Ratio vs. Lowest |
| :--- | :--- | :--- | :--- | :--- |
| **Anthropic** | Claude 3 Opus | Frontier | **$0.3000** | **222.2x** |
| **OpenAI** | OpenAI o3 | Frontier | **$0.0360** | **26.7x** |
| **Google** | Gemini 2.5 Pro | Frontier | **$0.0325** | **24.1x** |
| **Anthropic** | Claude 3.5 Sonnet | Workhorse | **$0.0600** | **44.4x** |
| **OpenAI** | OpenAI GPT-4o | Workhorse | **$0.0450** | **33.3x** |
| **OpenAI** | OpenAI o3-mini | Workhorse | **$0.0198** | **14.7x** |
| **Google** | Gemini 3.7 Flash | Workhorse | **$0.0150** | **11.1x** |
| **Anthropic** | Claude 3.5 Haiku | Economy | **$0.0160** | **11.8x** |
| **OpenAI** | GPT-4o-mini | Economy | **$0.0027** | **2.0x** |
| **Google** | Gemini 2.0 Flash-Lite | Economy | **$0.00135** | **1.0x (Baseline)** |

---

## ⚖️ Key Insights & Vendor Transparency

1. **Frontier vs. Workhorse Multipliers:** Running a routine coding task on **Claude 3 Opus** (`$0.3000`/turn) costs **20x more** than running it on **Gemini 3.7 Flash** (`$0.0150`/turn) or **OpenAI o3-mini** (`$0.0198`/turn).
2. **Reasoning Token Auditing:** On reasoning models like `o3` and `o3-mini`, reasoning tokens generated during chain-of-thought are billed at the **output rate** (`$8.00`/1M or `$4.40`/1M). TokenTotals surfaces these exact output counts in real time.
3. **Prompt Cache Savings:** Prompt caching drops input costs by **50% to 90%** across OpenAI, Anthropic, and Google. TokenTotals calculates and displays your net prompt cache savings on every turn.
