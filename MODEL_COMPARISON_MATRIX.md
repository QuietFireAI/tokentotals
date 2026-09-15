# TokenTotals Verified Developer API Pricing Matrix

**Checked-in catalog verification date:** 2026-09-14

This file is generated from TokenTotals' effective verified pricing view. Do not hand-edit prices here.
The view combines the checked-in catalog with any promoted provider snapshot consumed by `pricing_engine`.
OpenAI is currently the first dynamic official-source provider; Anthropic and Google remain dated catalog entries.
Unknown models are rejected by the runtime until a verified pricing entry is added.

## Official receipts

- OpenAI: https://developers.openai.com/api/docs/pricing
- Anthropic: https://platform.claude.com/docs/en/about-claude/pricing
- Google Cloud: https://cloud.google.com/gemini-enterprise-agent-platform/generative-ai/pricing

## Standard token rates and turn comparison

Turn example: 10,000 input tokens + 2,000 output tokens.
Rates are USD per 1M tokens. These are independent estimates, not provider invoices.
Caching, context bands, service tiers, tools, regional processing, promotions, account-specific
pricing, and other applicable billing dimensions can change the provider's final charge.

| Provider | Model | Input / 1M | Output / 1M | Example Turn |
| :--- | :--- | ---: | ---: | ---: |
| Anthropic | `claude-fable-5.1` | $10 | $50 | $0.200000 |
| Anthropic | `claude-haiku-4.5` | $1 | $5 | $0.020000 |
| Anthropic | `claude-opus-5` | $5 | $25 | $0.100000 |
| Anthropic | `claude-sonnet-5` | $2 | $10 | $0.040000 |
| Google | `gemini-3.1-flash-lite` | $0.25 | $1.5 | $0.005500 |
| Google | `gemini-3.1-pro-preview` | $2 | $12 | $0.044000 |
| Google | `gemini-3.5-flash` | $1.5 | $9 | $0.033000 |
| Google | `gemini-3.5-flash-lite` | $0.3 | $2.5 | $0.008000 |
| Google | `gemini-3.6-flash` | $0.75 | $3.75 | $0.015000 |
| Google | `gemini-3.7-flash` | $0.75 | $3.75 | $0.015000 |
| Google | `gemini-3.8-flash` | $0.75 | $3.75 | $0.015000 |
| OpenAI | `gpt-5.6-luna` | $0.2 | $1.2 | $0.004400 |
| OpenAI | `gpt-5.6-sol` | $4 | $20 | $0.080000 |
| OpenAI | `gpt-5.6-terra` | $2 | $12 | $0.044000 |
| OpenAI | `gpt-6-astra` | $10 | $50 | $0.200000 |
