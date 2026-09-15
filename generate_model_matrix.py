"""Generate MODEL_COMPARISON_MATRIX.md from TokenTotals' verified pricing view.

The effective view comes from pricing_engine: the checked-in catalog plus any promoted,
validated provider snapshot (OpenAI is the first dynamic provider implementation).
"""
from pathlib import Path

from pricing_engine import calculate_cost, list_models, load_catalog

INPUT_TOKENS = 10_000
OUTPUT_TOKENS = 2_000
OUTPUT = Path(__file__).with_name("MODEL_COMPARISON_MATRIX.md")


def render():
    catalog = load_catalog()
    sources = catalog.get("sources", {})
    dynamic = catalog.get("dynamic_sources", {})
    rows = []
    for model, record in sorted(list_models().items(), key=lambda item: (item[1].get("provider", ""), item[0])):
        cost = calculate_cost(record, INPUT_TOKENS, OUTPUT_TOKENS)["total_cost_usd"]
        rows.append(
            f"| {record['provider']} | `{model}` | ${record['input_price_per_1m']:.4g} | "
            f"${record['output_price_per_1m']:.4g} | ${cost:.6f} |"
        )

    verification_lines = [
        f"**Checked-in catalog verification date:** {catalog.get('verified_at', 'UNKNOWN')}",
    ]
    openai_dynamic = dynamic.get("openai")
    if openai_dynamic:
        verification_lines.append(
            f"**OpenAI promoted snapshot:** {openai_dynamic.get('verified_at', 'UNKNOWN')} "
            f"(source checked {openai_dynamic.get('source_checked_at', 'UNKNOWN')})"
        )

    return "\n".join([
        "# TokenTotals Verified Developer API Pricing Matrix",
        "",
        *verification_lines,
        "",
        "This file is generated from TokenTotals' effective verified pricing view. Do not hand-edit prices here.",
        "The view combines the checked-in catalog with any promoted provider snapshot consumed by `pricing_engine`.",
        "OpenAI is currently the first dynamic official-source provider; Anthropic and Google remain dated catalog entries.",
        "Unknown models are rejected by the runtime until a verified pricing entry is added.",
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
        "Rates are USD per 1M tokens. These are independent estimates, not provider invoices.",
        "Caching, context bands, service tiers, tools, regional processing, promotions, account-specific",
        "pricing, and other applicable billing dimensions can change the provider's final charge.",
        "",
        "| Provider | Model | Input / 1M | Output / 1M | Example Turn |",
        "| :--- | :--- | ---: | ---: | ---: |",
        *rows,
        "",
    ])


if __name__ == "__main__":
    OUTPUT.write_text(render(), encoding="utf-8")
    print(f"Wrote {OUTPUT}")
