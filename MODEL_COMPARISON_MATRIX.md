# 📊 TokenTotals Developer API Model Comparison Matrix

TokenTotals normalizes all LLM transaction costs against official developer API pricing registries across **Anthropic**, **OpenAI**, and **Google**.

---

## 🎯 Official Developer API Pricing Matrix

| Tier | Anthropic | OpenAI | Google | Primary Use Cases |
| :--- | :--- | :--- | :--- | :--- |
| **Frontier / Advanced** | **Claude 3.7 Sonnet**<br>`$3.00` In / `$15.00` Out | **OpenAI o1**<br>`$15.00` In / `$60.00` Out | **Gemini 2.5 Pro**<br>`$1.25` In / `$10.00` Out | Complex architecture design, deep multi-step reasoning, synthesis |
| **Workhorse / Standard** | **Claude 3.5 Sonnet**<br>`$3.00` In / `$15.00` Out | **OpenAI o3-mini**<br>`$1.10` In / `$4.40` Out | **Gemini 2.0 Flash**<br>`$0.10` In / `$0.40` Out | General code writing, refactoring, daily agent execution |
| **Economy / High-Speed** | **Claude 3.5 Haiku**<br>`$0.80` In / `$4.00` Out | **OpenAI o1-mini**<br>`$1.10` In / `$4.40` Out | **Gemini 2.0 Flash-Lite**<br>`$0.075` In / `$0.30` Out | Formatting, quick search, classification, simple linting |

---

## 💡 Standardized Turn Cost Comparison (10,000 Input / 2,000 Output Tokens)

For a single standard developer turn (~10,000 input tokens, ~2,000 output tokens):

$$\text{Turn Cost} = \left(\frac{10,000}{1,000,000} \times \text{Input Rate}\right) + \left(\frac{2,000}{1,000,000} \times \text{Output Rate}\right)$$

| Provider | Model | Tier | Standard Turn Cost | Multiplier vs. Baseline |
| :--- | :--- | :--- | :--- | :--- |
| **OpenAI** | OpenAI o1 | Frontier | **$0.2700** | **200.0x** |
| **Anthropic** | Claude 3.7 Sonnet | Frontier | **$0.0600** | **44.4x** |
| **Google** | Gemini 2.5 Pro | Frontier | **$0.0325** | **24.1x** |
| **OpenAI** | OpenAI o3-mini | Workhorse | **$0.0198** | **14.7x** |
| **OpenAI** | OpenAI o1-mini | Economy | **$0.0198** | **14.7x** |
| **Anthropic** | Claude 3.5 Haiku | Economy | **$0.0160** | **11.9x** |
| **Google** | Gemini 2.0 Flash | Workhorse | **$0.0018** | **1.33x** |
| **Google** | Gemini 2.0 Flash-Lite | Economy | **$0.00135** | **1.0x (Baseline)** |
