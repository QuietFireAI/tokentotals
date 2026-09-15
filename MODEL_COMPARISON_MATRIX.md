# TokenTotals Verified Developer API Pricing Matrix

**Checked-in catalog verification date:** 2026-09-15
**Official sources last checked:** 2026-09-15T14:42:31Z

**Freshness contract:** a verified pricing receipt is CURRENT for at most 24 hours from `source_checked_at`. Once older than 24 hours, TokenTotals treats the pricing surface as STALE and the integrity gate fails closed until a new verified refresh succeeds.

This file is generated from TokenTotals' effective verified pricing view. Do not hand-edit prices here.
The matrix, README pricing block, whitepaper pricing receipt, and daily status document are regenerated together after successful official-source checks.
Unknown models are rejected by the runtime until a verified pricing entry is deliberately added.

## What this matrix means

TokenTotals does **not** claim invoice parity. It independently approximates cost from the provider pricing rules represented in the verified catalog plus transaction telemetry available to the user. The point of this matrix is to make the represented math inspectable and challengeable.

The table below shows two different calculations for the same example workload:

- **Base estimate:** 10,000 input tokens + 2,000 output tokens at the represented base/standard rates.
- **Conservative pre-flight reservation:** the same workload at TokenTotals' catalog guard rates. The reservation is intentionally high-side and is a pacing control, not a forecast of the provider invoice.

## Calculation methods

Base estimate:

```text
base_estimate = (input_tokens / 1,000,000 × base_input_rate)
              + (output_tokens / 1,000,000 × base_output_rate)
```

Conservative pre-flight reservation:

```text
reservation = (estimated_input_tokens / 1,000,000 × guard_input_rate)
            + (bounded_output_tokens / 1,000,000 × guard_output_rate)
```

After a response supplies usable token counts, TokenTotals reconciles the reservation using the most specific pricing behavior currently implemented for that transaction. If usable final telemetry is missing, the conservative reservation remains on the books and the stream is marked unreconciled rather than guessed down to zero.

## Official pricing receipts

- OpenAI: https://developers.openai.com/api/docs/pricing
- Anthropic: https://platform.claude.com/docs/en/about-claude/pricing
- Google Cloud: https://cloud.google.com/gemini-enterprise-agent-platform/generative-ai/pricing

## Verified models, base rates, guard rates, and example math

Rates are USD per 1M tokens. The represented base rates are the standard/base text-token rates selected by the verified catalog. Guard rates are high-side rates used for pre-flight pacing across the published dimensions represented by the catalog; they are not universal maxima for every possible provider product or account.

| Provider | Model | Base input / 1M | Base output / 1M | Guard input / 1M | Guard output / 1M | Example base turn | Example reserved turn | Qualifier |
| :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| Anthropic | `claude-fable-5.1` | $10 | $50 | $20 | $50 | $0.200000 | $0.300000 | base input/output shown; caching and batch have separate rates |
| Anthropic | `claude-haiku-4.5` | $1 | $5 | $2 | $5 | $0.020000 | $0.030000 | base input/output shown; caching and batch have separate rates |
| Anthropic | `claude-opus-5` | $5 | $25 | $10 | $25 | $0.100000 | $0.150000 | base input/output shown; caching and batch have separate rates |
| Anthropic | `claude-sonnet-5` | $2 | $10 | $4 | $10 | $0.040000 | $0.060000 | base input/output shown; caching and batch have separate rates |
| Google | `gemini-3.1-flash-lite` | $0.25 | $1.5 | $0.495 | $2.97 | $0.005500 | $0.010890 | Standard/global base shown; region/service mode can differ |
| Google | `gemini-3.1-pro-preview` | $2 | $12 | $7.2 | $32.4 | $0.044000 | $0.136800 | Standard/global base shown for <=200K input; >200K is higher |
| Google | `gemini-3.5-flash` | $1.5 | $9 | $2.97 | $17.82 | $0.033000 | $0.065340 | Standard/global base shown; region/service mode can differ |
| Google | `gemini-3.5-flash-lite` | $0.3 | $2.5 | $0.594 | $4.95 | $0.008000 | $0.015840 | Standard/global base shown; region/service mode can differ |
| Google | `gemini-3.6-flash` | $0.75 | $3.75 | $1.485 | $7.425 | $0.015000 | $0.029700 | represented rate effective through 2026-12-31; Standard/global base shown; region/service mode can differ |
| Google | `gemini-3.7-flash` | $0.75 | $3.75 | $1.485 | $7.425 | $0.015000 | $0.029700 | represented rate effective through 2026-12-31; Standard/global base shown; region/service mode can differ |
| Google | `gemini-3.8-flash` | $0.75 | $3.75 | $1.485 | $7.425 | $0.015000 | $0.029700 | represented rate effective through 2026-12-31; Standard/global base shown; region/service mode can differ |
| OpenAI | `gpt-5.6-luna` | $0.2 | $1.2 | $0.4 | $1.8 | $0.004400 | $0.007600 | >272K input uses higher long-context rates |
| OpenAI | `gpt-5.6-sol` | $4 | $20 | $8 | $30 | $0.080000 | $0.140000 | published promotional base pricing available at least through 2026-11-21; >272K input uses higher long-context rates |
| OpenAI | `gpt-5.6-terra` | $2 | $12 | $4 | $18 | $0.044000 | $0.076000 | >272K input uses higher long-context rates |
| OpenAI | `gpt-6-astra` | $10 | $50 | $40 | $150 | $0.200000 | $0.700000 | >272K input uses higher long-context rates |

## Provider-specific qualifiers represented in this revision

- **OpenAI:** the represented Astra/Sol/Terra/Luna base rates are current on the cited official model pages. Prompts above 272K input tokens use 2× input/cache rates and 1.5× output for the full request on these models. GPT-5.6 Sol's published promotional base pricing is stated as available at least through 2026-11-21. Tool-specific and other non-token charges are outside this simple base-turn example unless separately implemented.
- **Anthropic:** the table shows base input/output token rates for Fable 5.1, Opus 5, Sonnet 5, and Haiku 4.5. Prompt-cache writes, cache hits/refreshes, batch, data-residency, and other applicable modes have distinct published rates and are not collapsed into the base column.
- **Google:** the table shows Standard/global base rates represented by the catalog. Gemini 3.1 Pro Preview has a higher >200K context band. Gemini 3.6/3.7/3.8 Flash are represented at the current promotional $0.75/$3.75 Standard/global rate through 2026-12-31; the cited page publishes $1.50/$7.50 starting 2027-01-01. Non-global, Priority, Flex/Batch, grounding, tuning, tool, and modality charges can differ.

## Accuracy boundary

A provider invoice can differ because the applicable billable event may include context bands, cached input/cache writes, requested versus actual service tier, region, modalities, hosted tools, grounding/search, storage/runtime meters, fine-tuning, promotions/effective dates, account-specific pricing, retries/partial streams, or provider-side rule changes. TokenTotals therefore leads with **approximation** and preserves provenance/unknowns instead of pretending to be in lockstep with a provider billing system.

The generated matrix is intentionally limited to models with a verified catalog entry used by this revision. It is not a list of every model a provider offers. Adding a model to the public matrix requires adding and validating its pricing record first.
