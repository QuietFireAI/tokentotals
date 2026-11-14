"""Print TokenTotals Turn Receipts recorded for Claude Code sessions.

Usage:
  tt_receipt.py                 last receipt, expanded, with its session total
  tt_receipt.py short           last receipt, one line
  tt_receipt.py session         every receipt in the latest session, one line each
  tt_receipt.py last N          last N receipts, one line each
  tt_receipt.py --session ID    limit to one session
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tokentotals_cc import receipts  # noqa: E402


def main(argv):
    session = None
    if "--session" in argv:
        i = argv.index("--session")
        session = argv[i + 1] if i + 1 < len(argv) else None
        argv = argv[:i] + argv[i + 2:]
    rs = receipts.read_receipts(session)
    if not rs:
        print("No Turn Receipts yet. One is written when a Claude Code turn finishes.")
        print(f"Ledger: {receipts.ledger_path()}")
        return 0
    latest_session = rs[-1]["session_id"]
    mode = argv[0] if argv else "expanded"
    if mode == "short":
        print(receipts.render_standard(rs[-1]))
    elif mode == "session":
        mine = [r for r in rs if r["session_id"] == latest_session]
        for r in mine:
            print(f"{r['created_at']}  {receipts.render_standard(r)}")
        tot = receipts.session_total(latest_session)
        print(f"Session total: {tot['receipts']} receipts, {tot['api_calls']} API calls, "
              f"${tot['known_list_equivalent_usd']:.4f} list price"
              + ("" if tot["complete"] else " (some receipts incomplete)"))
    elif mode == "last":
        n = int(argv[1]) if len(argv) > 1 and argv[1].isdigit() else 5
        for r in rs[-n:]:
            print(f"{r['created_at']}  {receipts.render_standard(r)}")
    else:
        print(receipts.render_expanded(rs[-1], receipts.session_total(latest_session)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
