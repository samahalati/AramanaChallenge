# Understanding ARAMANA – a guided tour

**English** · [فارسی](fa/UNDERSTANDING.md)

Read this first. It explains *what* the system is for, *how a request flows*, *why the code is shaped this way* (design patterns, SOLID, DRY), and *how to change it safely*. Every claim points to a real file.

---

## 1. The idea in one page

ARAMANA is a mental-health platform. As it grows, three problems appear at once:

| Problem | Module | Plain-English job |
|---|---|---|
| "Who works here, are they licensed, who supervises whom?" | **A – HR & administration** (`backend/hr`, `backend/accounts`) | Profiles, credentials, contracts, onboarding/suspension/termination, org structure. |
| "Is care quality being supervised properly?" | **B – Clinical supervision** (`backend/supervision`, `backend/clinical`) | Supervisors review practitioners' work, give feedback, assign corrective actions, escalate concerns. |
| "Is anybody abusing the system?" | **C – Fraud & anomaly detection** (`backend/detection`, `backend/monitoring`) | Finds suspicious patterns, scores them *explainably*, and hands them to a **human** investigator. |

The three share **one database and one set of rules about who may see what**. That shared foundation (`backend/core`) is the heart of the design: the fraud engine reads data the other two modules produce, and its alerts flow back into them.

**The three promises the design makes (and tests enforce):**
1. **A human decides.** No code path turns an alert into a suspension, penalty or accusation (`detection` is pure functions; HR actions are separate endpoints; a test asserts users are unchanged after detection).
2. **Everything is explainable.** Every score is the exact sum of per-indicator points you can read in the UI.
3. **Least privilege & privacy.** Administrators can't read clinical data; clients are pseudonyms; nobody sees an alert about themselves.

---

## 2. Who can do what (the mental model)

Six roles → permissions (`backend/core/rbac.py`, rendered in [RBAC_MATRIX.md](RBAC_MATRIX.md)). Two layers of checks:

1. **Role layer** – *what kind* of thing may you do? (`hr:write`, `alerts:investigate`, …) → `core/permissions.py`.
2. **Relationship layer** – *which records*? Own records / your **current** supervisees / users named in an alert → `hr/selectors.py`, `monitoring/visibility.py`.

Example: a supervisor holds `clinical:read:supervisees`, but reading therapist #9's sessions also requires #9 to be one of *their current* supervisees (effective-dated assignment). A compliance reviewer holds `clinical:read:alerted`, so they can only read clinical records of people named in an alert.

---

## 3. Follow one request end to end

*Scenario 4 live:* the platform admin `admin@aramana.test` asks for a practitioner's sessions.

```
React ─ GET /api/clinical/practitioners/15/sessions ──────────────────────────────┐
                                                                                   ▼
core.auth.JWTAuthentication      loads the user fresh from the DB (suspended ⇒ 401 instantly)
core.permissions.RolePermission  view.perms["get"] = (clinical:read:own|supervisees|alerted)
                                 platform_admin holds none ⇒ deny():
                                    • AccessEvent(access_denied, permission, path, ip)    ← raw signal
                                    • AuditLog row (hash-chained)
                                 ⇒ HTTP 403
...later, compliance presses "Run detection"...
monitoring.services.runs.run_detection
   → monitoring.loaders.load_data        (Adapter: ORM rows → DataFrames)
   → detection.engine.analyse            (pure; no Django)
        AdminScopeAbuse (rule)  sees ≥3 denials in 60 min across ≥2 areas ⇒ Finding
        score = noisy-OR of indicators ⇒ 47 (Medium)   [9 denials + account abuse ⇒ 96 Critical]
   → runs.upsert                         de-dup / recurrence logic ⇒ Alert + AlertUser + timeline event
React alert page ─ GET /api/alerts/{id}  (visibility: domain=security ⇒ platform_admin/compliance only,
                                          and NOT the subject ⇒ the admin gets 404 for their own alert)
Compliance: start review → request info → close (note ≥30 chars, evidence must have been viewed)
```

Notice the layering: **views** (HTTP, validation) → **services** (business rules, transactions, audit) → **models**. Views never contain business logic (`hr/views.py` is ~115 lines for 14 endpoints).

---

## 4. The detection engine in plain language

Five layers, each with a reason ([ARCHITECTURE §5](ARCHITECTURE.md)):

| Layer | Question it answers | Example | Code |
|---|---|---|---|
| Rules | "Is this *impossible or against policy*?" | two in-person sessions at once; blocked access bursts | `detectors/session.py`, `security.py`, `approvals.py` |
| Robust statistics | "Is this far from what's expected?" | referrals concentrated vs what specialisation policy predicts | `detectors/referral.py`, `peer.py` |
| Isolation Forest | "Is this *unusual in combination* in a way no rule foresaw?" | odd mix of load/cancellations/mismatches | `detectors/peer.py` (`IsolationForestDetector`) |
| Graph | "Do these three people form a suspicious cluster?" | counselor→therapist→supervisor ring | `detectors/graph.py` |
| LLM assistant (optional) | "Explain this alert, and answer my questions about it – without deciding anything" | cited, guardrailed briefing + Q&A | `detection/assistant/`, [LLM_ASSISTANT.md](LLM_ASSISTANT.md) |

**Scoring** (`detection/scoring.py`): each indicator has a *weight* (how much it may contribute, in `detection/config.yaml`) and a *strength* (0–1, how extreme the measurement is). Combine like independent chances: `score = 100·(1 − Π(1 − wᵢ·sᵢ))`.

Worked example — admin2's alert: denied-burst `0.75×1.0`, privilege-grants `0.55×1.0`, scope-probing `0.45×1.0`, account-burst `0.55×0.6`.
`1 − (0.25 × 0.45 × 0.55 × 0.67) = 1 − 0.0415 = 0.958` → **96 (Critical)**. Points shown: 75.0 + 13.8 + 5.1 + 2.0 = 95.9 ✔.

**Two safety valves**: (1) alerts supported *only* by weak evidence (ML score, volume) are capped at Low; (2) the referral test is *policy-aware* — a specialist unit that legitimately concentrates referrals is **suppressed** and listed with both p-values instead of alerted.

---

## 5. Design patterns used (and where)

| Pattern | Where | Why it earns its place |
|---|---|---|
| **Strategy + Registry** | `detection/base.py` (`Detector`, `@register`, `REGISTRY`), `detection/detectors/*` | Each detector is one small class with one method. The engine loops over the registry, so **adding a detector never edits the engine, scoring or persistence** (Open/Closed). 12 detectors today. |
| **State machine (State pattern, data-driven)** | `core/statemachine.py`; used by `hr/services.py` (user lifecycle), `monitoring/services/alerts.py` (investigation), `supervision/services.py` (review), `clinical/services.py` (session) | One 16-line class replaces four hand-rolled `if status == …` ladders. Illegal transitions raise `409` in one place. |
| **Observer** (Django signals) | `supervision/signals.py` ⇒ `monitoring/apps.py` ⇒ `monitoring/services/escalation.py` | Supervision *announces* an escalation; monitoring *subscribes* and creates the alert. Dependency points one way (monitoring → supervision) — no import cycle, neither side knows the other's internals. |
| **Adapter / Dependency Inversion** | `monitoring/loaders.py` | The detection package depends on DataFrames (an abstraction), not on the Django ORM. It can be unit-tested, reused in a worker, or moved to another stack. |
| **Service layer + Selectors (Repository-like)** | `*/services.py`, `hr/selectors.py`, `accounts/selectors.py` | Business rules in services; reusable read queries in selectors. `hr/selectors.py` is the *only* place that knows what "current assignment" means. |
| **Declarative policy** | `core/permissions.py` + `perms = {...}` on every view | One permission class for the whole API; views *declare* what they need. Missing declaration ⇒ denied (secure by default). |
| **Factory method** | `Cfg.ind()` in `detection/data.py`, `Detector.finding()` in `detection/base.py` | Every indicator takes its weight from the versioned config; detectors can't hard-code weights or forget fields. |
| **Template-method flavour** | `Detector` base + `detect()` | Base class owns construction, config access and finding assembly; subclasses implement only the detection logic. |
| **Adapter (providers)** | `detection/llm.py` | One OpenAI-compatible call for Gemini/Groq/Ollama; the transport knows nothing about prompts or safety. |
| **Pipeline / chain of gates** | `detection/assistant/investigator.py` + `guardrails.py` | pack → model (rules live in the prompt) → deterministic checks → LLM judge → one repair → deterministic fallback. Each step is a small function that can be tested (and red-teamed) alone; the fallback guarantees a safe answer exists, and no judge verdict means no model text is shown. |
| **Unit of Work** (small) | `seed/generate.py::UnitOfWork` | Collects objects, `bulk_create`s in dependency order → 5k-row seed in ~3 s. |
| **Memoised shared computation** | `Context.memo()` in `detection/base.py` | Expensive weekly tables / referral analysis computed once, shared by detectors. |

*Honesty note:* patterns are used where they remove real duplication or coupling — not decoratively. E.g. there is no "Factory of factories", and CRUD that is just CRUD stays plain DRF.

---

## 6. SOLID — with receipts

| Principle | Evidence |
|---|---|
| **S**ingle Responsibility | `core/audit.py` only audits. `monitoring/loaders.py` only converts rows→frames. `detection/scoring.py` only scores. `detection/explain.py` only words explanations. Views only translate HTTP ↔ services. |
| **O**pen/Closed | New detector = new class + `@register` + weights in YAML. New role/permission = edit one table in `core/rbac.py`. New workflow = a dict of transitions. No existing code changes. |
| **L**iskov | Every `Detector` subclass honours the contract `detect() -> list[Finding]`; the engine treats them uniformly (`primary` vs `behavioral` only changes *how results merge*, not how they are called). All `SupervisionView` subclasses are drop-in. |
| **I**nterface Segregation | Detectors receive a small `Context` (data, config, memo) — not the whole app. Views declare only the permissions they need. The `detection` package imports nothing from Django. |
| **D**ependency Inversion | High-level `detection.engine` depends on abstractions (`Detector`, `Data` frames, `Cfg`); the Django-specific details are injected at the edge (`loaders.py`, `runs.py`). `llm.summarise` takes settings and an optional `transport`, so tests inject a mock HTTP transport. |

---

## 7. DRY — duplication that was deliberately removed

| Before (FastAPI draft) | After | File |
|---|---|---|
| 6 hand-written copies of sliding-window code (denied bursts, account bursts, edit bursts, failed logins, per-IP spray, approval peaks) | one `bursts()` helper | `detection/data.py` |
| 4 status-transition ladders | one `StateMachine` | `core/statemachine.py` |
| Indicator constructed with 8 positional args and a looked-up weight each time | `cfg.ind(name, label, value, threshold, strength)` | `detection/data.py` |
| Serializer boilerplate in every view | `validated(Serializer, request)` | `hr/views.py` |
| 4 near-identical `POST /reviews/<id>/<step>` views | one `ReviewAction` class + handler table | `supervision/views.py` |
| Credential and contract "add" endpoints | one `_create_child` | `hr/views.py` |
| Credential/contract PATCH + audit | `AuditedUpdateView` base | `hr/views.py` |
| Per-view permission checks + denial logging | `RolePermission` + `perms` dict | `core/permissions.py` |
| Hand-written JSON dicts for lists | DRF `ModelSerializer`s | `*/serializers.py` |
| Same table / modal / loading code in every page | `DataTable`, `FormModal`, `Query`, `useAct` | `frontend/src/components` |

Rule of thumb applied: *three similar lines are fine; the third copy of a concept becomes a helper*.

---

## 8. Frontend architecture (React)

```
src/
  api/client.js        fetch wrapper (bearer token, uniform errors, auto sign-out on 401)
  api/hooks.js         useGet(path)  – cached GET (TanStack Query)
                       useAct()      – run a mutation, toast the result, refresh all queries
  auth/AuthContext     user + can(permission); nav comes from the server (/auth/me)
  components/          DataTable · FormModal (config-driven forms) · Query (loading/error once) · ui (Card, Badge, Bars…)
  features/<module>/   one folder per module, each a small router + page components
```

* **Server decides, UI reflects.** Navigation and buttons come from permissions in `/auth/me`; the API re-checks everything. Hiding a button is UX, not security.
* **Config-driven forms:** a modal is just `{title, fields:[{name,label,type}], onSubmit}`; there is exactly one dialog implementation.
* **No `dangerouslySetInnerHTML`**: React escapes API data → no XSS surface.
* Mutations go through `useAct` → after any success all queries are invalidated, so pages never show stale state and no page hand-writes cache logic.

---

## 9. How to change things safely

**Add a detector (≈ 5 steps)** — full checklist in [HOWTO.md](HOWTO.md)
1. New class in `backend/detection/detectors/…` subclassing `Detector` (set `category/domain/scenario`, implement `detect()` using `self.cfg.ind(...)` and `self.finding(...)`), decorate with `@register`.
2. Add its indicator weights/thresholds to `detection/config.yaml`; bump `ruleset_version`.
3. If it creates a new scenario name, add explanation text in `detection/explain.py`.
4. Add an injected anomaly **and a hard negative** to `seed/generate.py` (+ ground-truth entry).
5. Add a test in `backend/tests/test_detection.py`; run `python manage.py evaluate`.

**Add a permission/role** — edit `core/rbac.py`; run `python manage.py export_docs`; add a case to `tests/test_security.py`.
**Add a workflow** — define a `StateMachine({...})`; call `.apply(action, current)` in the service.
**Add an endpoint** — serializer → service function → thin view with `perms = {...}` → URL. Done; auth, denial logging and audit conventions come for free.

---

## 10. Reading order (30 minutes)

1. `backend/core/rbac.py`, `permissions.py`, `audit.py` — the shared foundation (10 min).
2. `backend/hr/services.py` — a clean service with a state machine.
3. `backend/detection/base.py` → `detectors/session.py` → `engine.py` → `scoring.py` — the engine.
4. `backend/monitoring/services/alerts.py` — investigation workflow, visibility, safeguards.
5. `backend/tests/test_e2e.py` — the five end-to-end stories, executable.
6. `frontend/src/features/monitoring/AlertDetail.jsx` — how the UI presents an explainable alert.

---

## 11. Questions you should be ready to answer

| Question | Short answer |
|---|---|
| Why not just an LLM for fraud detection? | Unverifiable, non-deterministic, privacy-risky, and indefensible for HR consequences. LLM only paraphrases pseudonymised evidence; scores come from rules/stats/ML/graph. |
| How do you avoid flagging legitimate specialisation? | Expected referral distribution is built from specialisation + capacity (+5 % slack); a naive test runs alongside; "naive-only" hits are *suppressed* and shown with both p-values. |
| How is it explainable? | Noisy-OR decomposes exactly into points per indicator; each shows measured value, reference, weight, strength. Ruleset+model version stored on every alert. |
| What stops misuse of alerts? | No automatic action path; documented notes required; "substantiated" requires having viewed evidence; reviewer ≠ subject; every view/action audited; misconduct never routed to supervisors. |
| Why a modular monolith? | One coherent data model for three modules; cheapest to make correct; seams (service layer, ID-only cross-boundary refs, pure detection package, signals) allow extraction. |
| How does it integrate with a Go core? | OpenAPI contract + events; swap JWT for OIDC; detection package is HTTP-free so it can run as a worker; clinical tables can move to a separate DB (ID-only references). |
| What are the weak points? | Synthetic self-authored anomalies ⇒ optimistic metrics; hand-set weights; demo auth; Python-side alert filtering; batch (not streaming) detection. See [TECHNICAL_REPORT §5](TECHNICAL_REPORT.md). |
| Why is the clinical/HR separation real, not cosmetic? | Different apps/tables, ID-only references, no clinical permission for admin roles, tests assert it, and denials are persisted and fed back into detection. |
