# TokenTotals Technical & Security Whitepaper
### Localhost Layer-7 FinOps Proxy, Pre-Flight Circuit Breakers, and Defensive Prior Art Specification
**Author:** QuietFireAI (Jeff Phillips)  
**License:** GNU General Public License v3.0 (GPLv3)  
**Date:** September 2026  
**Document Version:** 2.4-DEFENSIVE-SPEC

---

## 1. Abstract & Prior Art Disclosure

This document serves as both the architectural security specification for **TokenTotals** and an official **Defensive Publication** establishing prior art in the public domain under 35 U.S.C. § 102. 

TokenTotals introduces a local, zero-egress Layer-7 HTTP/WebSocket loopback proxy daemon operating on `127.0.0.1`. It intercepts Large Language Model (LLM) API transactions, parses abstract syntax representations of prompt payloads, calculates pre-flight cryptographic/BPE token counts, compares estimated financial transaction impact against a persistent local state store, and enforces a local budget advisory gate and notification modal with active modal human acknowledgment.

By publishing this specification under the GPLv3 open-source license, QuietFireAI dedicates these mechanisms to the public domain, barring any entity from asserting patent claims over:
1. Local pre-flight Layer-7 LLM cost simulation prior to TCP/TLS socket upstream handshakes.
2. Local loopback proxy enforcement paired with OS-level blocking modal confirmation ("I UNDERSTAND" pattern).
3. Client-side heuristic counterfactual model downgrade advisory computing potential savings without external telemetry.

---


### 1.1 Non-Invasive Observability & Liability Disclaimer
It is critical to distinguish TokenTotals from upstream accounting systems. TokenTotals is an independent real-time developer cost calculator, telemetry estimation engine, and local notification daemon. TokenTotals does not communicate with provider billing endpoints, query user credit balances, or guarantee absolute network-level traffic blocking. All figures represent estimated calculations derived from local token frequencies multiplied by published vendor rate schedules. TokenTotals provides advisory notifications to inform developer decision-making without guaranteeing vendor billing synchronization. TokenTotals does not communicate with provider billing endpoints, nor does it query user credit balances. TokenTotals operates purely as a stateless, passive-to-active Layer-7 telemetry and pacing governor on localhost. All financial figures represent contextual estimates derived from BPE token frequency multiplied by published vendor rate schedules. It governs transaction execution velocity without modifying or querying provider account states.

## 2. Threat Model & Zero-Egress Architecture

### 2.1 The Autonomous Agent Egress Risk
Modern generative AI agentic systems (e.g., Cursor, Windsurf, AutoGen, CrewAI) execute recursive decision loops. Under failure modes (e.g., parsing errors, hallucinated retry policies), agents generate continuous request bursts that deplete user credit balances without real-time observability.

### 2.2 The Zero-Egress Guarantee
Existing FinOps proxies (Portkey, Helicone, Langfuse) operate as SaaS gateways, requiring developers to transmit plaintext API keys, proprietary source code, and user prompts across third-party networks. 

TokenTotals rejects this topology.
* **Network Boundary:** The daemon binds strictly to IPv4 loopback `127.0.0.1`. It refuses non-loopback binds (`0.0.0.0`).
* **Cryptographic Egress:** Upstream TLS connections originate directly from the host system's network stack to provider endpoints (`api.openai.com`, `api.anthropic.com`).
* **Key Isolation:** API keys pass through volatile process memory only long enough to construct HTTP `Authorization` headers. No keys are ever written to disk, logged, or forwarded to secondary endpoints.

---

## 3. Mathematical Pre-Flight Circuit Breaker Formulation

Traditional rate limiters throttle post-hoc (after an HTTP transaction concludes). TokenTotals implements a deterministic pre-flight gate.

### 3.1 Pre-Flight Cost Estimation
Given an incoming request payload $R$ containing an array of message objects $M = \{m_1, m_2, \dots, m_k\}$ targeted at model $m$:

$$\text{Tokens}_{\text{in}} = \text{BPE}(M, \text{Encoding}(m))$$

The estimated pre-flight cost $C_{\text{est}}$ is computed against the local real-time pricing matrix $P$:

$$C_{\text{est}} = \frac{\text{Tokens}_{\text{in}}}{1,000,000} \times P_{\text{in}}(m)$$

### 3.2 The Invariant Budget Enforcement Rule
Let $S_{\text{today}}$ be the accumulated daily spend stored in `~/.tokentotals/state.json`, and let $L_{\text{daily}}$ be the user-defined budget ceiling:

$$\text{If } (S_{\text{today}} + C_{\text{est}}) > L_{\text{daily}} \implies \text{HALT}(R)$$

Upon evaluating true:
1. The incoming socket is immediately severed with an HTTP `403 Forbidden` response.
2. No upstream TCP handshake is established.
3. `state.json` updates `is_locked = true`.
4. The OS-level Reactive Modal Alert is spawned.

---

## 4. The OS-Level Dead Man's Switch (Lockout Modal)

When `is_locked = true`, the daemon transitions from passive proxying to active lockdown.

1. **Window Placement:** A dedicated Win32/Tkinter window is initialized with `-topmost` priority, positioning it above all IDEs, terminals, and browsers.
2. **Auditory Cue:** Triggers the host operating system's exclamation audio interrupt (`winsound.MessageBeep(winsound.MB_ICONHAND)`).
3. **Cryptic Barrier Elimination:** To prevent accidental dismissal or bypass by script automation, the modal requires physical string matching against the passphrase `"I UNDERSTAND"`.
4. **Graceful Recovery:** Users may select `[ +$5 Quick Boost ]`, which atomically increments $L_{\text{daily}}$ by \$5.00, resets `is_locked = false`, and restores loopback traffic without terminating active IDE sessions.

---

## 5. Counterfactual Model Optimization & Advisory

TokenTotals incorporates local heuristic classification to calculate counterfactual "Potential Savings":

$$\text{Potential Savings} = \sum_{i=1}^{n} \left( C_{\text{actual}}(R_i, m_{\text{flagship}}) - C_{\text{counterfactual}}(R_i, m_{\text{economy}}) \right)$$

Where $R_i$ satisfies the routine complexity threshold ($\text{Tokens}_{\text{in}} < 300$, word count $< 80$, and task classification $\in \{\text{format}, \text{lint}, \text{short\_query}\}$).

This information is presented purely as **non-destructive advisory insights** on the local dashboard, preserving user autonomy while quantifying optimization opportunities.

---


### 5.1 Real-Time Telemetry & Context Invariance Specification
The system produces deterministic, KaTeX-safe telemetry payloads capturing both micro (turn-level) and macro (session-level) FinOps dynamics:
* **Pre-Flight Status:** In Budget (Green), Caution (Yellow), Limit Reached (Red).
* **Cognitive Decomposition:** Separation of latent chain-of-thought (thinking tokens) from materialized output tokens.
* **Cache Amortization:** Real-time ratio of cached prompt tokens against upstream baseline rates.
* **Context Velocity:** Token accumulation velocity per interaction turn ($V_{	ext{tok}} = \Delta T / \Delta n$).

QuietFireAI encourages open-source contributors to fork, extend, and adapt these specifications under the GNU GPLv3 license.

## 6. Conclusion

TokenTotals demonstrates that developer trust, privacy, and budget safety in generative AI are best achieved at the local system boundary. By providing complete transparency, open-source auditing under GPLv3, and zero telemetry egress, TokenTotals provides an immutable airbag for modern AI engineering.
