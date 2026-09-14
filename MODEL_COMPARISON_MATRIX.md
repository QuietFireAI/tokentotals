# 📊 TokenTotals Cross-Platform Model Comparison Matrix (2026 Edition)

To give developers complete transparency into relative model costs, TokenTotals categorizes LLM models into three standardized performance tiers across the Big Three providers (**Anthropic**, **OpenAI**, and **Google**).

---

## 🎯 Tier Classification & Price Mapping

| Tier | Anthropic | OpenAI | Google | Primary Use Cases |
| :--- | :--- | :--- | :--- | :--- |
| **Frontier / Advanced** | **Claude Opus 4.6**<br>`$15.00` In / `$75.00` Out | **OpenAI o3**<br>`$10.00` In / `$40.00` Out | **Gemini 2.5 Pro**<br>`$1.25` In / `$10.00` Out | Complex architecture design, deep multi-step reasoning, legal/medical synthesis |
| **Workhorse / Standard** | **Claude 3.7 Sonnet**<br>`$3.00` In / `$15.00` Out | **OpenAI o3-mini**<br>`$1.10` In / `$4.40` Out | **Gemini 3.7 Flash**<br>`$0.15` In / `$0.60` Out | General code writing, refactoring, agent execution, daily developer work |
| **Economy / High-Speed** | **Claude 3.5 Haiku**<br>`$0.80` In / `$4.00` Out | **OpenAI GPT-4o-mini**<br>`$0.15` In / `$0.60` Out | **Gemini 2.0 Flash-Lite**<br>`$0.075` In / `$0.30` Out | Formatting, quick search, classification, simple linting, token-conscious sub-agents |

---

## 💡 Counterfactual Cost Examples (10,000 Input / 2,000 Output Tokens)

For a single standard developer turn (~10k context input tokens, ~2k response tokens):

| Provider | Model | Tier | Cost for Single Turn | Ratio vs. Lowest |
| :--- | :--- | :--- | :--- | :--- |
| **Anthropic** | Claude Opus 4.6 | Frontier | **$0.3000** | 222x |
| **OpenAI** | OpenAI o3 | Frontier | **$0.1800** | 133x |
| **Google** | Gemini 2.5 Pro | Frontier | **$0.0325** | 24x |
| **Anthropic** | Claude 3.7 Sonnet | Workhorse | **$0.0600** | 44x |
| **OpenAI** | OpenAI o3-mini | Workhorse | **$0.0198** | 14.6x |
| **Google** | Gemini 3.7 Flash | Workhorse | **$0.0027** | 2x |
| **Anthropic** | Claude 3.5 Haiku | Economy | **$0.0160** | 11.8x |
| **OpenAI** | GPT-4o-mini | Economy | **$0.0027** | 2x |
| **Google** | Gemini 2.0 Flash-Lite | Economy | **$0.00135** | **1x (Baseline)** |

---

## ⚖️ Why This Matrix Matters for Developers & FinOps

1. **Zero Guesswork:** Developers often use a Frontier model for routine code formatting or quick file lookups, incurring a **100x–200x premium** over an Economy model.
2. **Normalized Metrics:** TokenTotals normalizes all telemetry against this matrix in real time, giving developers immediate visibility into counterfactual alternatives.
3. **Provider Shade (The Truth in Raw Numbers):** Showing that a Workhorse task costs `$0.06` on Sonnet vs `$0.0027` on Gemini 3.7 Flash lets developers make value-based choices without vendor lock-in bias.
