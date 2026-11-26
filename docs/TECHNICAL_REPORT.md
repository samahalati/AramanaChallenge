# Technical Report

**English** · [فارسی](fa/TECHNICAL_REPORT.md)

*Scope: prototype delivered against the ARAMANA AI-Engineer challenge. Numbers below are produced by `python manage.py evaluate` (seed 42) and `backend/scripts/multi_seed_eval.py`; they are reproducible (raw multi-seed output: `docs/eval_multi_seed.txt`). The Django/React rewrite reproduced the earlier FastAPI results exactly (same 12 alerts, same ablation, same 8-seed means).*

## 1. Architectural decisions

| Decision | Rationale | Trade-off / alternative |
|---|---|---|
| **Modular monolith** (Django + DRF, views → services → models, one DB) | Three modules must share one coherent model; fastest path to an integrated, testable prototype; package seams (one Django app per boundary, `detection/` free of Django, Observer signal between supervision and monitoring) allow later extraction | Single deployable; horizontal scaling by replicas, detection as separate worker later |
| **Data boundaries = Django apps** (`accounts/hr`, `clinical/supervision`, `core`, `monitoring`), cross-boundary links by integer ID only, client pseudonyms | Demonstrates separation of clinical vs administrative data; can be physically split (separate DB/role) without schema surgery | Not physically separated in the demo (one SQLite file) |
| **RBAC + relationship scoping** (`core/rbac.py`, declarative `perms` per view, `monitoring/visibility.py`) | Brief demands role, organisational relationship, responsibility and data-sensitivity based access; one file is auditable and generates the matrix doc | Visibility filtered in Python for alerts (needs SQL/RLS at scale) |
| **Hash-chained audit log** | Tamper-evidence without external infra; verification endpoint and test | Not a substitute for WORM storage / external anchoring in production |
| **Effective-dated assignments** | History and "effective dates for organisational changes" without overwrites | More complex "current" queries (indexed) |
| **Monitoring, not blocking** | A governance layer must accept records to be able to detect problems; blocking would hide them | Policy choice; blocking rules could be added as a pre-commit hook per scenario |
| **React + Vite SPA** (TanStack Query, React Router) | Requested stack; reusable `DataTable`/`FormModal`/`Query`/`useAct`; React escapes data ⇒ no XSS surface; permissions drive navigation | Extra Node toolchain; Django also serves the built app for single-process deploys |
| **YAML-versioned detection config** | Weights/thresholds are configuration, versioned and hashed per run | — |
| **Design patterns where they remove duplication** (Strategy+Registry detectors, data-driven StateMachine, Observer signal, Adapter at the ORM edge) | Open/Closed extension, one implementation of each concept; see [UNDERSTANDING.md](UNDERSTANDING.md) §5–7 | More indirection than plain CRUD – kept only where it pays |

## 2. Technology selection

| Need | Choice | Why |
|---|---|---|
| API | Python 3.11+, **Django 5/6 + Django REST Framework**, drf-spectacular | Batteries-included ORM/migrations/admin-grade conventions; DRF serializers for validation; OpenAPI generation; contract stays consumable from a Go core |
| Persistence | Django ORM + migrations; SQLite → PostgreSQL (`DATABASE_URL`) | Zero-setup demo, production-grade path |
| ML / stats | scikit-learn (Isolation Forest), SciPy, NumPy, pandas, networkx | Mature, free, deterministic with seeds; no GPU, no external service |
| AI assistance | OpenAI-compatible adapter → Gemini free tier / Groq free tier / Ollama local; template fallback | "Free API" requirement; no vendor lock-in; works fully offline |
| Auth | PyJWT + Django's PBKDF2 hasher | No extra native dependencies; replace with OIDC in production |
| Tests | pytest-django (rolled-back transaction per test over a once-seeded DB) + Playwright UI smoke test | 62 backend tests, ~8 s |

## 3. AI & anomaly-detection methodology

Five layers (details and "why each technique" in [ARCHITECTURE §5](ARCHITECTURE.md)): **rules → robust statistics → Isolation Forest → graph → AI-assisted briefing**. Findings from all layers are merged per (category, subject), scored with a **noisy-OR** of weighted indicators and explained by a deterministic template. The LLM never scores.

* **Feature engineering:** practitioner-week vectors (`load`, `cancel_rate`, `noshow_rate`, `heavy_mod_rate`, `mismatch_rate`, `overlap_pairs`), supervisor-week vectors (`n_decided`, `approve_rate`, `doc_missing_rate`, `mean_minutes`, `rapid_rate`), policy-expected referral matrices, referral/approval graphs ([DATASET §2](DATASET.md)).
* **Cold start without labels** (brief §7.3): explicit rules encode policy; statistics compare to peers / to the policy-implied expectation; Isolation Forest finds multivariate outliers unsupervised; synthetic data with injected anomalies provides a *measurement harness*, not training labels. Investigator outcomes (false-positive feedback) are stored to calibrate later.
* **Explainable risk score:** `score = 100·(1 − Π(1 − wᵢsᵢ))`; Σ per-indicator points = score; UI shows indicator, measured value, reference, weight, strength, points. Levels Low/Medium/High/Critical from YAML.
* **Distinguishing suspicious from legitimate** (scenario 2): expectation uses specialisation + capacity (+5 % policy slack); a naive-uniform test is computed alongside, and candidates that fail only the naive test are listed as **suppressed** with both p-values (seed 42: counselor #41, naive p = 0.0002, policy-aware p = 0.57).
* **Corroboration rule:** alerts supported *only* by ML/volume indicators are capped at Low (the legitimate end-of-period supervisor scores 28.7 → Low rather than Medium).
* **Versioning & reproducibility:** `ruleset_version`, `model_version` (feature-set/params/seed hash), `config_hash` stored on every run/alert; fixed seeds (IsolationForest, Monte-Carlo); test asserts a second run produces identical scores and zero new alerts.

## 4. Detection performance on the synthetic scenarios

Evaluation unit: *(user, category)* pairs; positive = alert at **Medium or above**. Alert subject counts (all users for network/subject-less alerts). 16 injected positives, 7 hard negatives.

**Seed 42 (the demo dataset)**

| Category | Precision | Recall | F1 | Notes |
|---|---|---|---|---|
| A Therapist (overlap, duration, cancellations) | 1.00 | 1.00 | 1.00 | 3/3 |
| B Counselor (referral concentration) | 1.00 | 1.00 | 1.00 | 2/2 |
| C Supervisor (approvals) | 1.00 | 1.00 | 1.00 | 1/1 |
| D Admin/platform (out-of-scope, edit burst, brute force, IP spraying) | 1.00 | 1.00 | 1.00 | 7/7 users |
| E Network ring | 1.00 | 1.00 | 1.00 | 3/3 |
| **Overall** | **1.00** | **1.00** | **1.00** | tp 16 · fp 0 · fn 0; hard-negative FPs at ≥ Medium: **0/7** |

The only alert touching a hard-negative user is the legitimate high-volume supervisor, correctly **Low (28.7)**.

**Ablation (which layers add value)** — alert counts as positive only if the chosen layers *alone* reach the Medium floor:

| Layers | Precision | Recall | F1 |
|---|---|---|---|
| Rules only | 1.00 | 0.625 | 0.77 |
| Statistics only | 1.00 | 0.19 | 0.32 |
| ML only | 0.00 | 0.00 | 0.00 |
| Graph only | 1.00 | 0.19 | 0.32 |
| Rules + statistics | 1.00 | 0.81 | 0.90 |
| **Full ensemble** | **1.00** | **1.00** | **1.00** |

Reading: rules carry the logical/policy scenarios; statistics are needed for referral steering and cancellation patterns; the graph is the *only* way the ring is detected at Medium+; ML never exceeds the threshold alone **by design** and instead corroborates (e.g. it adds points to the overlap, duration, approval and cancellation alerts).

**Robustness over 8 different synthetic worlds** (`backend/scripts/multi_seed_eval.py 1…8`): mean precision **0.980**, mean recall **1.000**, mean F1 **0.989**, hard-negative false positives **0** in every seed. Seed 2 has 3 extra (user, E) pairs: the graph layer found a genuine cluster created by chance (the already-concentrated counselor + a supervisor who approved 24/24 reviews, probability ≈ 1 % per pair but ≈ 20 % somewhere among 24 pairs). We deliberately did **not** tune this away — see limitations.

**Honest caveat.** The anomalies and the detectors were written by the same author on stationary synthetic data. These numbers show the *machinery works and is reproducible*, not that production precision will be 1.0. Expect materially lower precision on real data (see §6).

## 5. Known limitations & potential false positives

| Area | Limitation | Mitigation in place / next step |
|---|---|---|
| Data | Synthetic, stationary, self-authored anomalies | Multi-seed check; shadow-mode calibration on real data |
| Overlap rule | Tolerance 5 min; legit unrecorded group sessions or timezone/sync issues → false positives | `group_id` exemption; benign explanations listed; `record_refs` dedup |
| Duration mismatch | Late check-out / outages look like inflation | Share threshold (≥12 %, ≥4 events); explanation lists benign causes |
| Referral concentration | Client preference, availability, language, geography not in the policy model | 5 % slack; suppression list; investigator FP feedback; extend eligibility model |
| Graph ring | Chance 100 % approval runs in small teams (seed 2) | Needs **both** edges + policy lift; add Bayesian approval-rate test / min cohort-adjusted threshold |
| ML | Isolation Forest on 24/8-user cohorts is weak; no drift handling | Weak weight + Low cap; explanation required; rolling re-fit in production |
| Weights | Hand-set expert weights (configurable) | Calibrate on investigator outcomes; keep rules for impossibilities |
| Security | Demo auth: no MFA/SSO/refresh/rotation; JWT in `sessionStorage`; lockout is the only brute-force control; CSP allows inline styles | OIDC, httpOnly cookies, rate limiting (reverse proxy/WAF), TLS at proxy |
| Audit | Hash chain is tamper-*evident*, not tamper-proof (DB admin can rewrite the whole chain) | Periodically anchor the head hash externally |
| Concurrency | One global audit chain: appends are optimistic (unique `prev_hash`, retry on a lost race), so heavy write bursts retry; verified with 4 concurrent workers (no fork) | Per-tenant chains / sequence-based ordering if write volume grows |
| Policy | Approvals without documentation are accepted and flagged, not blocked | Make blocking configurable per policy |
| Scheduling | Detection is on-demand/batch | CronJob/worker; incremental features |
| Deployment / HA | Verified: SQLite, PostgreSQL 16 (all tests + evaluation identical), the Docker image, and a replicated stack (PostgreSQL + 2 app replicas + nginx): 130 req/s, 0 errors, audit chain intact; killing one replica mid-run cost 1 in-flight request (see [DEPLOYMENT.md](DEPLOYMENT.md)). Not verified: long soak, multi-machine load, PostgreSQL row-level security, database failover, disaster recovery; the CI workflow has been validated step by step locally but has not yet run on a hosted runner | The database and the load balancer are single instances in the compose stack – production needs a managed PostgreSQL with standby and a managed LB; see DEPLOYMENT.md §4 |
| Fairness | Peer comparison can penalise legitimately different roles (part-time, new starters) | Cohort by role/FTE/tenure; fairness monitoring |
| Human oversight | System cannot prevent misuse of alerts by reviewers | No auto-action path; documented process required; audit of who viewed what; reviewer ≠ subject |

## 6. Security considerations (summary)

See [ARCHITECTURE §7](ARCHITECTURE.md). Highlights: PBKDF2 + lockout + uniform auth errors; least-privilege RBAC with relationship scoping; **administrative roles hold no clinical permission**; denied access is persisted and feeds detection (scenario 4); self-privilege-change blocked; conflict-of-interest guard for alerts; client-ref redaction; pseudonymised LLM prompts; hash-chained audit; security headers/CSP; generic 500 responses; secrets via environment only.

## 7. Scalability strategy

Current: 47 users / 5.1k sessions / 0.4k referrals / 0.9k reviews → a full detection run takes **≈ 1 s** (single process), 97 tests ≈ 14 s. Measured on the replicated stack (PostgreSQL + 2 replicas × 2 workers, one machine): **130 req/s, p95 ≈ 200–230 ms, 0 errors**, and one replica can die without an outage ([DEPLOYMENT.md](DEPLOYMENT.md)). Strategy: (1) PostgreSQL + indexes already placed on hot predicates; (2) incremental weekly aggregates (materialised views) instead of full-frame reloads; (3) run detectors per cohort in parallel workers on a schedule; Monte-Carlo test cost ∝ `sims × referrals × therapists`, bounded by the ≥20-referral gate; (4) SQL-level alert visibility (RLS) and keyset pagination; (5) split detection into its own deployment while keeping the same DB contract; (6) optional LLM calls are asynchronous and cacheable.

## 8. Estimated infrastructure & operational cost (order-of-magnitude, to be validated)

Assumptions: ~2,000 practitioners, ~50k sessions/month, one region, 24/7.

| Item | Prototype | Production estimate (monthly) |
|---|---|---|
| App (2 × small containers, HA) | $0 (local) | $60–120 |
| PostgreSQL (managed, small HA + backups) | $0 (SQLite) | $120–250 |
| Detection worker (CronJob, 2 vCPU few minutes/run) | $0 | $10–30 |
| Logs/metrics/alerting | $0 | $50–150 |
| Object storage / backups / WORM audit anchor | $0 | $10–30 |
| LLM briefings (free tiers ≈ $0; paid fallback ≈ 1k alerts × ~1k tokens) | $0 | ≈ $0–20 |
| **Total** | **$0** | **≈ $250–600 / month** infra; plus people cost: ~0.25–0.5 FTE reviewer per 100 alerts/week at expected volumes |

## 9. Roadmap to production readiness

| Phase | Items |
|---|---|
| **0 – Governance (before any real data)** | DPIA, lawful basis, clinical-governance & HR sign-off, staff notice, appeals process, reviewer training, retention policy |
| **1 – Hardening (4–6 wks)** | OIDC/SSO + MFA, httpOnly cookies/CSRF, per-IP rate limiting, secrets manager, TLS/HSTS, SAST/DAST/dependency scanning, Postgres RLS + managed HA database, external audit anchoring, backup/restore drills, long soak and multi-machine load tests (CI, replicated stack and a first load test already exist) |
| **2 – Integration (4–6 wks)** | Contract with Go core (OpenAPI + events/outbox), identity projection, event ingestion, scheduler/worker split, observability (traces, metrics, SLOs) |
| **3 – Model quality (6–10 wks)** | Shadow mode, threshold calibration on outcomes, supervised calibration layer on indicator strengths, drift/fairness dashboards, richer policy model (language/geo/availability), Bayesian tests for small-sample rates |
| **4 – Operations** | Reviewer workload tooling (queues, SLAs, bulk actions), case management exports, periodic model/rule review board, red-team exercises for the detectors |
