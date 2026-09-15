# TokenTotals Token Estimation Contract

**Status:** normative implementation/disclosure contract  
**Applies to:** pre-flight token estimation, budget reservation, reconciliation, README/whitepaper claims, receipts, dashboards, and future tokenizer integrations

## 1. Governing distinction

TokenTotals must distinguish **pre-flight estimated tokens** from **provider-reported usage tokens**.

The current pre-flight estimator in `pricing_engine.estimate_text_tokens()` is a local pacing heuristic:

```text
estimated_tokens = max(1, ceil(len(text encoded as UTF-8 bytes) / 3))
```

The optional model argument does not make this a model tokenizer. The current estimator intentionally produces the same result for the same UTF-8 text regardless of whether the requested model is OpenAI, Anthropic, or Google.

## 2. Claims that are not permitted

Unless a future implementation actually executes and validates the applicable provider/model tokenizer, TokenTotals must not describe the current pre-flight value as:

- a BPE token count;
- an exact token count;
- a deterministic provider token count;
- provider-accurate tokenization;
- cryptographic tokenization;
- a model-specific tokenizer result.

The current value may be described as a **local token estimate**, **UTF-8-length heuristic**, or **conservative pre-flight estimate**.

## 3. Pre-flight purpose

The heuristic exists to support conservative budget pacing before provider telemetry exists. It is combined with the verified model's conservative guard rates and a bounded output-token ceiling to produce the pre-flight reservation.

The pre-flight reservation is not a provider invoice prediction. It is a high-side pacing control intended to reserve defensible budget before upstream egress.

## 4. Post-response reconciliation

When a non-stream provider response exposes usable input/prompt and output/completion usage counts, those provider-reported counts supersede the local pre-flight heuristic for the supported reconciliation calculation.

This does **not** turn TokenTotals into the provider billing system. The resulting dollar value remains an independent estimate subject to the pricing dimensions implemented for that transaction, as defined by `docs/ACCURACY_AND_ESTIMATION_STANDARD.md`.

If usable final usage telemetry is unavailable, TokenTotals must not manufacture a precise final token count. For the currently supported streaming path, the conservative reservation remains on the books and the stream is marked unreconciled.

## 5. Proven current behavior

Regression coverage must preserve all three properties:

1. the current local estimator is exactly the documented UTF-8-byte heuristic and is not model-specific;
2. public claim surfaces cannot describe that heuristic as BPE/exact/provider-accurate tokenization; and
3. when usable provider token counts are returned, reconciliation uses those returned counts rather than retaining the pre-flight heuristic amount as the final estimate.

## 6. Requirements for a future tokenizer implementation

A future change may replace or augment the heuristic with real tokenizer support, but the public claim must not change merely because a tokenizer library is installed as a dependency.

Before TokenTotals may claim model/provider tokenization, the implementation must define and test:

- the exact provider/model or model-family mapping to tokenizer/encoding;
- tokenizer/encoding version provenance;
- handling for aliases, snapshots, preview models, and provider-side model substitutions;
- serialization rules for system/developer/user/tool messages and other request structure;
- treatment of attachments, images, audio, tools, or other non-text input where applicable;
- behavior when no verified tokenizer mapping exists;
- regression fixtures against trusted provider/tokenizer reference values; and
- disclosure of any remaining difference between local tokenization and provider billing telemetry.

Unknown tokenizer mapping must fall back to an explicitly labeled estimate or fail closed according to the applicable pacing policy; it must never silently inherit an unrelated model tokenizer and be presented as exact.

## 7. Integrity rule

```text
before response: estimate honestly -> reserve conservatively

after usable provider usage: reconcile from observed usage

without usable provider usage: remain conservative / unreconciled
```

The precision of the language must never exceed the precision of the implementation.
