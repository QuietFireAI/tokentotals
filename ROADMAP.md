# TokenTotals Roadmap

TokenTotals is now organized around one launch requirement rather than a collection of partially related surfaces:

> **Use an existing AI/agent work surface normally. When the answer finishes, the matching Turn Receipt appears directly beneath that answer.**

The first launch surface is **Hermes Agent**. OpenClaw is next. The built-in TokenTotals browser chat and browser-extension work remain engineering/reference tracks and do not define launch success.

## Why the roadmap changed

The project's initial testing concept focused on frontier-model/browser workflows. That work proved important accounting and rendering components, but continuing to validate that path at the required evidence standard became **too cost-intensive for the project on our end**.

The project therefore chose to change the launch dependency rather than lower the proof standard or keep spending against an expensive test surface. Hermes became the launch target because its documented observer lifecycle exposes stable transaction identities and normalized usage telemetry. That gives TokenTotals a better environment for proving the real product behavior.

The earlier browser/frontier work remains a testing/reference track and may continue. It is no longer allowed to block launch.

The resulting sequence is:

```text
initial frontier/browser testing
        ↓
core receipt machinery established
        ↓
frontier testing becomes too cost-intensive for sustained launch validation
        ↓
Hermes launch integration
        ↓
OpenClaw integration
        ↓
continued browser/frontier adapter work when justified
```

## Current launch sequence

### 1. Hermes integration candidate

**Status:** implemented; automated proof green; live user-zero acceptance pending.

The Hermes build uses Hermes' documented observer lifecycle for stable session, turn and provider-request correlation.

Implemented candidate behavior includes:

- per-Hermes-turn scope;
- successful provider API-request capture;
- retry/error evidence capture;
- deterministic child-transaction pricing through TokenTotals provider calculators;
- one top-level receipt per human Hermes turn;
- append-only privacy-limited evidence;
- Standard and Expanded terminal receipt rendering;
- guarded inline placement after the Hermes answer;
- fail-open behavior when TokenTotals is unavailable; and
- no second model call for receipt generation.

The candidate has passed:

- full TokenTotals regression CI;
- Hermes-specific contract tests;
- a pinned real-Hermes `plugins doctor --ci` run;
- Windows candidate build;
- packaged TokenTotals smoke test; and
- Windows packaging contract recheck.

Those results prove implementation/package properties. They do **not** yet prove the end-user product experience.

### 2. Hermes live user-zero gate

**Status:** active launch gate.

The Hermes build is promoted only when a clean user run demonstrates:

```text
normal Hermes prompt
        ↓
normal Hermes answer
        ↓
matching Turn Receipt directly underneath
```

Required acceptance:

1. ordinary user-created prompt, not a canned demo requirement;
2. answer rendered unchanged;
3. receipt appears immediately after that exact answer;
4. stable same-turn correlation;
5. no second LLM generation for receipt accounting/rendering;
6. truthful missing-data behavior;
7. receipt values derive from the actual Hermes transaction evidence;
8. multiple successive turns do not cross-bind;
9. a multi-call/tool turn produces one top-level receipt with child transaction accounting;
10. plugin disable returns Hermes to normal behavior; and
11. TokenTotals failure does not prevent Hermes from answering.

A screenshot, ledger record, CI job or TokenTotals `/chat` receipt cannot substitute for this live gate.

### 3. Hermes hardening after user-zero

**Status:** conditional on live findings.

If user-zero exposes defects, use the project repair discipline:

> diagnose → one repair → recheck → archive evidence → continue

Do not redesign unrelated architecture while closing a demonstrated usability/runtime defect.

Likely post-proof hardening areas include:

- installer/plugin packaging ergonomics;
- automatic discovery of the active local TokenTotals port;
- clearer plugin enable/disable UX;
- upstream Hermes compatibility checks;
- tool-loop/retry stress tests; and
- release signing/distribution decisions.

### 4. Hermes launch documentation and release

**Status:** documentation rewritten around Hermes; public release waits for the live gate.

Launch-facing documentation must describe Hermes as the primary surface.

The user journey is not “move your conversation into TokenTotals.” It is:

> **keep using Hermes; TokenTotals receipts the transaction.**

Launch materials must not claim support beyond what has been proven. In particular:

- browser `/chat` is a reference harness, not the product destination;
- browser/frontier integrations are continuing testing/research work;
- provider account/invoice records remain authoritative;
- missing telemetry remains unavailable; and
- green automated tests are not described as live product proof.

### 5. OpenClaw integration

**Status:** next first-class integration after Hermes proof.

OpenClaw will receive an independent adapter and evidence set. It is not treated as a rename of the Hermes integration.

The OpenClaw track will specifically test:

- one human instruction spanning several model/tool transactions;
- OpenClaw's existing usage/cost telemetry;
- retries and tool loops;
- subagent/child execution where exposed;
- stable correlation to the user-visible answer; and
- one top-level Turn Receipt with inspectable children.

The same rules apply: the model does not calculate its receipt, missing data is not zero, and a real in-surface receipt is the acceptance gate.

### 6. Lobster workflow stress test

**Status:** planned after OpenClaw core integration.

Lobster is useful as a workflow stress case because retries, branches and workflow-level cost controls can create richer transaction trees.

The test question is whether one workflow-level receipt with child transactions remains understandable and defensible.

### 7. Browser/frontier surfaces

**Status:** experimental/testing track; not launch-critical.

TokenTotals retains two browser-oriented surfaces:

- built-in `/chat` reference client; and
- experimental provider-site extension work.

The built-in client remains useful for deterministic engine/provider/renderer testing.

The browser/frontier track can continue when resources and telemetry evidence justify it. A receipt-looking UI inserted beneath an answer does not count as complete accounting if the underlying usage evidence is unavailable.

## Core engine work that remains valid

The Hermes-first launch does not discard the underlying TokenTotals machinery. It relies on it.

Already-built core capabilities include:

- canonical Turn Receipt object;
- provider pricing registries/calculators;
- observed/derived/unavailable semantics;
- exact receipt identity;
- append-only local turn ledger;
- thread aggregation;
- Standard and Expanded renderers;
- CSV audit export;
- local pacing/Turn Notice support;
- Windows packaging; and
- verification-receipt history.

These are engine capabilities. They are not substitutes for proving an actual host integration.

## Evidence language

This roadmap uses three separate words deliberately:

- **Implemented** — code exists.
- **Tested** — a named test was actually executed.
- **Proven** — the exact acceptance behavior has direct evidence.

No roadmap item is promoted by replacing one of those meanings with another.

## Release order

The intended order is now:

```text
Hermes user-zero proof
        ↓
Hermes hardening/recheck
        ↓
Hermes-first TokenTotals release
        ↓
OpenClaw integration/proof
        ↓
Lobster stress test
        ↓
continued browser/frontier experiments when justified
```

That order can change only because new evidence changes the engineering decision—not because an easier proxy makes the project look further along.
