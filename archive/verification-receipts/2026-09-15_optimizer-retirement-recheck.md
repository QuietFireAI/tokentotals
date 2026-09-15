# TokenTotals Auto-Economy / Optimizer Retirement Recheck Receipt

Date: 2026-09-15

## Scope

This receipt closes the auto-economy / counterfactual potential-savings runtime item.

The objective was not to replace stale model names with newer model names. The objective was to determine whether TokenTotals could defensibly infer that a cheaper model/provider was an equivalent substitute for the model explicitly requested by the caller.

## Diagnosis

The previous optimizer had several structural problems:

1. It classified a request as routine/lightweight largely from prompt word/token length.
2. It recognized a short hard-coded set of older "premium" model names.
3. It selected an economy target from a model-name substring rule.
4. For non-GPT requests, that rule could select a Google Gemini model even when the caller requested Anthropic Claude.
5. The counterfactual "Potential Savings" amount compared preflight input-side estimates, not a complete hypothetical turn including output, tools, modalities, context behavior, service tier, or other provider-specific charges.
6. Pricing data alone does not prove equivalent capability, credentials, tool support, modality support, context limits, provider policy, data path, latency, reasoning behavior, or output quality.
7. The dashboard/documentation presented the resulting counterfactual as a savings opportunity, including a static "up to ~90%" claim that was not defensible from the observed request telemetry.

Updating the stale model IDs would therefore preserve the architectural defect.

## Decision

The optimizer was retired rather than renamed or expanded.

TokenTotals now preserves the model/provider explicitly selected by the client. It remains a pricing, observability, pacing, and circuit-breaker layer; it does not silently choose which model should answer the request.

A future model-routing feature would require its own explicit design and evidence, including user-controlled mappings, credential compatibility, capability/tool/modality checks, application requirements, and a defensible comparison basis. That is outside this pricing-hardening item.

## Implementation commits

- `8d750631162ab0538088d69d6f62339fb649b037` — removed automatic model substitution, optimizer globals/status fields, potential-savings dashboard card, and static optimization claim from `proxy_server.py`.
- `9a41257d9c42af3d346d8479aacf4194831ba775` — removed `auto_economy_mode`, `potential_savings_usd`, and `flagged_routine_calls` from active config/state defaults and simplified spend updates.
- `dd5c39db27534f7a01bff04807e38fc2a09ee449` — removed the retired potential-savings tray metric.
- `039410c1be36a33146c643ef2e0c442adf8904eb` — reconciled README behavior/configuration language and documented the model-integrity boundary.
- `85663290ef98cb03ee6b2558c520a84123639e25` — replaced the whitepaper's active counterfactual downgrade specification with the model-integrity boundary and retirement rationale.
- `58f118c571c1fe28bb35bafa172023f4450463cb` — cleaned residual dashboard rewrite artifact after the optimizer removal.
- `1a3049d0308759621edfca01948f9170eaa27f7c` — added optimizer-retirement/model-integrity regression tests.

## Backward compatibility

Older `~/.tokentotals/config.json` or state files can still physically contain historical optimizer keys. Current runtime code does not consume or expose those retired values. New default config/state files no longer create them.

This avoids making a historical local file unreadable while ensuring a legacy `auto_economy_mode: true` value has no routing effect.

## Regression invariants

The new tests enforce that:

- optimizer globals and model-substitution variables are absent from the runtime;
- active config/state defaults do not expose optimizer/savings fields;
- `config_manager.update_spend` no longer accepts counterfactual savings/routine arguments;
- `/api/status` does not expose optimizer/savings fields even if legacy state/config dictionaries contain them;
- a legacy config with `auto_economy_mode: true` cannot remap the explicitly requested model;
- dashboard/current docs no longer claim an active automatic downgrade or unsupported potential-savings meter;
- the whitepaper identifies the model-integrity boundary rather than specifying an active downgrade advisory.

## Clean-machine evidence

GitHub Actions run: `35023417088`
Job: `104564531426`
Commit: `1a3049d0308759621edfca01948f9170eaa27f7c`
Result: **SUCCESS**

Clean runner stages:

- dependency install: success
- Python compile: success
- live `proxy_server` import: success
- regression suite: **85/85 passed**

Optimizer-specific tests passing:

- `test_dashboard_and_current_docs_do_not_claim_active_auto_downgrade`
- `test_default_state_and_config_do_not_expose_retired_optimizer`
- `test_legacy_auto_economy_true_cannot_remap_requested_model`
- `test_runtime_optimizer_symbols_are_removed`
- `test_status_endpoint_omits_retired_optimizer_metrics`

The existing OpenAI, Anthropic, Google/Gemini, legacy-pricing-removal, preflight-fallback, proxy-integration, and runtime-model-catalog regressions remained green.

## Result

**COMPLETE for this item.**

TokenTotals no longer mutates the caller's selected model/provider through the retired auto-economy heuristic, and it no longer presents a counterfactual input-only comparison as a runtime potential-savings metric.

## Explicitly not claimed

This receipt does not claim that every cheaper model is unsuitable as an alternative. It records only that TokenTotals' pricing layer does not have enough information to prove safe/equivalent automatic substitution and therefore does not make that decision for the caller.

Historical receipts that describe prior optimizer behavior remain unchanged as historical evidence.
