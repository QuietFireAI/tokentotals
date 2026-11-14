---
description: Show the TokenTotals Turn Receipt for the last finished turn (args - short, session, last N)
argument-hint: "[short | session | last N]"
allowed-tools: Bash(sh:*)
---

!`sh "${CLAUDE_PLUGIN_ROOT}/bin/tokentotals-run" tt_receipt.py $ARGUMENTS`

Show the TokenTotals output above to the user exactly as printed, inside a code block. Do not add analysis or change any number.
