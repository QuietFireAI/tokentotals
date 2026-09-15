# 📊 TokenTotals Developer API Model Comparison Matrix

TokenTotals normalizes all LLM transaction costs against official developer API pricing registries across **Anthropic**, **OpenAI**, and **Google**.

---

## 🎯 Developer API Pricing Matrix

| Tier | Anthropic | OpenAI | Google | Primary Use Cases |
| :--- | :--- | :--- | :--- | :--- |
| **Frontier / Advanced** | **Claude 3.7 Sonnet**<br>`$3.00` In / `$15.00` Out | **OpenAI o1**<br>`$15.00` In / `$60.00` Out | **Gemini 2.5 Pro**<br>`$1.25` In / `$10.00` Out | Complex architecture design, deep multi-step reasoning, synthesis |
| **Workhorse / Standard** | **Claude 3.5 Sonnet**<br>`$3.00` In / `$15.00` Out | **OpenAI GPT-4o**<br>`$2.50` In / `$10.00` Out | **Gemini 3.6 / 3.7 Flash**<br>`$0.15` In / `$0.60` Out | General code writing, refactoring, daily agent execution |
| **Economy / High-Speed** | **Claude 3.5 Haiku**<br>`$0.80` In / `$4.00` Out | **OpenAI GPT-4o-mini**<br>`$0.15` In / `$0.60` Out | **Gemini 2.0 Flash-Lite**<br>`$0.075` In / `$0.30` Out | Formatting, quick search, classification, simple linting |

---

## 💡 Standardized Turn Cost Comparison (10,000 Input / 2,000 Output Tokens)

For a single standard developer turn (~10,000 input tokens, ~2,000 output tokens):

$$\text{Turn Cost} = \left(\frac{10,000}{1,000,000} \times \text{Input Rate}\right) + \left(\frac{2,000}{1,000,000} \times \text{Output Rate}\right)$$

| Provider | Model | Tier | Standard Turn Cost | Multiplier vs. Baseline |
| :--- | :--- | :--- | :--- | :--- |
| **OpenAI** | OpenAI o1 | Frontier | **$0.2700** | **200.0x** |
| **Anthropic** | Claude 3.7 Sonnet | Frontier | **$0.0600** | **44.4x** |
| **OpenAI** | OpenAI GPT-4o | Workhorse | **$0.0450** | **33.3x** |
| **Google** | Gemini 2.5 Pro | Frontier | **$0.0325** | **24.1x** |
| **Google** | Gemini 3.6 / 3.7 Flash | Workhorse | **$0.0150** | **11.1x** |
| **Anthropic** | Claude 3.5 Haiku | Economy | **$0.0160** | **11.8x** |
| **OpenAI** | OpenAI GPT-4o-mini | Economy | **$0.0027** | **2.0x** |
| **Google** | Gemini 2.0 Flash-Lite | Economy | **$0.00135** | **1.0x (Baseline)** |
