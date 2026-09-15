# 📊 TokenTotals Developer API Model Comparison Matrix

TokenTotals normalizes all LLM transaction costs against official developer API pricing registries across **Anthropic**, **OpenAI**, and **Google**.

---

## 🎯 Developer API Pricing Matrix (2026 Active Lineup)

| Tier | Anthropic | OpenAI | Google | Primary Use Cases |
| :--- | :--- | :--- | :--- | :--- |
| **Frontier / Advanced** | **Claude 3.7 Sonnet**<br>`$3.00` In / `$15.00` Out | **GPT-6 Astra**<br>`$10.00` In / `$50.00` Out | **Gemini 2.5 Pro**<br>`$1.25` In / `$10.00` Out | Complex architecture design, deep multi-step reasoning, synthesis |
| **Workhorse / Standard** | **Claude 3.7 Sonnet**<br>`$3.00` In / `$15.00` Out | **GPT-5.6 Terra**<br>`$2.00` In / `$12.00` Out | **Gemini 3.7 Flash**<br>`$0.15` In / `$0.60` Out | General code writing, refactoring, daily agent execution |
| **Economy / High-Speed** | **Claude 3.5 Haiku**<br>`$0.80` In / `$4.00` Out | **GPT-5.6 Luna**<br>`$0.20` In / `$1.20` Out | **Gemini 2.0 Flash-Lite**<br>`$0.075` In / `$0.30` Out | Formatting, quick search, classification, simple linting |

---

## 💡 Standardized Turn Cost Comparison (10,000 Input / 2,000 Output Tokens)

For a single standard developer turn (~10,000 input tokens, ~2,000 output tokens):

$$\text{Turn Cost} = \left(\frac{10,000}{1,000,000} \times \text{Input Rate}\right) + \left(\frac{2,000}{1,000,000} \times \text{Output Rate}\right)$$

| Provider | Model | Tier | Standard Turn Cost | Multiplier vs. Baseline |
| :--- | :--- | :--- | :--- | :--- |
| **OpenAI** | GPT-6 Astra | Frontier | **$0.2000** | **148.1x** |
| **Anthropic** | Claude 3.7 Sonnet | Frontier | **$0.0600** | **44.4x** |
| **OpenAI** | GPT-5.6 Sol | Frontier | **$0.0800** | **59.3x** |
| **OpenAI** | GPT-5.6 Terra | Workhorse | **$0.0440** | **32.6x** |
| **Google** | Gemini 2.5 Pro | Frontier | **$0.0325** | **24.1x** |
| **Anthropic** | Claude 3.5 Haiku | Economy | **$0.0160** | **11.9x** |
| **OpenAI** | GPT-5.6 Luna | Economy | **$0.0044** | **3.3x** |
| **Google** | Gemini 3.7 Flash | Workhorse | **$0.0027** | **2.0x** |
| **Google** | Gemini 2.0 Flash-Lite | Economy | **$0.00135** | **1.0x (Baseline)** |
