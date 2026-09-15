# IR-015 Protocol Scope Proof

**Finding:** IR-015 — WebSocket claim  
**Verdict:** UNSUPPORTED CLAIM / REPAIRED AND REVALIDATED  
**Proof revision:** 2026-09-15

## What was wrong

The baseline technical whitepaper described TokenTotals as an **HTTP/WebSocket loopback proxy daemon**. The reviewed application did not implement a TokenTotals WebSocket route or WebSocket proxy lifecycle. Chat completions were exposed through HTTP, with streamed responses returned as Server-Sent Events (SSE).

That made the baseline WebSocket wording an implementation overclaim rather than a description of an existing feature.

## Actual repair

The hardened public documentation now describes the implemented boundary:

- chat-completion requests use HTTP `/v1/chat/completions`;
- streamed chat-completion responses use SSE over that HTTP endpoint;
- TokenTotals does **not** claim a WebSocket proxy endpoint in this revision.

No placeholder or cosmetic WebSocket feature was added simply to preserve the old wording.

## Adversarial / regression proof

Three independent guards cover the claim and runtime boundary.

1. **Public-claim regression.** `tests/test_public_claim_integrity.py` rejects the baseline HTTP/WebSocket proxy language and requires the explicit current no-WebSocket statement to remain on the public claim surfaces.
2. **Route-table proof.** `tests/test_ir015_protocol_scope.py::test_tokentotals_exposes_no_websocket_route` inspects the production FastAPI application's route table and requires zero Starlette `WebSocketRoute` entries.
3. **Behavioral streaming proof.** `tests/test_ir015_protocol_scope.py::test_streaming_chat_path_is_real_http_sse` sends a real `stream=true` POST through the production FastAPI application, with provider egress mocked. It requires HTTP 200, a response `Content-Type` beginning with `text/event-stream`, SSE `data:` framing, and the final `[DONE]` marker.

The behavioral proof is deliberately stronger than grepping source code: it exercises the actual request/response path exposed by the application.

## Validation result

An intermediate GitHub Actions run surfaced one stale test-contract failure: the scheduler regression still expected the prior workflow step label after the daily receipt workflow had been deliberately strengthened. That run produced **1 failed / 68 passed**; the runtime, Linux smoke, Windows runtime smoke, and Windows build-tool jobs were otherwise healthy. The stale assertion was reconciled to the new PASS/FAIL receipt contract rather than weakening the workflow.

GitHub Actions run `34996610230` on commit `475d63adae8d540ae5453d60985f9ff6a6092cba` then passed:

- **70/70** regression/integration tests on Ubuntu / CPython 3.12.14;
- constrained Linux runtime smoke;
- constrained Windows runtime smoke;
- constrained Windows PyInstaller/build-tool smoke;
- `pip check` in the validated environments.

No production protocol code change was required during IR-015 because the hardened implementation already matched the corrected HTTP+SSE documentation boundary. The revalidation pass supplied the missing permanent proof.

## Remaining boundary

This proof says TokenTotals itself exposes no WebSocket proxy route in the reviewed revision. It does not make claims about transport mechanisms that LiteLLM or an upstream provider may use internally outside TokenTotals' own application boundary.

A future TokenTotals WebSocket feature may be added, but stronger WebSocket language is not permitted until a real route/lifecycle is implemented and covered by connection, streaming, failure, accounting, and budget-control tests.
