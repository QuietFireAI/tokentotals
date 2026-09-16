# TokenTotals — Hermes User Guide

> **Launch experience:** use Hermes normally; after a completed Hermes answer, TokenTotals places the matching Turn Receipt directly beneath it.

**Current status:** pre-release candidate pending live user-zero proof.  
**Primary launch surface:** Hermes Agent on Windows.  
**Next planned surface:** OpenClaw.  
**TokenTotals `/chat`:** engineering/reference surface only.

## 1. What you are installing

The Hermes launch uses two local pieces:

1. **TokenTotals for Windows** — the local receipt/accounting engine.
2. **TurnReceipt Hermes plugin** — observes Hermes' documented turn/request lifecycle telemetry and binds one receipt to the completed Hermes turn.

You continue using Hermes as Hermes. TokenTotals is not a replacement chat client.

```text
Hermes prompt
   ↓
Hermes model/tool work
   ↓
Hermes answer
   ↓
TURN RECEIPT
   ↓
TurnReceipt.com
```

The model does not write the receipt. TokenTotals calculates it from available usage evidence and its deterministic pricing/accounting logic. No second model call is required merely to calculate or render the receipt.

## 2. Before you start

For the current pre-release candidate you need:

- Windows 10 or Windows 11;
- a working Hermes installation and provider/model configuration;
- the TokenTotals Hermes Windows candidate ZIP; and
- the TurnReceipt Hermes plugin ZIP.

Hermes supports native Windows. A WSL install is not required for the CLI test path.

If Hermes is already installed and working, do not reinstall it just for TokenTotals.

## 3. Start TokenTotals

1. Extract the TokenTotals Hermes candidate ZIP into its own folder.
2. Run `TokenTotals.exe`.
3. If Windows SmartScreen appears for the unsigned pre-release candidate, record exactly what Windows shows before choosing whether to continue.
4. Confirm the TokenTotals tray icon appears.
5. Leave TokenTotals running while using Hermes.

TokenTotals runs its local service on loopback. It normally starts at `127.0.0.1:8080` and can use another port in the `8080-8089` range if needed.

You do **not** need to open TokenTotals `/chat` to use the Hermes integration.

## 4. Install the Hermes plugin

Hermes user plugins live under the active Hermes home in a `plugins` directory. On native Windows the normal Hermes home is under `%LOCALAPPDATA%\hermes`.

The final plugin folder must contain both:

```text
plugin.yaml
__init__.py
```

and should be installed as the `turnreceipt` plugin directory under the active Hermes plugin path.

If your plugin ZIP extracts into an extra wrapper directory, make sure the actual `turnreceipt` folder—not the wrapper ZIP folder—is what ends up in Hermes' `plugins` directory.

## 5. Ask Hermes to validate the plugin

Open a new PowerShell or Windows Terminal and run Hermes' own plugin doctor against the installed TurnReceipt plugin.

Example shape:

```powershell
hermes plugins doctor "$env:LOCALAPPDATA\hermes\plugins\turnreceipt" --ci
```

If your Hermes home differs, use the path Hermes is actually using.

### Expected result

Plugin Doctor should finish successfully without registration errors.

### If it fails

Stop there. Save the entire output. Do not manually edit plugin Python files or install random dependencies to make the test pass.

A failed Plugin Doctor run is a product/test failure to diagnose, not something the user is expected to repair.

## 6. Enable TurnReceipt in Hermes

Run:

```powershell
hermes plugins enable turnreceipt
```

Then verify it appears in Hermes' plugin listing:

```powershell
hermes plugins list
```

### Expected result

`turnreceipt` is visible and enabled.

If Hermes asks for explicit consent/activation, use the normal Hermes plugin workflow. TokenTotals does not bypass Hermes' plugin permission model.

## 7. Run the real product test

Start normal Hermes chat:

```powershell
hermes chat
```

Ask **any ordinary question you choose**. Do not use a canned TokenTotals phrase unless you want to.

Examples are deliberately unnecessary: the integration is supposed to work for a normal Hermes turn, not a demo prompt.

### The pass condition

For the same turn you should see:

```text
[normal Hermes answer]

TURN RECEIPT
----------------------------------------
Provider               ...
Model                  ...
Input tokens           ...
Cached input           ... or Unavailable
Output tokens          ...
Turn estimate          ... or Unavailable
...
----------------------------------------
TurnReceipt.com
```

The exact fields depend on what the Hermes/provider transaction exposes.

**The receipt must appear directly after the matching Hermes answer.**

A ledger entry somewhere else, a TokenTotals dashboard update, `/chat`, or a green CI run does not substitute for this behavior.

## 8. Run three different turns

After the first turn succeeds, run at least two more unrelated prompts.

The goal is to verify that:

- each Hermes answer receives its own receipt;
- values can differ naturally from turn to turn;
- receipt placement stays with the correct answer; and
- a previous receipt is not reused or duplicated.

There is no hard-wired test phrase or expected canned token/cost value.

## 9. Test a multi-call/tool turn

After simple turns work, ask Hermes to perform an ordinary task that causes a tool loop or more than one provider API request.

The intended accounting model is:

```text
one human Hermes turn
  ├─ provider request 1
  ├─ provider request 2
  └─ provider request 3
        ↓
one top-level Turn Receipt
```

TokenTotals prices successful child provider transactions individually when it has sufficient telemetry, then sums them into the top-level Hermes turn receipt.

Failed/retried API attempts remain failure evidence; they do not become invented successful child charges.

## 10. Standard and Expanded modes

The default is **Standard**.

Standard is the compact receipt intended to live directly beneath the answer.

To request deeper terminal detail for development/testing, set:

```powershell
$env:HERMES_TURNRECEIPT_MODE = "expanded"
```

Start a new Hermes process after changing the environment variable.

Expanded uses the same canonical receipt object. It can expose deeper usage/reconciliation information and the number/details of child API transactions where available.

Switching display mode does not trigger another model call and does not recalculate the model answer.

## 11. What the receipt labels mean

**TokenTotals estimate** means TokenTotals had enough telemetry/pricing information for the applicable deterministic accounting path.

**Incomplete / partial estimate** means some cost can be reconstructed but one or more dimensions remain unresolved.

**Cost unavailable** means TokenTotals cannot establish a defensible amount for that turn.

Unavailable is not zero.

A Turn Receipt is an independent estimate. It is not the provider invoice, provider account balance, or provider spending authorization.

## 12. Privacy boundary

The Hermes plugin's TokenTotals accounting payload excludes:

- prompt text;
- assistant answer text;
- conversation history;
- tool arguments/results;
- API keys;
- cookies;
- authorization headers; and
- hidden reasoning content.

For exact answer-to-receipt placement, the current CLI adapter can hash the answer in memory and use that digest only as a short-lived binding key. The answer text itself is not sent to TokenTotals or written into the Hermes evidence store by this integration.

TokenTotals' local application data remains under the user's TokenTotals data directory, normally `%USERPROFILE%\.tokentotals`.

## 13. What to do when something fails

For user-zero testing, use this rule:

> **First unexpected behavior: stop, preserve it, report it.**

Do not repair around the product by:

- editing plugin Python files;
- pip-installing guessed dependencies into Hermes;
- changing Hermes source;
- copying receipts manually;
- switching to TokenTotals `/chat` to claim success; or
- inventing missing telemetry.

Useful evidence is:

- screenshot;
- exact command entered;
- complete error text;
- whether TokenTotals was still running;
- whether `turnreceipt` showed enabled; and
- which Hermes/provider/model you were using.

Failures are part of the validation record.

## 14. Clean disable test

Disable the integration:

```powershell
hermes plugins disable turnreceipt
```

Start a fresh Hermes process and send a normal prompt.

### Expected result

Hermes behaves normally and no Turn Receipt appears.

This proves the integration is additive rather than required for Hermes to function.

Re-enable afterward with:

```powershell
hermes plugins enable turnreceipt
```

## 15. TokenTotals unavailable test

With the plugin enabled, stop TokenTotals and start a fresh Hermes session.

### Expected result

Hermes should still answer normally. The receipt cannot settle because the local TokenTotals engine is unavailable, but the integration must not break the model answer.

Restart TokenTotals before continuing receipt tests.

## 16. Browser/reference surfaces

TokenTotals still contains a built-in browser page at `/chat` and experimental browser-extension work.

For the Hermes launch these are **testing/reference surfaces only**.

`/chat` is useful for controlled testing of TokenTotals' accounting engine, renderer and provider plumbing. It is not where a Hermes user is expected to move their conversation.

Browser extensions remain experimental because consumer AI websites may not expose the same stable transaction/usage telemetry Hermes exposes. They are not part of the Hermes launch promise.

## 17. Launch acceptance

The Hermes build can be promoted from candidate only after a real clean-machine run demonstrates all of the following:

- ordinary Hermes prompt;
- ordinary Hermes answer unchanged;
- matching Turn Receipt directly beneath that answer;
- stable same-turn correlation;
- no extra model generation for the receipt;
- missing telemetry left unavailable;
- simple and multi-call turns reconcile with Hermes observer evidence;
- plugin disable leaves Hermes normal;
- TokenTotals failure does not break Hermes; and
- restart/new turns do not cross-bind receipts.

Until that behavior is demonstrated, this documentation calls the build a **candidate**, not a finished release.

## 18. Next surface

After the Hermes gate is proven, TokenTotals' next planned first-class integration is OpenClaw.

OpenClaw will get its own adapter and validation evidence. It will not be documented as complete merely because the Hermes architecture exists.
