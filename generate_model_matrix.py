"""Generate TokenTotals pricing comparison surfaces from the verified pricing view.

`MODEL_COMPARISON_MATRIX.md` and the marked pricing block in `README.md` are both
rendered from `pricing_engine`, so the public comparison surfaces cannot quietly
become independent hand-maintained pricing tables.
"""
from pathlib import Path

from pricing_engine import calculate_cost, list_models, load_catalog

INPUT_TOKENS = 10_000
OUTPUT_TOKENS = 2_000
OUTPUT = Path(__file__).with_name("MODEL_COMPARISON_MATRIX.md")
README = Path(__file__).with_name("README.md")
README_START = "<!-- TOKENTOTALS_VERIFIED_PRICING_START -->"
README_END = "<!-- TOKENTOTALS_VERIFIED_PRICING_END -->"


def _money(value: float) -> str:
    return f"${value:.6f}"


def _rate(value: float) -> str:
    return f"${value:.6g}"


def _sorted_models():
    return sorted(
        list_models().items(),
        key=lambda item: (item[1].get("provider", ""), item[0]),
    )


def _effective_note(model: str, record: dict) -> str:
    notes = []
    effective_until = record.get("effective_until")
    if effective_until:
        notes.append(f"represented rate effective through {effective_until}")
    if model == "gpt-5.6-sol":
        notes.append("published promotional base pricing available at least through 2026-11-21")
    if record.get("provider") == "OpenAI":
        notes.append(">272K input uses higher long-context rates")
    elif model == "gemini-3.1-pro-preview":
        notes.append("Standard/global base shown for <=200K input; >200K is higher")
    elif record.get("provider") == "Google":
        notes.append("Standard/global base shown; region/service mode can differ")
    elif record.get("provider") == "Anthropic":
        notes.append("base input/output shown; caching and batch have separate rates")
    return "; ".join(notes) or "base text-token rate represented by verified catalog"


def _row_values(model: str, record: dict) -> dict:
    base = calculate_cost(record, INPUT_TOKENS, OUTPUT_TOKENS, conservative=False)[
        "total_cost_usd"
    ]
    guard = calculate_cost(record, INPUT_TOKENS, OUTPUT_TOKENS, conservative=True)[
        "total_cost_usd"
    ]
    return {
        "provider": record["provider"],
        "model": model,
        "input": float(record["input_price_per_1m"]),
        "output": float(record["output_price_per_1m"]),
        "guard_input": float(record["guard_input_price_per_1m"]),
        "guard_output": float(record["guard_output_price_per_1m"]),
        "base_turn": base,
        "guard_turn": guard,
        "note": _effective_note(model, record),
    }


def render_compact_table() -> str:
    rows = []
    for model, record in _sorted_models():
        row = _row_values(model, record)
        rows.append(
            f"| {row['provider']} | `{model}` | {_rate(row['input'])} | "
            f"{_rate(row['output'])} | {_money(row['base_turn'])} | "
            f"{_money(row['guard_turn'])} |"
        )
    return "\n".join(
        [
            "| Provider | Verified model | Base input / 1M | Base output / 1M | 10K in + 2K out base estimate | Conservative pre-flight reservation |",
            "| :--- | :--- | ---: | ---: | ---: | ---: |",
            *rows,
        ]
    )


def render_readme_pricing_section() -> str:
    catalog = load_catalog()
    return "\n".join(
        [
            README_START,
            "## Current verified model pricing snapshot",
            "",
            f"**Verified catalog date:** {catalog.get('verified_at', 'UNKNOWN')}  ",
            "**Comparison workload:** 10,000 input tokens + 2,000 output tokens.",
            "",
            "This table is generated from the same `pricing_engine` view used by the proxy and `MODEL_COMPARISON_MATRIX.md`; it is not a separately maintained marketing table. Dollar values are independent approximations from represented provider rules and observed/estimated telemetry, not provider invoices.",
            "",
            render_compact_table(),
            "",
            "Base-turn approximation:",
            "",
            "```text",
            "base_estimate = (input_tokens / 1,000,000 × base_input_rate)",
            "              + (output_tokens / 1,000,000 × base_output_rate)",
            "```",
            "",
            "Pre-flight reservation uses the same formula with the catalog's conservative guard rates. The guard is deliberately a high-side pacing amount; it is **not** a prediction that the provider will invoice that amount. After usable provider token telemetry arrives, TokenTotals reconciles the reservation to the most specific supported estimate. Unknown pricing fails closed instead of receiving an invented rate.",
            "",
            "The compact table shows represented base text-token rates. Context bands, cache read/write rates, service modes, region, tools, modalities, promotions/effective dates, account-specific pricing, and other billable dimensions can change the applicable provider charge. See [MODEL_COMPARISON_MATRIX.md](MODEL_COMPARISON_MATRIX.md) for the row-by-row guard rates and qualifiers.",
            README_END,
        ]
    )


def render() -> str:
    catalog = load_catalog()
    sources = catalog.get("sources", {})
    dynamic = catalog.get("dynamic_sources", {})
    rows = []
    for model, record in _sorted_models():
        row = _row_values(model, record)
        rows.append(
            f"| {row['provider']} | `{model}` | {_rate(row['input'])} | "
            f"{_rate(row['output'])} | {_rate(row['guard_input'])} | "
            f"{_rate(row['guard_output'])} | {_money(row['base_turn'])} | "
            f"{_money(row['guard_turn'])} | {row['note']} |"
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

    return "\n".join(
        [
            "# TokenTotals Verified Developer API Pricing Matrix",
            "",
            *verification_lines,
            "",
            "This file is generated from TokenTotals' effective verified pricing view. Do not hand-edit prices here.",
            "The view combines the checked-in catalog with any promoted provider snapshot consumed by `pricing_engine`.",
            "OpenAI is currently the first dynamic official-source provider; Anthropic and Google remain dated verified catalog entries with non-destructive official-source drift checks.",
            "Unknown models are rejected by the runtime until a verified pricing entry is deliberately added.",
            "",
            "## What this matrix means",
            "",
            "TokenTotals does **not** claim invoice parity. It independently approximates cost from the provider pricing rules represented in the verified catalog plus transaction telemetry available to the user. The point of this matrix is to make the represented math inspectable and challengeable.",
            "",
            "The table below shows two different calculations for the same example workload:",
            "",
            f"- **Base estimate:** {INPUT_TOKENS:,} input tokens + {OUTPUT_TOKENS:,} output tokens at the represented base/standard rates.",
            "- **Conservative pre-flight reservation:** the same workload at TokenTotals' catalog guard rates. The reservation is intentionally high-side and is a pacing control, not a forecast of the provider invoice.",
            "",
            "## Calculation methods",
            "",
            "Base estimate:",
            "",
            "```text",
            "base_estimate = (input_tokens / 1,000,000 × base_input_rate)",
            "              + (output_tokens / 1,000,000 × base_output_rate)",
            "```",
            "",
            "Conservative pre-flight reservation:",
            "",
            "```text",
            "reservation = (estimated_input_tokens / 1,000,000 × guard_input_rate)",
            "            + (bounded_output_tokens / 1,000,000 × guard_output_rate)",
            "```",
            "",
            "After a response supplies usable token counts, TokenTotals reconciles the reservation using the most specific pricing behavior currently implemented for that transaction. If usable final telemetry is missing, the conservative reservation remains on the books and the stream is marked unreconciled rather than guessed down to zero.",
            "",
            "## Official pricing receipts",
            "",
            f"- OpenAI: {sources.get('openai')}",
            f"- Anthropic: {sources.get('anthropic')}",
            f"- Google Cloud: {sources.get('google')}",
            "",
            "## Verified models, base rates, guard rates, and example math",
            "",
            "Rates are USD per 1M tokens. The represented base rates are the standard/base text-token rates selected by the verified catalog. Guard rates are high-side rates used for pre-flight pacing across the published dimensions represented by the catalog; they are not universal maxima for every possible provider product or account.",
            "",
            "| Provider | Model | Base input / 1M | Base output / 1M | Guard input / 1M | Guard output / 1M | Example base turn | Example reserved turn | Qualifier |",
            "| :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |",
            *rows,
            "",
            "## Provider-specific qualifiers represented in this revision",
            "",
            "- **OpenAI:** the represented Astra/Sol/Terra/Luna base rates are current on the cited official model pages. Prompts above 272K input tokens use 2× input/cache rates and 1.5× output for the full request on these models. GPT-5.6 Sol's published promotional base pricing is stated as available at least through 2026-11-21. Tool-specific and other non-token charges are outside this simple base-turn example unless separately implemented.",
            "- **Anthropic:** the table shows base input/output token rates for Fable 5.1, Opus 5, Sonnet 5, and Haiku 4.5. Prompt-cache writes, cache hits/refreshes, batch, data-residency, and other applicable modes have distinct published rates and are not collapsed into the base column.",
            "- **Google:** the table shows Standard/global base rates represented by the catalog. Gemini 3.1 Pro Preview has a higher >200K context band. Gemini 3.6/3.7/3.8 Flash are represented at the current promotional $0.75/$3.75 Standard/global rate through 2026-12-31; the cited page publishes $1.50/$7.50 starting 2027-01-01. Non-global, Priority, Flex/Batch, grounding, tuning, tool, and modality charges can differ.",
            "",
            "## Accuracy boundary",
            "",
            "A provider invoice can differ because the applicable billable event may include context bands, cached input/cache writes, requested versus actual service tier, region, modalities, hosted tools, grounding/search, storage/runtime meters, fine-tuning, promotions/effective dates, account-specific pricing, retries/partial streams, or provider-side rule changes. TokenTotals therefore leads with **approximation** and preserves provenance/unknowns instead of pretending to be in lockstep with a provider billing system.",
            "",
            "The generated matrix is intentionally limited to models with a verified catalog entry used by this revision. It is not a list of every model a provider offers. Adding a model to the public matrix requires adding and validating its pricing record first.",
            "",
        ]
    )


def update_readme(text: str) -> str:
    section = render_readme_pricing_section()
    if README_START in text and README_END in text:
        before, rest = text.split(README_START, 1)
        _, after = rest.split(README_END, 1)
        return before.rstrip() + "\n\n" + section + "\n\n" + after.lstrip()

    insertion_marker = "## Budget-gate behavior"
    if insertion_marker not in text:
        raise RuntimeError(
            "README has no generated pricing block and no insertion marker; refusing to guess where to write it."
        )
    return text.replace(insertion_marker, section + "\n\n" + insertion_marker, 1)


if __name__ == "__main__":
    OUTPUT.write_text(render(), encoding="utf-8")
    README.write_text(update_readme(README.read_text(encoding="utf-8")), encoding="utf-8")
    print(f"Wrote {OUTPUT} and refreshed the verified pricing block in {README}")
