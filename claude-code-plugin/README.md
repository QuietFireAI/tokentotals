# TokenTotals for Claude Code

Turn Receipts for Claude Code. When a turn finishes, TokenTotals reads the usage telemetry Claude Code already records for every API call in the session transcript (uncached input, cache writes split by 5-minute and 1-hour lifetime, cache reads, output and thinking tokens, service tier and inference geography), prices each call with the TokenTotals Anthropic pricing engine, and shows a one-line receipt:

```
Turn Receipt: $0.42 · 6 API calls · claude-opus-5-5 · in 12 · cache write 31k · cache read 640k · out 3.1k
```

Run `/tokentotals:receipt` for the expanded receipt with components, notes and the session total. Arguments: `short`, `session`, `last N`.

## What it is and isn't

- List-price estimate from Claude Code's own usage fields. Not an invoice, not your account balance.
- Pro and Max subscription usage is not billed per token. For subscribers the receipt shows what the turn would cost at API list price, plus the token breakdown.
- Missing is not zero: a model without a registered price shows `unavailable`, and an incomplete calculation is labelled incomplete.
- Prompt and response text are never written to the ledger. Only usage numbers, model IDs, message IDs and timestamps.
- Subagent API calls (from the session's `subagents` folder) are included and counted separately.

## Install

In a terminal:

```
claude plugin marketplace add QuietFireAI/tokentotals
claude plugin install tokentotals@tokentotals
```

Then start a new Claude Code session. Each finished turn shows a `Turn Receipt:` line.

## Requirements

Python 3.9 or newer on PATH (`python3`, `python` or `py`). No other dependencies. No network access.

## Data

Receipts are appended to `receipts.jsonl` in the plugin data folder (`~/.claude/plugins/data/...`).

## Pricing

`scripts/tokentotals_cc/pricing/anthropic_registry.json` is a copy of the repo's `pricing/anthropic_registry.json`, and `scripts/tokentotals_cc/anthropic_pricing.py` a copy of `anthropic_pricing.py`. `tests/test_claude_code_plugin.py` fails if the copies drift. Current Claude 5.5 and Fable 5.2 rates were read from https://platform.claude.com/docs/en/about-claude/pricing on 2026-11-13.

License: GPL-3.0. Part of https://github.com/QuietFireAI/tokentotals.
