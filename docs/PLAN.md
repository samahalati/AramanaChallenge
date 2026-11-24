# ARAMANA AI Engineer Challenge – Implementation Plan

> **v2 update:** after the first FastAPI prototype (kept in git history) the project was rebuilt on the requested stack – **Django + DRF backend, React frontend** – with a SOLID/DRY refactor (Strategy-registry detectors, data-driven state machine, Observer signal, ORM-adapter). Behaviour was preserved exactly (identical evaluation results). The table below describes the original plan; see [UNDERSTANDING.md](UNDERSTANDING.md) for the current design.

Time budget: ~2 hours of build time (the challenge allows 96h; we optimise for a *functional, integrated, defensible* prototype, as the brief itself asks).

## 1. Goals (from the brief, §2, §11, §12)
Three modules on **one shared data model**:
- **A – HR & Platform Admin** (10%): profiles, credentials, contracts, lifecycle (onboard/suspend/reactivate/terminate), org structure, RBAC.
- **B – Clinical Supervision** (15%): supervisor dashboard, supervisee mgmt, review workflow, escalation, audit.
- **C – Fraud & Anomaly Engine** (25%): rules + statistics + ML + graph + AI-assisted explanation; explainable risk score; investigation workflow; human-in-the-loop.
Plus: architecture (15%), data engineering (10%), security (10%), code quality/tests/docs (10%), presentation (5%).

## 2. Key decisions
| Topic | Decision | Why |
|---|---|---|
| Backend | Python 3.11+ / FastAPI, modular routers + service layer | Brief names it; OpenAPI docs for free; REST contract stays consumable from a Go core |
| DB | SQLAlchemy 2.0, **SQLite by default**, Postgres-compatible (`DATABASE_URL`), Alembic migration | Zero-setup demo; production path is Postgres |
| Data boundaries | Logical schemas by table prefix: `hr_*`, `clin_*`, `sec_*`, `ai_*`; cross-boundary links by opaque ID only; clients are pseudonyms | Separation of clinical vs HR data (§3.4, §7.2) |
| AuthN | JWT (PyJWT), PBKDF2 password hashing, lockout after N failures | No native deps, secure |
| AuthZ | Role → permission matrix **plus** relationship scoping (supervisor sees only current supervisees; subject of an alert cannot see it) | RBAC + ABAC per §3.4 |
| Audit | Append-only, **hash-chained** audit log; every denied access recorded in `sec_access_events` | Tamper evidence, §4.5 |
| Detection | 5 layers: Rules · Robust-stats (MAD, chi-square/JS-divergence) · IsolationForest · Graph (networkx) · AI-assisted explanation | §5.2; LLM never scores |
| Scoring | Noisy-OR of weighted indicators (YAML-configurable); every point traceable in `score_breakdown`; levels Low/Medium/High/Critical | Explainable, §5.3 |
| Free LLM API | OpenAI-compatible client → **Groq / Google Gemini free tier / local Ollama**; default = deterministic template (no key needed) | "Need free API"; brief requires an offline alternative |
| Frontend | Dependency-free SPA (vanilla JS + CSS) served by FastAPI at `/` | `pip install` + run; no Node build |
| Data | Seeded synthetic generator with **ground-truth labels** and hard negatives | Measurable evaluation, §7.3, §9 |

## 3. Detection design (the 25% module)
- **A Therapist**: rule: overlapping intervals (interval sweep), >12 h/day; rule: reported vs check-in duration mismatch / completed-without-checkin; stats: robust z of weekly volume, cancel/modify rate vs peers; ML: IsolationForest on practitioner-week features.
- **B Counselor**: referral concentration — chi-square GOF + HHI + JS-divergence vs *expected distribution from assignment policy/specialization*; legitimate specialization concentration is suppressed/down-weighted (hard negative).
- **C Supervisor**: approvals/day robust z, share without documentation, review-time too short; IsolationForest; conflict-of-interest via graph (approve ↔ refer rings).
- **D Admin/Platform**: denied access events, failed-login bursts, privilege escalation, out-of-scope edits (rule + rate z-score).
- **E Network**: weighted directed graph (counselor→therapist referrals, supervisor→supervisee approvals); reciprocal/dense-cluster detection.
- Alert dedupe + merge across detectors; **recurrence tracked longitudinally but never changes score or status** (no presumption of misconduct).
- Evaluation: precision/recall/F1 per scenario + ablation (rules-only / stats-only / ML-only / ensemble) on seeded synthetic data; false-positive feedback loop (per-rule FP rate from investigator decisions); versioned rule-set + model version stored on each alert.

## 4. Integration flows (≥3 end-to-end, §6 / §8)
1. Overlapping sessions → alert → compliance reviewer investigates → request info → close/escalate → HR note.
2. Referral concentration → alert → distinguishes specialization → compliance review → false-positive marked (feedback).
3. Supervisor mass-approval w/o docs → alert routed to *compliance* (not the subject supervisor) → reviewer sees activity history.
4. Admin out-of-scope access → 403 + access event → security alert → escalate to platform admin/compliance.
5. Quality concern → routed to the practitioner's supervisor → review outcome recorded on operational record.

## 5. Milestones (≈2h)
| Min | Deliverable |
|---|---|
| 0–10 | Plan, repo scaffold, `.gitignore`, engineering rules, how-to playbooks, requirements |
| 10–40 | Models, DB, security (JWT, RBAC, audit chain), HR + supervision services/routers |
| 40–60 | Synthetic data generator (normal + injected anomalies + hard negatives + ground truth) |
| 60–85 | Detection engine (rules, stats, ML, graph, scoring, explain, LLM adapter), alert/investigation API |
| 85–105 | Frontend SPA (HR, supervisor, monitoring, alert detail, audit) |
| 105–120 | Tests, evaluation run, docs (README, architecture, ERD, RBAC matrix, report, slides), final commit/push |

## 6. Deliverable map (§10)
- A: `docs/ARCHITECTURE.md` (system/module/data-flow/detection/security diagrams in Mermaid, ERD, RBAC matrix, API)
- B: running app (`make run`), seed data, 4+ scenarios, investigation workflow
- C: source, `README.md`, `.env.example`, `tests/`, Alembic migration, assumptions & limitations
- D: `docs/TECHNICAL_REPORT.md` (with measured results)
- E: `docs/PRESENTATION.md` (Marp-compatible slides)

## 7. Non-goals / risks
- No real data, no paid APIs, no polished UI. Auth is demo-grade (no MFA/SSO); documented in limitations.
- Risk: scope. Mitigation: shared service layer + generated seed data + data-driven RBAC matrix.
