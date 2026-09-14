# 📊 TokenTotals Frontier Model Comparison Matrix (2026 Release)

To provide accurate counterfactual estimates, TokenTotals tracks state-of-the-art frontier models across **Anthropic** (**Fable 5.1**), **OpenAI** (**GPT-6 Astra** / **o3**), and **Google** (**Google Antigravity** / **Gemini 3**).

---

## 🎯 Verified Frontier Pricing & Tier Classification

| Provider | Model | Tier | Input Rate (per 1M) | Output Rate (per 1M) | Special Billing & Feature Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Anthropic** | **Fable 5.1** | **Frontier** | **$10.00** | **$50.00** | Cache reads reduced to `$0.25`/1M (-75%). Mythos 5.1 cybersecurity variant shares core architecture. |
| **OpenAI** | **GPT-6 Astra** | **Frontier** | **$10.00** | **$50.00** | Long-context (>272k) input & cache rate 2x multiplier; output rate 1.5x multiplier (`$75.00`). |
| **OpenAI** | **o3-pro** | **Frontier** | **$20.00** | **$80.00** | Enterprise reasoning model; reasoning tokens billed at full output rate. |
| **Google** | **Antigravity Pro** | **Frontier / Platform** | **$1.25** | **$10.00** | Metered Gemini 3 Pro backend; tiered subscription ($19.99–$199.99/mo) with credit add-ons. |
| **Anthropic** | **Claude 3.7 Sonnet** | **Workhorse** | **$3.00** | **$15.00** | Hybrid coding/reasoning standard. |
| **OpenAI** | **o3-mini** | **Workhorse** | **$1.10** | **$4.40** | High-speed reasoning model. |
| **Google** | **Gemini 3.7 Flash** | **Workhorse** | **$0.75** | **$3.75** | High-velocity agentic workhorse. |
| **Google** | **Gemini 2.0 Flash-Lite**| **Economy** | **$0.075** | **$0.30** | Ultra-low cost baseline. |

---

## 💡 Standardized Turn Cost Comparison (10,000 Input / 2,000 Output Tokens)

For a single standard developer interaction (~10,000 input tokens, ~2,000 output tokens):

$$\text{Turn Cost} = \left(\frac{10,000}{1,000,000} \times \text{Input Rate}\right) + \left(\frac{2,000}{1,000,000} \times \text{Output Rate}\right)$$

| Provider | Model | Tier | Standard Turn Cost | Multiplier vs. Baseline |
| :--- | :--- | :--- | :--- | :--- |
| **OpenAI** | OpenAI o3-pro | Frontier | **$0.3600** | **266.7x** |
| **Anthropic** | Fable 5.1 | Frontier | **$0.2000** | **148.1x** |
| **OpenAI** | GPT-6 Astra | Frontier | **$0.2000** | **148.1x** |
| **Anthropic** | Claude 3.7 Sonnet | Workhorse | **$0.0600** | **44.4x** |
| **Google** | Antigravity Pro | Frontier | **$0.0325** | **24.1x** |
| **OpenAI** | OpenAI o3-mini | Workhorse | **$0.0198** | **14.7x** |
| **Google** | Gemini 3.7 Flash | Workhorse | **$0.0150** | **11.1x** |
| **Anthropic** | Claude 3.5 Haiku | Economy | **$0.0160** | **11.8x** |
| **OpenAI** | GPT-4o-mini | Economy | **$0.0027** | **2.0x** |
| **Google** | Gemini 2.0 Flash-Lite | Economy | **$0.00135** | **1.0x (Baseline)** |
