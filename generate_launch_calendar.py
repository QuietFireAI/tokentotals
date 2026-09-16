import datetime
import argparse
import sys
from pathlib import Path

def generate_ics(start_date_str="2026-09-22", output_path="TokenTotals_30Day_Launch_Plan.ics"):
    try:
        start_date = datetime.datetime.strptime(start_date_str, "%Y-%m-%d").date()
    except Exception:
        start_date = datetime.date.today() + datetime.timedelta(days=7)

    events = [
        {
            "day_offset": 0,
            "title": "🛡️ TokenTotals Launch: Staging & 60s Demo Recording",
            "desc": "Phase 1: Verify GitHub repo (github.com/QuietFireAI/tokentotals). Record 60-second screen capture of Cursor hitting the configured local pacing threshold, audio chime, and topmost 'I UNDERSTAND' local lockout modal.",
            "duration_hours": 2,
            "time": "10:00"
        },
        {
            "day_offset": 3,
            "title": "🚀 TokenTotals: Hacker News 'Show HN' Launch",
            "desc": "Phase 2: Post 'Show HN: TokenTotals - Local turn receipts and cost pacing for AI agents' at 8:00 AM ET. Monitor comments and engage with the community.",
            "duration_hours": 3,
            "time": "08:00"
        },
        {
            "day_offset": 4,
            "title": "💬 TokenTotals: Reddit Community Drop",
            "desc": "Phase 2: Post tailored angles across subreddits:\n- r/Cursor & r/Windsurf (Local pacing threshold + turn telemetry)\n- r/LocalLLaMA (Local loopback control plane; permitted provider calls still egress upstream)\n- r/OpenAI (Why local turn-level cost telemetry matters between provider billing updates).",
            "duration_hours": 2,
            "time": "11:00"
        },
        {
            "day_offset": 5,
            "title": "🐦 TokenTotals: X/Twitter Launch Thread",
            "desc": "Phase 2: Publish 4-tweet thread with the 60s demo video, GitHub repo link, ORCID attribution, and Buy Me a Coffee link.",
            "duration_hours": 1,
            "time": "12:00"
        },
        {
            "day_offset": 7,
            "title": "✍️ TokenTotals: HackerNoon & Medium Article Drop",
            "desc": "Phase 3: Publish deep dive: 'The $400 Morning Surprise: Why Autonomous AI Workflows Need Local Cost Telemetry and Pacing' on HackerNoon and Medium.",
            "duration_hours": 2,
            "time": "09:00"
        },
        {
            "day_offset": 10,
            "title": "📰 TokenTotals: 404 Media & Tech Press Pitch",
            "desc": "Phase 3: Send personalized pitches to independent tech journalists (404 Media, Ars Technica) highlighting an indie engineer building transparent local AI cost telemetry and pacing tooling.",
            "duration_hours": 2,
            "time": "14:00"
        },
        {
            "day_offset": 15,
            "title": "🏆 TokenTotals: Product Hunt Launch Day",
            "desc": "Phase 4: Launch on Product Hunt at 12:01 AM PT. Engage with hunters, answer questions in comments, and share Product Hunt link on socials.",
            "duration_hours": 4,
            "time": "03:00"
        },
        {
            "day_offset": 17,
            "title": "📬 TokenTotals: AI Newsletter Submissions",
            "desc": "Phase 4: Submit to top AI newsletters:\n- Ben's Bites\n- TLDR AI\n- The Rundown\n- List on There's An AI For That (TAAFT) & AlternativeTo.",
            "duration_hours": 2,
            "time": "10:00"
        },
        {
            "day_offset": 22,
            "title": "📣 TokenTotals: Regional Press & QuietFire Bridge",
            "desc": "Phase 5: Distribute regional press release highlighting local software innovation. Publish announcement on how TokenTotals integrates as the local cost-telemetry and pacing layer for TelsonBase and DispatcherAgents.",
            "duration_hours": 2,
            "time": "10:00"
        },
        {
            "day_offset": 29,
            "title": "📈 TokenTotals: 30-Day Retrospective & Community Review",
            "desc": "Phase 5: Audit GitHub stars, forks, and issues. Review community pull requests and plan the next roadmap from verified runtime behavior and community feedback.",
            "duration_hours": 2,
            "time": "15:00"
        }
    ]

    now_stamp = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")

    ics_lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//QuietFireAI//TokenTotals Launch Plan//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:TokenTotals 30-Day Launch Plan",
        "X-WR-TIMEZONE:America/New_York"
    ]

    for idx, ev in enumerate(events):
        ev_date = start_date + datetime.timedelta(days=ev["day_offset"])
        hour, minute = map(int, ev["time"].split(":"))
        dt_start = datetime.datetime(ev_date.year, ev_date.month, ev_date.day, hour, minute)
        dt_end = dt_start + datetime.timedelta(hours=ev["duration_hours"])

        dt_start_str = dt_start.strftime("%Y%m%dT%H%M%S")
        dt_end_str = dt_end.strftime("%Y%m%dT%H%M%S")
        clean_desc = ev["desc"].replace("\n", "\\n")

        ics_lines.extend([
            "BEGIN:VEVENT",
            f"UID:tokentotals-launch-day{ev['day_offset']}-{idx}@quietfireai.com",
            f"DTSTAMP:{now_stamp}",
            f"DTSTART:{dt_start_str}",
            f"DTEND:{dt_end_str}",
            f"SUMMARY:{ev['title']}",
            f"DESCRIPTION:{clean_desc}",
            "STATUS:CONFIRMED",
            "TRANSP:OPAQUE",
            "BEGIN:VALARM",
            "ACTION:DISPLAY",
            "DESCRIPTION:Reminder: TokenTotals Launch Milestone",
            "TRIGGER:-PT30M",
            "END:VALARM",
            "END:VEVENT"
        ])

    ics_lines.append("END:VCALENDAR")

    output_content = "\r\n".join(ics_lines)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(output_content)
    print(f"Generated {output_path} starting on {start_date_str} ({len(events)} events)")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate TokenTotals 30-Day Launch Calendar (.ics)")
    parser.add_argument("--start", default="2026-09-22", help="Start date (YYYY-MM-DD), e.g. 2026-09-22")
    parser.add_argument("--out", default="TokenTotals_30Day_Launch_Plan.ics", help="Output .ics file path")
    args = parser.parse_args()
    generate_ics(args.start, args.out)
