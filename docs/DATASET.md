# Synthetic dataset, assumptions & limitations

**English** · [فارسی](fa/DATASET.md)

**No real personal, clinical or confidential data is used anywhere.** Names are random combinations from a fixed list; clients exist only as pseudonyms (`C-0001`…); no free-text clinical content exists in the schema.

Generator: `backend/seed/generate.py` (`python manage.py seed_demo [--seed-value N] [--reset] [--detect]`) · deterministic (default seed 42) · writes `data/ground_truth.json` (git-ignored) used only by `manage.py evaluate`.

## 1. Structure (≈ 12 weeks, Mon 2026-08-31 → Fri 2026-11-20)

| Entity | Volume (seed 42) | Notes |
|---|---|---|
| Staff accounts | 47 | 2 platform admins, 2 HR admins, 2 compliance reviewers, 8 supervisors, 24 therapists, 6 assistant counselors, +3 pending "temp" accounts created by the rogue admin |
| Therapist specialisations | trauma 2 · anxiety 5 · depression 5 · couples 4 · child 4 · addiction 4 | trauma has only two eligible practitioners → creates the *policy-explained concentration* hard negative |
| Clients | 360 pseudonyms, each with a primary need | |
| Sessions | 5,091 (incl. group sessions and 72 future scheduled) | 50-min slots Mon–Fri 09–17; 86 % completed / 8 % cancelled / 6 % no-show; check-in/out jitter; 30 % in-person at a fixed location per therapist |
| Referrals | 864 (12 per counselor per week) | counselor need-mix varies; target chosen ∝ capacity among practitioners eligible for the need |
| Reviews | 940 (48 pending/in-progress) | ~3 per supervisee-week; ~82 % approved; documentation present 96 %; review time ≈ N(14, 4) min |
| Admin / access | 1,630 access events, 115 admin activities | HR admin 0–3 edits per working day; 2–4 logins per user-week; isolated typos and isolated denials as noise |
| Supervision | 24+1 assignments (1 historical reassignment), 288 meetings (≈85 % attended), 6 quality issues, corrective actions | |
| Credentials/contracts/lifecycle | 2 credentials + 1 contract + onboarding per practitioner; one expiring, one expired, one suspend→reactivate | |

## 2. Feature definitions (used by ML / statistics)

| Feature | Definition |
|---|---|
| `load` | non-cancelled+cancelled sessions that week ÷ weekly capacity (group sessions count once) |
| `cancel_rate`, `noshow_rate` | share of the week's sessions |
| `heavy_mod_rate` | share of sessions with ≥ 2 modifications |
| `mismatch_rate` | completed sessions with no check-in, or reported duration exceeding check-in/out span by > max(10 min, 25 %) |
| `overlap_pairs` | overlapping 1:1 session pairs starting that week (group sessions excluded) |
| `n_decided`, `approve_rate`, `doc_missing_rate`, `mean_minutes`, `rapid_rate` | per supervisor-week: reviews decided, share approved, approved without documentation, mean review time, share under 3 min |
| referral expectation | per referral: probability ∝ capacity over practitioners whose specialisation matches the need; 5 % "policy slack" spread uniformly (exceptions/client requests) |

## 3. Anomaly generation methodology

Injected on top of the normal process, each with an explicit **ground truth** entry:

| Category | Scenario | Injection |
|---|---|---|
| A | `session_overlap` | 7 overlapping pairs over the last 3 weeks for one therapist, 4 of them in-person at two different locations |
| A | `duration_discrepancy` | last 5 weeks: 45 % of completed sessions report 50 min but check-in span 22–30 min; 12 % completed with no check-in |
| A | `cancellation_pattern` | last 4 weeks: 38 % cancelled, 60 % of sessions modified 2–4 times |
| B | `referral_concentration` | last 6 weeks: 82 % of one counselor's referrals go to 2 practitioners (mostly specialisation mismatches) |
| C | `approval_burst` | 58 approvals within ~30 hours, review time ≈ 1.2 min, ~45 % intended without documentation (22 of the 87 approvals in the 28-day window lack documentation) |
| D | `admin_out_of_scope` | platform admin: 9 denied clinical/HR/supervision requests in 27 min, 3 accounts created in 6 min, 3 privileged role grants |
| D | `admin_modification_burst` | HR admin: 14 credential edits + 4 contract edits in ~45 min |
| D | `failed_login_burst` / `multi_account_ip` | 14 failed logins on one account from 2 addresses in 14 min; one address failing against 4 more accounts |
| E | `referral_approval_ring` | one counselor sends ~51 % of referrals to one anxiety therapist (policy-consistent on its face), who gets ~89 % of intake from that counselor; the therapist's supervisor approves 22/22 reviews in ~6.5 min each with documentation |

**Hard negatives** (must *not* produce Medium+ alerts): busy-but-legitimate therapist (38/wk capacity, 33 sessions/wk), group sessions (shared interval), back-to-back touching sessions, counselor in the trauma unit (concentration explained by policy), supervisor with a legitimate end-of-period burst (42 reviews, complete documentation, normal time), normal HR admin, normal platform admin.

## 4. Assumptions

1. Sessions have a *scheduled* interval, a *reported* duration and platform-measured check-in/out; the latter is the only verification source.
2. Specialisation + capacity define the assignment policy; real policy may add language, location, availability, client preference.
3. An approval "without documentation" is recorded by a boolean attested at review time.
4. The platform logs authorization decisions (allowed/denied) and admin actions with timestamps and IPs.
5. All timestamps are UTC; the detection reference time (`as_of`) is the latest data timestamp, which makes results reproducible.

## 5. Limitations of the synthetic data

* **The injected anomalies were written by the same author as the detectors.** Perfect scores on the main seed are therefore *optimistic*; `backend/scripts/multi_seed_eval.py` over 8 seeds (see report) is the more honest signal (mean precision 0.98, recall 1.00).
* Real fraud is adaptive, noisy and rarer than 10 injected cases in 47 users; base rates, seasonality, clinician heterogeneity and data-quality problems are much worse than simulated.
* Normal behaviour is i.i.d. and stationary; no holidays, part-timers, shifts, travel times, supervision cycles or onboarding ramp-ups.
* Network structure is small (24/6/8); graph metrics (density, components) are barely meaningful at this size.
* Ground truth is perfect; real investigators produce noisy labels.

## 6. Moving to real data (after proper authorisation)

1. **Legal/ethical gate first**: DPIA, lawful basis, clinical-governance approval, works-council/staff notice; keep human-in-the-loop and appeal paths.
2. **Ingest via events/ETL** into the same `clinical_*`/`supervision_*`/`core_*` tables (pseudonymise client identifiers at the border; keep the mapping in the core platform only).
3. **Shadow mode** (alerts hidden from decisions) for 4–8 weeks: measure alert volume per reviewer-hour, tune thresholds on *investigator outcomes* (false-positive feedback already captured), recalibrate weights per scenario.
4. **Learn from outcomes**: once ≥ a few hundred closed alerts exist, fit a supervised calibration layer (e.g. logistic regression on indicator strengths) *on top of* the explainable indicators; keep rules for logical impossibilities.
5. **Fairness & drift monitoring**: compare alert rates across specialisations/employment types/units; re-fit Isolation Forests on a rolling window; alert on drift.
6. **Replace synthetic noise assumptions** with measured distributions (session length, cancel rates) per specialisation.
