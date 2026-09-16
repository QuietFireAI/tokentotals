import argparse
import datetime


BOUNDARY = (
    "TokenTotals provides local turn receipts and cost pacing for AI agents. "
    "The local pacing threshold is local admission control, not provider-account clearance; "
    "permitted remote-provider requests still egress upstream."
)


def generate_ics(start_date_str="2026-09-17", output_path="TokenTotals_30Day_Launch_Plan.ics"):
    try:
        start_date = datetime.datetime.strptime(start_date_str, "%Y-%m-%d").date()
    except Exception:
        start_date = datetime.date.today() + datetime.timedelta(days=1)

    events = [
        (0, "09:00", 3, "tokentotals-hermes-userzero@quietfireai.com",
         "TokenTotals Hermes: User-Zero Live Receipt Proof",
         "Run TokenTotals with the TurnReceipt Hermes plugin in normal Hermes. Launch gate is a normal Hermes prompt and answer followed directly by the matching Turn Receipt. Preserve any failure. Browser/frontier testing is not the launch gate."),
        (1, "09:00", 3, "tokentotals-hermes-hardening@quietfireai.com",
         "TokenTotals Hermes: User-Zero Hardening and Recheck",
         "Repair only demonstrated user-zero defects using diagnose - one repair - recheck - archive evidence. Re-run simple turn, multi-call turn, plugin-disable, and TokenTotals-unavailable tests."),
        (2, "10:00", 2, "tokentotals-hermes-releasegate@quietfireai.com",
         "TokenTotals Hermes: Release Gate",
         "Promote only after live Hermes answer-to-receipt proof, Windows package proof, regression tests, and documentation reconciliation are all green. Do not substitute CI or TokenTotals slash-chat for the live gate."),
        (3, "10:00", 2, "tokentotals-hermes-demo@quietfireai.com",
         "TokenTotals Hermes: Record Real Launch Demo",
         "Record a real Hermes session showing ordinary prompt, ordinary answer, and Turn Receipt directly below it. No canned or hard-wired demo path. Show Expanded detail only after the basic receipt is visibly settled."),
        (5, "10:00", 2, "tokentotals-hermes-publicdrop@quietfireai.com",
         "TokenTotals Hermes: Public Drop",
         "Publish the Hermes-first release only if the live acceptance gate is proven. Position TokenTotals as the local accounting engine and Turn Receipt integration for Hermes. State browser/frontier work as continuing testing/reference work."),
        (7, "10:00", 2, "tokentotals-openclaw-start@quietfireai.com",
         "TokenTotals: Begin OpenClaw Integration",
         "Start the next first-class adapter after Hermes proof. Test stable turn correlation, multi-call/tool loops, retries, subagents where exposed, and one top-level Turn Receipt with inspectable children."),
        (14, "10:00", 1, "tokentotals-browser-revisit@quietfireai.com",
         "TokenTotals: Review Browser/Frontier Testing Track",
         "Reassess browser/frontier integrations only after Hermes/OpenClaw evidence and available project resources justify renewed testing. Initial browser work remains preserved as testing/reference work; it is not a launch dependency."),
    ]

    now_stamp = datetime.datetime.now(datetime.UTC).strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//QuietFireAI//TokenTotals Hermes Launch Plan//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:TokenTotals Hermes-First Launch Plan",
        "X-WR-TIMEZONE:America/New_York",
    ]

    for offset, time_text, duration_hours, uid, title, description in events:
        event_date = start_date + datetime.timedelta(days=offset)
        hour, minute = map(int, time_text.split(":"))
        start = datetime.datetime(event_date.year, event_date.month, event_date.day, hour, minute)
        end = start + datetime.timedelta(hours=duration_hours)
        desc = f"{description} {BOUNDARY}".replace("\n", "\\n")
        lines.extend([
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{now_stamp}",
            f"DTSTART:{start.strftime('%Y%m%dT%H%M%S')}",
            f"DTEND:{end.strftime('%Y%m%dT%H%M%S')}",
            f"SUMMARY:{title}",
            f"DESCRIPTION:{desc}",
            "STATUS:CONFIRMED",
            "TRANSP:OPAQUE",
            "END:VEVENT",
        ])

    lines.append("END:VCALENDAR")
    with open(output_path, "w", encoding="utf-8") as handle:
        handle.write("\r\n".join(lines) + "\r\n")
    print(f"Generated {output_path} starting on {start_date_str} ({len(events)} events)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the TokenTotals Hermes-first launch calendar (.ics)")
    parser.add_argument("--start", default="2026-09-17", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--out", default="TokenTotals_30Day_Launch_Plan.ics", help="Output .ics file path")
    args = parser.parse_args()
    generate_ics(args.start, args.out)
