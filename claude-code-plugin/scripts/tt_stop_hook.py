"""Claude Code Stop hook: write a Turn Receipt for the turn that just ended.

Reads the hook JSON on stdin, prices the new API calls in the transcript and
prints {"systemMessage": "..."} so Claude Code shows a one-line receipt.
Always exits 0: a Stop hook that exits 2 would block Claude from stopping.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return
    transcript = payload.get("transcript_path")
    session_id = payload.get("session_id") or "unknown"
    if not transcript or not os.path.exists(transcript):
        return
    from tokentotals_cc import receipts

    receipt = receipts.receipt_for_new_calls(session_id, transcript)
    if receipt is None:
        return
    print(json.dumps({"systemMessage": receipts.render_standard(receipt)}))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # never break the user's session
        try:
            sys.stderr.write(f"TokenTotals hook error: {exc}\n")
        except Exception:
            pass
    sys.exit(0)
