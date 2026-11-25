---
marp: true
theme: default
paginate: true
title: ARAMANA – Governance, Supervision & Fraud Detection
---

# ARAMANA governance platform
### HR administration · clinical supervision · explainable fraud & anomaly detection

AI Engineer technical challenge – working prototype
*(Marp-compatible: `npx @marp-team/marp-cli docs/PRESENTATION.md --pdf` · or read as plain Markdown)*

---

## The problem, and the stance we took

- A growing mental-health platform must manage a **workforce**, **supervise** care quality, and **detect abuse** – without becoming a surveillance tool.
- Design principles
  1. **One shared data model**, three modules – not three apps
  2. **Explainable** over clever: every score traces to indicators
  3. **Human decides**: no code path from an alert to a sanction
  4. **Privacy by construction**: pseudonymous clients, clinical ≠ HR data

---

## Architecture (modular monolith, Go-compatible)

*Patterns: Strategy+Registry (detectors) · State machine · Observer (signals) · Adapter/DIP (ORM→DataFrames) · declarative permissions*

```
React SPA ──REST/JWT──▶ Django + DRF: views → services → ORM ──▶ SQLite/Postgres
                                  │ declarative RBAC + relationship scoping · hash-chained audit
                                  └──▶ detection package (Strategy detectors; no Django) ──▶ alerts
```
- Boundaries = Django apps: `accounts/hr` · `clinical/supervision` · `core` · `monitoring` (cross-links by ID only)
- Core flows are **implemented, not described**: alert → route to supervisor → review outcome → HR history
- Integration with the Go core: OpenAPI contract + events; identity via OIDC; engine already HTTP-free

---

## Module A & B – what works (live demo)

- **HR**: profiles, credentials expiry dashboard, contracts, lifecycle state machine (pending→active⇄suspended→terminated), effective-dated supervisor assignments with history
- **Supervision**: dashboard (pending/overdue/quality/escalation/trends), review → feedback → corrective action → close, quality issues → escalation to compliance
- **RBAC**: 6 roles; HR & platform admins hold **zero** clinical permission; supervisors see only *current* supervisees; client refs redacted for non-clinical roles

---

## Module C – five layers, each with a reason

| Layer | Used for | Why |
|---|---|---|
| Rules | overlaps, impossible locations, denied-access bursts, undocumented approvals | logical impossibilities need no statistics |
| Robust statistics | referral steering vs **policy-expected** distribution; peer outliers (MAD) | small counts → Monte-Carlo test; policy separates specialisation from steering |
| Isolation Forest | unknown unknowns | no labels exist; always explained; can't alert alone |
| Graph | counselor–therapist–supervisor rings | collusion is relational |
| LLM assistant (free/optional) | cited briefing + grounded Q&A on pseudonymised evidence | never scores or decides; 4 deterministic checks + LLM judge (fail-closed) + prompt-level refusals + deterministic fallback; red-teamed (1320 checks (English + Persian)) |

---

## Explainable risk score

`score = 100 · (1 − Π(1 − weightᵢ × strengthᵢ))` → points per indicator **sum exactly to the score**

- Weights/thresholds in versioned YAML; `ruleset_version` + `model_version` on every alert
- **Corroboration cap**: only-ML/volume evidence ⇒ Low (legit busy supervisor = 28.7)
- Each alert: evidence, benign explanations to rule out, recommended action, status, timeline
- Distinguishes **operational · clinical · potential misconduct · security** and routes accordingly

---

## The four required scenarios (all pre-seeded & live-runnable)

1. **Overlapping sessions** → 15 pairs, 4 physically impossible → *Critical*
2. **Referral network** → 51–82 % concentration vs policy → *High/Critical*; specialisation unit **suppressed** (policy-aware p = 0.57 vs naive 0.0002)
3. **Supervisor approvals** → 58/87 under 3 min, undocumented → *Critical*; legit volume → *Low*
4. **Unauthorized admin** → 9 blocked requests + account abuse → *Critical*, audit trail intact, subject cannot see own alert
+ Graph-only ring · HR edit burst · brute force / credential stuffing

---

## Human-in-the-loop & investigation

`new → under_review → info_requested → escalated → false_positive | closed_no_action | closed_substantiated`

- Documented note required; *substantiated* requires the reviewer to have **viewed the evidence**
- Conflict-of-interest guard: nobody sees/assigns/routes alerts about themselves
- Repeated anomalies → **longitudinal context only** (no score change, no presumption)
- False-positive feedback tracked per scenario → tuning; closed alerts aren't re-raised without new records
- Test proves the engine never modifies users

---

## Results (reproducible)

| | Precision | Recall | F1 |
|---|---|---|---|
| Seed 42, Medium+ | 1.00 | 1.00 | 1.00 |
| 8 random worlds (mean) | 0.98 | 1.00 | 0.99 |
| Rules only / Stats only / Graph only | 1.0 | 0.63 / 0.19 / 0.19 | – |
| **Full ensemble** | | **1.00** | |

0 / 7 hard negatives alerted at Medium+. **Caveat:** self-authored synthetic anomalies ⇒ optimistic; seed 2 showed a chance graph cluster (documented, not tuned away).
Engineering: 93 tests (detection, RBAC, workflows, 5 end-to-end flows, LLM guardrail red-team) + browser smoke test · full detection run ≈ 1 s

---

## Security & privacy

- PBKDF2 + lockout + uniform auth errors · JWT; tokens of suspended users die immediately
- Least privilege + relationship scoping; denials **persisted** and fed into detection
- Hash-chained audit with verification endpoint (tamper test) · logs *what was accessed*
- Pseudonymous clients, minimised LLM prompts, security headers/CSP, no `innerHTML`, no secrets in code

---

## Limitations & roadmap

**Limits:** synthetic data · demo-grade auth (no MFA/SSO) · SQLite default, Python-side alert filtering · batch detection · hand-set weights · chain tamper-evident not tamper-proof

**Roadmap:** (0) DPIA/governance → (1) OIDC+MFA, RLS, WAF, external audit anchor → (2) Go-core events & identity, worker split → (3) shadow mode, calibration on outcomes, drift/fairness monitoring → (4) reviewer tooling & SLAs

Estimated production infra ≈ **$250–600 / month** (+ reviewer time)

---

## Thank you – questions

Repo: README quick start (2 min) · `docs/ARCHITECTURE.md` · `docs/TECHNICAL_REPORT.md`
Demo logins: `compliance@ / hr@ / supervisor1@ / admin@ / admin2@ / therapist1@ / counselor1@aramana.test` – `Demo!2345`
