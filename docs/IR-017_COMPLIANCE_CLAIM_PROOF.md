# IR-017 Compliance Claim Proof

**Finding:** IR-017 — Government / FedRAMP / FISMA statement  
**Verdict:** UNSUPPORTED CLAIM / REPAIRED AND REVALIDATED  
**Proof revision:** 2026-09-15

## What was wrong

The baseline README placed TokenTotals under a **FedRAMP & FISMA Compliance** heading and stated that a local, zero-egress tool that never transmits data off the machine “sails through compliance review.”

That conclusion was not established by the implementation. Loopback binding, local state, source availability, or the absence of a separate QuietFireAI telemetry service can be relevant security properties, but those properties do not by themselves confer FedRAMP authorization, FISMA compliance, an Authority to Operate (ATO), classification-handling approval, or permission to deploy in a regulated environment.

## Why it mattered

Compliance and authorization are system- and organization-specific determinations. Presenting a local architecture as automatically clearing those processes could cause a user to treat an architectural characteristic as a regulatory approval.

The integrity issue was documentation scope, not that the local architecture had no security value.

## Actual repair

The hardened public documentation preserves the useful architectural facts while removing the unsupported regulatory conclusion.

The README now states:

> It is not a FedRAMP/FISMA authorization and does not make an environment compliant by itself.

The technical/security whitepaper states that loopback binding, local state, source availability, and absence of a QuietFireAI telemetry service may be useful properties in controlled environments, but **do not by themselves establish FedRAMP authorization, FISMA compliance, ATO suitability, classification-handling approval, or permission for deployment**. Those determinations are explicitly assigned to the relevant organization and security/compliance authority.

No fake certification, badge, control matrix, or self-issued compliance status was added to preserve the baseline marketing language.

## Regression proof

`tests/test_public_claim_integrity.py::test_fedramp_fisma_compliance_cannot_be_inferred_from_local_architecture` permanently rejects public claim language including:

- `sails through compliance review`;
- the baseline `FedRAMP & FISMA Compliance:` heading;
- claims that TokenTotals is automatically or “by design” FedRAMP/FISMA compliant.

The same test positively requires the current README and whitepaper disclaimers so the repair cannot be satisfied merely by deleting all discussion of the boundary.

## Revalidation target

The regression is executed as part of the complete forensic suite together with the constrained Linux runtime, Windows runtime, and Windows build-tool checks. IR-017 does not require a production-code change because the implementation cannot itself grant the external authorization that the baseline prose overstated.

## Remaining boundary

This proof does not determine whether TokenTotals is suitable for any particular government, defense, intelligence, healthcare, financial, or other regulated deployment. Such suitability depends on the complete system, data classification, hosting/runtime environment, controls, dependencies, operating procedures, authorization boundary, and the responsible organization's assessment.

TokenTotals may accurately describe tested architectural properties. It may not convert those properties into a compliance or authorization claim without independent evidence appropriate to that specific claim.
