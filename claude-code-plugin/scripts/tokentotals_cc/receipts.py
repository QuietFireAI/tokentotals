"""Turn Receipts for Claude Code, built from the session transcript.

Claude Code writes every API response it receives to the session transcript
(JSONL). Each assistant entry carries the provider's own ``usage`` object:
uncached input, cache writes split by 5-minute / 1-hour TTL, cache reads,
output and thinking tokens, service tier, inference geography and server-tool
counters. This module reads those entries, prices each API call with the
TokenTotals Anthropic engine, and groups the calls that finished since the
previous receipt into one Turn Receipt.

Nothing here reads prompt or response text into the ledger. Only usage
telemetry, model IDs, message IDs and timestamps are stored.
"""

import json
import os
import time
from pathlib import Path

from . import anthropic_pricing as ap

SCHEMA_VERSION = 1
LEDGER_NAME = "receipts.jsonl"


# ---------------------------------------------------------------- storage

def data_dir():
    root = os.environ.get("CLAUDE_PLUGIN_DATA") or os.path.join(
        os.path.expanduser("~"), ".tokentotals", "claude-code"
    )
    path = Path(root)
    path.mkdir(parents=True, exist_ok=True)
    return path


def ledger_path():
    return data_dir() / LEDGER_NAME


def _safe_session(session_id):
    return "".join(ch for ch in str(session_id or "unknown") if ch.isalnum() or ch in "-_")[:80] or "unknown"


def _seen_path(session_id):
    d = data_dir() / "seen"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{_safe_session(session_id)}.json"


def load_seen(session_id):
    p = _seen_path(session_id)
    if not p.exists():
        return set()
    try:
        return set(json.loads(p.read_text(encoding="utf-8")))
    except Exception:
        return set()


def save_seen(session_id, seen):
    p = _seen_path(session_id)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(sorted(seen)), encoding="utf-8")
    os.replace(tmp, p)


def append_receipt(receipt):
    with ledger_path().open("a", encoding="utf-8") as f:
        f.write(json.dumps(receipt, sort_keys=True) + "\n")


def read_receipts(session_id=None):
    p = ledger_path()
    if not p.exists():
        return []
    out = []
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except Exception:
                continue
            if session_id and r.get("session_id") != session_id:
                continue
            out.append(r)
    return out


# ------------------------------------------------------------- transcript

def read_transcript(path):
    entries = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except Exception:
                continue
    return entries


def subagent_transcripts(transcript_path):
    """Subagent API calls live in <session>/subagents/*.jsonl next to the main transcript."""
    base = Path(transcript_path)
    sub_dir = base.with_suffix("") / "subagents"
    if not sub_dir.is_dir():
        return []
    return sorted(str(p) for p in sub_dir.glob("*.jsonl"))


def collect_calls(entries):
    """Return one record per API response, in transcript order.

    Claude Code can write one response across several transcript lines (one per
    content block) that repeat the same message id and usage. Keep the last
    usage seen for each id, so a response is counted once.
    """
    calls = {}
    order = []
    for e in entries:
        if e.get("type") != "assistant":
            continue
        msg = e.get("message")
        if not isinstance(msg, dict):
            continue
        usage = msg.get("usage")
        model = msg.get("model")
        if not isinstance(usage, dict) or not model or model.startswith("<"):
            continue
        call_id = msg.get("id") or e.get("requestId") or e.get("uuid")
        if not call_id:
            continue
        if call_id not in calls:
            order.append(call_id)
        calls[call_id] = {
            "call_id": call_id,
            "model": model,
            "usage": usage,
            "timestamp": e.get("timestamp"),
            "sidechain": bool(e.get("isSidechain")),
        }
    return [calls[i] for i in order]


# ---------------------------------------------------------------- pricing

TOKEN_FIELDS = (
    ("input_tokens", "uncached_input"),
    ("cache_write_5m_tokens", "cache_write_5m"),
    ("cache_write_1h_tokens", "cache_write_1h"),
    ("cache_read_input_tokens", "cache_read"),
    ("output_tokens", "output"),
    ("thinking_tokens", "thinking"),
)


def _pico(usd):
    return int(round(usd * 1e12))


def build_receipt(session_id, calls, *, now=None):
    tokens = {name: 0 for _, name in TOKEN_FIELDS}
    known_pico = 0
    complete_pico = 0
    all_complete = True
    models = {}
    notes = []
    priced_calls = []
    verified = set()
    geos = set()

    for c in calls:
        r = ap.calculate_anthropic_cost(c["model"], c["usage"])
        n = r["usage"]
        for src, name in TOKEN_FIELDS:
            tokens[name] += int(n.get(src) or 0)
        known = r.get("known_list_equivalent_usd")
        total = r.get("total_cost_usd")
        if known is not None:
            known_pico += _pico(known)
        if total is not None:
            complete_pico += _pico(total)
        if not r.get("complete"):
            all_complete = False
        if r.get("verified_at"):
            verified.add(r["verified_at"])
        if r.get("inference_geo"):
            geos.add(str(r["inference_geo"]))
        for note in r.get("notes", []):
            if note not in notes:
                notes.append(note)
        m = models.setdefault(c["model"], {"calls": 0, "known_usd_pico": 0})
        m["calls"] += 1
        if known is not None:
            m["known_usd_pico"] += _pico(known)
        priced_calls.append({
            "call_id": c["call_id"],
            "model": c["model"],
            "timestamp": c.get("timestamp"),
            "sidechain": c.get("sidechain", False),
            "complete": bool(r.get("complete")),
            "total_cost_usd": total,
            "known_list_equivalent_usd": known,
            "components_usd": r.get("components_usd"),
            "long_context_applied": r.get("long_context_applied", False),
        })

    any_known = any(pc["known_list_equivalent_usd"] is not None for pc in priced_calls)
    if all_complete and priced_calls:
        basis = "provider_registry_complete"
        cost = complete_pico / 1e12
    elif any_known:
        basis = "known_list_equivalent_incomplete"
        cost = None
    else:
        basis = "unavailable"
        cost = None

    return {
        "schema_version": SCHEMA_VERSION,
        "receipt_id": f"cc-{int((now or time.time()) * 1000)}-{calls[-1]['call_id'][-8:]}" if calls else None,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now or time.time())),
        "session_id": session_id,
        "source": "claude_code_transcript",
        "api_calls": len(calls),
        "subagent_api_calls": sum(1 for c in calls if c.get("sidechain")),
        "models": {k: {"calls": v["calls"], "known_list_equivalent_usd": v["known_usd_pico"] / 1e12} for k, v in models.items()},
        "tokens": tokens,
        "estimated_cost_usd": cost,
        "known_list_equivalent_usd": known_pico / 1e12 if any_known else None,
        "cost_basis": basis,
        "pricing_verified_at": sorted(verified),
        "inference_geo": sorted(geos),
        "notes": notes,
        "calls": priced_calls,
        "disclaimer": "List-price estimate from Claude Code usage telemetry. Not an invoice. "
                      "Pro/Max subscription usage is not billed per token.",
    }


def receipt_for_new_calls(session_id, transcript_path, *, now=None):
    """Price every API call not yet on a receipt for this session.

    The transcript can lag the live conversation, so a call that lands late is
    picked up by the next receipt instead of being lost or double counted.
    """
    calls = collect_calls(read_transcript(transcript_path))
    for sub in subagent_transcripts(transcript_path):
        for c in collect_calls(read_transcript(sub)):
            c["sidechain"] = True
            calls.append(c)
    seen = load_seen(session_id)
    new = [c for c in calls if c["call_id"] not in seen]
    if not new:
        return None
    receipt = build_receipt(session_id, new, now=now)
    append_receipt(receipt)
    seen.update(c["call_id"] for c in new)
    save_seen(session_id, seen)
    return receipt


# -------------------------------------------------------------- rendering

def _k(n):
    n = int(n or 0)
    if n >= 1_000_000:
        return f"{n / 1_000_000:.2f}M"
    if n >= 10_000:
        return f"{n / 1000:.0f}k"
    if n >= 1000:
        return f"{n / 1000:.1f}k"
    return str(n)


def _usd(v):
    if v is None:
        return "unavailable"
    if v < 0.01:
        return f"${v:.4f}"
    return f"${v:.2f}"


def cost_label(receipt):
    if receipt["cost_basis"] == "provider_registry_complete":
        return _usd(receipt["estimated_cost_usd"])
    if receipt["cost_basis"] == "known_list_equivalent_incomplete":
        return f"at least {_usd(receipt['known_list_equivalent_usd'])} (incomplete)"
    return "unavailable"


def render_standard(receipt):
    t = receipt["tokens"]
    models = ", ".join(receipt["models"].keys())
    return (
        f"Turn Receipt: {cost_label(receipt)} · {receipt['api_calls']} API call"
        f"{'s' if receipt['api_calls'] != 1 else ''} · {models} · "
        f"in {_k(t['uncached_input'])} · cache write {_k(t['cache_write_5m'] + t['cache_write_1h'])} · "
        f"cache read {_k(t['cache_read'])} · out {_k(t['output'])}"
    )


def render_expanded(receipt, session_total=None):
    t = receipt["tokens"]
    lines = [
        "TokenTotals Turn Receipt",
        f"  receipt      {receipt['receipt_id']}",
        f"  session      {receipt['session_id']}",
        f"  estimate     {cost_label(receipt)}   basis: {receipt['cost_basis']}",
        f"  pricing      Anthropic list price, verified {', '.join(receipt['pricing_verified_at']) or 'n/a'}",
        f"  geography    {', '.join(receipt['inference_geo']) or 'not reported'}",
        f"  API calls    {receipt['api_calls']} ({receipt.get('subagent_api_calls', 0)} from subagents)",
        "  tokens",
        f"    uncached input   {t['uncached_input']:>12,}",
        f"    cache write 5m   {t['cache_write_5m']:>12,}",
        f"    cache write 1h   {t['cache_write_1h']:>12,}",
        f"    cache read       {t['cache_read']:>12,}",
        f"    output           {t['output']:>12,}",
        f"    (of which thinking {t['thinking']:,})",
        "  by model",
    ]
    for model, m in receipt["models"].items():
        lines.append(f"    {model:<22} {m['calls']:>3} calls  {_usd(m['known_list_equivalent_usd'])}")
    comps = {}
    for c in receipt["calls"]:
        for k, v in (c.get("components_usd") or {}).items():
            if v is not None:
                comps[k] = comps.get(k, 0) + v
    if comps:
        lines.append("  components (list price)")
        for k, v in comps.items():
            if v:
                lines.append(f"    {k:<16} {_usd(v):>12}")
    if receipt["notes"]:
        lines.append("  notes")
        for n in receipt["notes"]:
            lines.append(f"    - {n}")
    if session_total:
        lines.append(
            f"  session so far  {session_total['receipts']} receipts, {session_total['api_calls']} calls, "
            f"{_usd(session_total['known_list_equivalent_usd'])} list-price"
            + ("" if session_total["complete"] else " (some receipts incomplete)")
        )
    lines.append(f"  {receipt['disclaimer']}")
    return "\n".join(lines)


def session_total(session_id):
    rs = read_receipts(session_id)
    known = sum(_pico(r.get("known_list_equivalent_usd") or 0) for r in rs) / 1e12
    return {
        "receipts": len(rs),
        "api_calls": sum(r.get("api_calls", 0) for r in rs),
        "known_list_equivalent_usd": known,
        "complete": all(r.get("cost_basis") == "provider_registry_complete" for r in rs),
    }
