# TokenTotals Daily Pricing Integrity Status

> Generated file. Do not hand-edit pricing values or freshness metadata here.

**Last successful official-source refresh:** 2026-09-15T14:36:21Z

**Verified catalog date:** 2026-09-15

**Calculation workload:** 10,000 input tokens + 2,000 output tokens

A successful daily refresh means every represented provider passed its configured official-source integrity check before the catalog freshness date, matrix, README block, whitepaper receipt, and example calculations were regenerated. A failed provider check must fail the workflow rather than stamping stale numbers as current.

| Provider | Status | Refresh mode | Source hash |
| :--- | :--- | :--- | :--- |
| OpenAI | verified | official structured source parse; recognized safe changes refresh catalog, suspicious/source-only/model-set changes fail closed | `01d1e3d0543cc8e2bc776dfb87c7d12b0388663a385be953b63988429c19c9b1` |
| Anthropic | verified | official live base+guard drift validation; mismatch, missing model, parse ambiguity, or expiry fails closed | `26fd92cabb5588693e785c851fbd8c66b102d337175a67f9e99e39212b554c6b` |
| Google | verified | official live base+guard drift validation; mismatch, missing model, parse ambiguity, or expiry fails closed | `9a83fb941931c951f54e93caab426615f3d09111e57a6db261864930cf84bf51` |

## Current generated comparison

| Provider | Verified model | Base input / 1M | Base output / 1M | 10K in + 2K out base estimate | Conservative pre-flight reservation |
| :--- | :--- | ---: | ---: | ---: | ---: |
| Anthropic | `claude-fable-5.1` | $10 | $50 | $0.200000 | $0.300000 |
| Anthropic | `claude-haiku-4.5` | $1 | $5 | $0.020000 | $0.030000 |
| Anthropic | `claude-opus-5` | $5 | $25 | $0.100000 | $0.150000 |
| Anthropic | `claude-sonnet-5` | $2 | $10 | $0.040000 | $0.060000 |
| Google | `gemini-3.1-flash-lite` | $0.25 | $1.5 | $0.005500 | $0.010890 |
| Google | `gemini-3.1-pro-preview` | $2 | $12 | $0.044000 | $0.136800 |
| Google | `gemini-3.5-flash` | $1.5 | $9 | $0.033000 | $0.065340 |
| Google | `gemini-3.5-flash-lite` | $0.3 | $2.5 | $0.008000 | $0.015840 |
| Google | `gemini-3.6-flash` | $0.75 | $3.75 | $0.015000 | $0.029700 |
| Google | `gemini-3.7-flash` | $0.75 | $3.75 | $0.015000 | $0.029700 |
| Google | `gemini-3.8-flash` | $0.75 | $3.75 | $0.015000 | $0.029700 |
| OpenAI | `gpt-5.6-luna` | $0.2 | $1.2 | $0.004400 | $0.007600 |
| OpenAI | `gpt-5.6-sol` | $4 | $20 | $0.080000 | $0.140000 |
| OpenAI | `gpt-5.6-terra` | $2 | $12 | $0.044000 | $0.076000 |
| OpenAI | `gpt-6-astra` | $10 | $50 | $0.200000 | $0.700000 |

## Calculation rule

```text
base_estimate = (input_tokens / 1,000,000 × base_input_rate)
              + (output_tokens / 1,000,000 × base_output_rate)

reservation = (estimated_input_tokens / 1,000,000 × guard_input_rate)
            + (bounded_output_tokens / 1,000,000 × guard_output_rate)
```

These are independent approximations/pacing controls, not provider invoices. Unsupported billing dimensions remain explicit limitations rather than being silently invented.
