# TokenTotals User Guide

> **Turn Receipts for AI — explained without requiring a developer background.**

TokenTotals is a local Windows application that sits between a supported AI client and the selected AI provider. It records privacy-limited usage telemetry for completed turns and turns that information into an independent **Turn Receipt**.

A Turn Receipt is **not a provider invoice**. It is TokenTotals' record of what it could observe, derive, reconcile, and estimate for that turn. Provider billing/account records remain authoritative.

---

## 1. What TokenTotals does

When you send a supported AI request through TokenTotals, the basic flow is:

```text
Your question
   ↓
TokenTotals local proxy
   ↓
Selected AI provider/model
   ↓
Normal model answer
   ↓
Turn Receipt for that completed turn
```

The model's answer is not rewritten to add receipt text. TokenTotals keeps the normal answer intact and associates a separate receipt with the completed turn.

In the built-in TokenTotals chat surface, that looks like:

```text
Question
Answer
TURN RECEIPT

Question
Answer
TURN RECEIPT
```

The deeper/expanded view can also show aggregate information for the current thread.

---

## 2. Starting TokenTotals on Windows

1. Download the Windows ZIP from the TokenTotals GitHub release.
2. Extract the ZIP to a folder of your choice.
3. Run `TokenTotals.exe`.
4. TokenTotals starts a local service on your own computer, normally beginning at:

   `http://127.0.0.1:8080`

   If that port is already occupied, TokenTotals checks ports `8080` through `8089` for an available local port.
5. A TokenTotals tray icon appears in the Windows notification area.

TokenTotals binds its local control surface to `127.0.0.1` (your own computer). Requests that you deliberately route through TokenTotals can still go from TokenTotals to the selected upstream AI provider.

---

## 3. Opening the chat and dashboard

### Turn Receipt Chat

Open:

`http://127.0.0.1:8080/chat`

Use the actual port shown by TokenTotals if it selected a different port.

The chat surface lets you:

- choose a model from the local TokenTotals model registry;
- enter the provider API key needed for that model;
- choose **Standard receipt** or **Expanded receipt**;
- begin a new thread; and
- send a message through TokenTotals.

The API key entered on this page is kept in the page session for sending the request. TokenTotals does not write that API key into the Turn Receipt ledger.

### Dashboard

Open:

`http://127.0.0.1:8080/dashboard`

The dashboard is a deeper diagnostic/control surface. It is useful for local pacing, Turn Notices, current thread telemetry, and detailed accounting information.

You can also double-click or use the TokenTotals tray icon to open the dashboard.

---

## 4. Standard vs. Expanded receipts

### Standard receipt

Standard is the default compact display. It is intended to answer the immediate questions:

- Which provider/model handled this turn?
- How many input, cached-input, and output tokens were recorded when available?
- What is TokenTotals' estimated cost for this turn?
- What pricing/estimate status applies?
- What is the receipt ID?

### Expanded receipt

Expanded shows the same canonical Turn Receipt with more detail. Depending on what the provider exposes, it can include:

- observed vs. derived token values;
- reasoning/thinking tokens;
- cache write/create tokens;
- tool-related usage;
- residual/unclassified tokens;
- reconciliation information;
- component cost math and effective rates when reproducible;
- requested/canonical/observed model identity;
- estimate completeness and provenance; and
- current aggregate information for the thread.

Changing Standard/Expanded changes the **presentation**, not the underlying accounting. TokenTotals does not calculate two different receipts.

Your receipt display preference is stored locally by the browser for the TokenTotals chat page.

---

## 5. What the estimate labels mean

TokenTotals deliberately shows uncertainty instead of hiding it.

### `TokenTotals estimate`

TokenTotals had enough provider telemetry and pricing information to perform its normal provider reconstruction for the turn.

It is still an independent estimate, not the provider invoice.

### `Fallback estimate`

TokenTotals did not have enough telemetry for its normal reconstruction and used a secondary cost source.

The fallback amount may be **higher or lower** than the provider's eventual invoice.

### `List-equivalent estimate`

TokenTotals could reconstruct a known public list-equivalent portion, but account-specific or unobservable adjustments may exist.

### `Incomplete estimate`

TokenTotals recorded an amount, but at least one pricing or telemetry dimension remains unresolved.

### `Cost unavailable`

TokenTotals does not have a defensible cost estimate for that turn.

**Unavailable does not mean zero.** TokenTotals does not silently convert missing information into `$0.00`.

---

## 6. Observed, derived, and unavailable

Expanded receipts distinguish the basis of telemetry values.

- **Observed** — reported by the provider/response telemetry available to TokenTotals.
- **Derived** — calculated from other defensible observed values.
- **Unavailable** — TokenTotals cannot establish the value from the information available to it.

This distinction matters. A neat-looking zero can be more misleading than an honest blank/unavailable value.

---

## 7. Thread totals

Each Turn Receipt is bound to one completed turn by a stable TokenTotals receipt/turn ID.

The deeper thread view can aggregate completed receipts for the conversation and report information such as:

- number of completed turns;
- cumulative estimated thread cost;
- how many turns have usable cost estimates;
- complete vs. partial cost coverage; and
- model/provider mix and deeper telemetry where available.

A thread aggregate is still based on TokenTotals estimates. It is not a provider account balance.

---

## 8. Local pacing threshold

TokenTotals includes an optional local pacing control. The default local threshold is currently `$10.00` per local daily state period unless the user changes the configuration.

This threshold is **not** your provider's spending limit, account balance, credit balance, or authorization to spend.

It only controls new requests that are routed through this TokenTotals process.

### Tray colors

- **Green** — below the configured local warning threshold.
- **Yellow** — nearing the configured local pacing threshold.
- **Red** — the TokenTotals local pacing lock is active.

The default warning point is `75%` of the configured local pacing threshold.

### `+$5 Local Threshold`

The tray/dashboard quick-boost control raises the TokenTotals local pacing threshold by `$5.00`.

It does **not** add money or credit to a provider account.

### When the local pacing lock is active

TokenTotals pauses new requests routed through this local proxy until the user acknowledges/unlocks it or changes the local threshold.

It does not stop:

- requests sent directly to a provider outside TokenTotals;
- provider work that was already in flight; or
- provider-account billing outside the TokenTotals proxy.

---

## 9. Turn Notice

Turn Notice is an optional per-turn local reminder.

When enabled, you choose a positive dollar threshold. TokenTotals can then notify you when a turn estimate reaches the configured reminder level.

Turn Notice is **not** a provider spending authorization, provider warning, or provider-account balance.

If you do not want Turn Notice, leave it disabled or use the dashboard's **Disable** control.

---

## 10. New Thread

The **New thread** button in TokenTotals chat:

- clears the visible TokenTotals chat transcript in that page;
- starts a new local thread ID; and
- starts a new thread aggregate for subsequent receipts.

It does not erase previously written Turn Receipt ledger records.

---

## 11. What TokenTotals stores locally

TokenTotals keeps its local application files under:

```text
%USERPROFILE%\.tokentotals
```

Important files include local configuration/state and the append-only Turn Receipt ledger.

The Turn Receipt ledger is intentionally privacy-limited. It is designed around usage/accounting telemetry rather than conversation content.

TokenTotals does **not** intentionally put the following into the Turn Receipt ledger:

- prompt text;
- model answer text;
- provider API keys; or
- hidden model reasoning.

The built-in chat page necessarily holds the current visible conversation in that browser page while you use it so it can send the conversational context on subsequent turns. That is separate from the Turn Receipt ledger.

---

## 12. How to stop TokenTotals

### Stop it now

Use the TokenTotals tray icon and choose:

**Exit**

That stops the TokenTotals desktop process and its local proxy.

**Closing the browser tab does not stop TokenTotals.** The tray process is the application.

### Stop routing another app through TokenTotals

If you previously configured an IDE, script, or other AI client to use the TokenTotals localhost/base URL, restore that client's provider/base-URL configuration to the original provider setting.

TokenTotals cannot intercept calls that you do not route through it.

### Remove the Windows ZIP application

The ZIP release is portable rather than a traditional system installer.

1. Exit TokenTotals from the tray.
2. Delete the extracted TokenTotals application folder if you no longer want the executable.

Your local TokenTotals history/settings under `%USERPROFILE%\.tokentotals` remain unless **you** choose to delete that folder as well.

Deleting that local data folder removes local TokenTotals records/settings stored there. Do this only if you no longer need those records.

---

## 13. Common questions

### Is the Turn Receipt my provider bill?

No. It is an independent TokenTotals usage estimate/evidence record. The provider's billing/account record remains authoritative.

### Why does my TokenTotals estimate differ from another tool?

Different tools may have different telemetry, pricing tables, timing, model mappings, account-specific information, or fallback behavior. TokenTotals is designed to expose its basis and uncertainty instead of hiding those differences.

### Why is a field unavailable instead of zero?

Because TokenTotals cannot prove it was zero. Missing telemetry and observed zero are not the same fact.

### Why does a receipt take a moment to appear?

The model answer can finish before all post-response accounting has settled. TokenTotals binds the answer to a server-owned receipt ID and retrieves the settled receipt when it becomes available.

### Does Expanded mode cost more?

No additional model call is required merely to expand an already generated Turn Receipt. It is another rendering of the same local receipt data.

### Can I use TokenTotals without the built-in chat page?

Yes. TokenTotals exposes an OpenAI-compatible local proxy and Turn Receipt APIs for compatible clients/integrations. The built-in `/chat` page is the simplest way to see the receipt-in-conversation experience.

---

## 14. The simplest mental model

Think of TokenTotals like a local receipt printer attached to AI usage:

- the AI provider still provides the service;
- TokenTotals observes the usage information legitimately available to it;
- TokenTotals keeps the model answer separate;
- TokenTotals calculates what it can defend;
- TokenTotals labels what it cannot defend; and
- after the turn, TokenTotals gives you the receipt.

**Question → Answer → Turn Receipt → Repeat.**

For technical details, calculation rules, API routes, and implementation boundaries, see the repository README, `TURN_RECEIPTS.md`, and `CALCULATION_TRANSPARENCY.md`.


---

## 15. Exporting a thread for audit

The Turn Receipt chat includes an **Export CSV** button. It becomes available after the current thread has at least one settled Turn Receipt.

The download is a spreadsheet-friendly CSV containing one row for each completed turn recorded in that thread. It is generated from the same canonical Turn Receipt data used by the on-screen receipts; TokenTotals does not create a second accounting calculation just for the export.

The export includes fields such as:

- receipt and thread IDs;
- turn number and completion time;
- provider and model identity;
- available token categories and their observed/derived basis;
- TokenTotals turn estimate, estimate status, and pricing basis;
- running thread estimate;
- cost-coverage status; and
- latency when available.

The audit CSV intentionally does **not** include prompt text, model answer text, provider API keys, or hidden model reasoning.

A missing cost remains a blank value and changes the running coverage to partial/unavailable as appropriate. TokenTotals does not turn missing cost information into `$0`. An actual observed/recorded zero remains a real zero.

Text cells are escaped before export when necessary so values beginning like spreadsheet formulas cannot execute as formulas when the CSV is opened in Excel or similar software.

The current API route for the same export is:

```text
GET /api/threads/<thread_id>/turn-receipts.csv
```

The CSV is intended for ordinary spreadsheet review, accounting reconciliation, research, reimbursement records, or audit work. It remains a TokenTotals usage-estimate record; provider billing/account records remain authoritative.
