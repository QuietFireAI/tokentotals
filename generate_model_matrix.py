"""Generate MODEL_COMPARISON_MATRIX.md from the checked-in verified pricing catalog."""
from pathlib import Path

from pricing_engine import calculate_cost, list_models, load_catalog

INPUT_TOKENS = 10_000
OUTPUT_TOKENS = 2_000
OUTPUT = Path(__file__).with_name("MODEL_COMPARISON_MATRIX.md")


def render():
    catalog = load_catalog()
    sources = catalog.get("sources", {})
    rows = []
    for model, record in sorted(list_models().items(), key=lambda item: (item[1].get("provider", ""), item[0])):
        cost = calculate_cost(record, INPUT_TOKENS, OUTPUT_TOKENS)["total_cost_usd"]
        rows.append(
            f"| {record['provider']} | `{model}` | ${record['input_price_per_1m']:.4g} | "
            f"${record['output_price_per_1m']:.4g} | ${cost:.6f} |"
        )
    return "\n".join([
        "# TokenTotals Verified Developer API Pricing Matrix",
        "",
        f"**Receipt verification date:** {catalog.get('verified_at', 'UNKNOWN')}",
        "",
        "This file is generated from `pricing_catalog.json`. Do not hand-edit prices here.",
        "Unknown models are rejected by the runtime until a verified catalog entry is added.",
        "",
        "## Official receipts",
        "",
        f"- OpenAI: {sources.get('openai')}",
        f"- Anthropic: {sources.get('anthropic')}",
        f"- Google Cloud: {sources.get('google')}",
        "",
        "## Standard token rates and turn comparison",
        "",
        f"Turn example: {INPUT_TOKENS:,} input tokens + {OUTPUT_TOKENS:,} output tokens.",
        "Rates are USD per 1M tokens. Provider discounts, caching, batch/flex/fast modes, tools,",
        "regional uplifts, and promotional expiration can change actual invoices; the runtime's",
        "pre-flight guard uses conservative guard rates from the catalog where applicable.",
        "",
        "| Provider | Model | Input / 1M | Output / 1M | Example Turn |",
        "| :--- | :--- | ---: | ---: | ---: |",
        *rows,
        "",
    ])


if __name__ == "__main__":
    OUTPUT.write_text(render(), encoding="utf-8")
    print(f"Wrote {OUTPUT}")
