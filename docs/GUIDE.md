# Complete guide: install, run, and how everything works

**English** · [فارسی](fa/GUIDE.md)

This is the practical manual. For the design reasoning read [UNDERSTANDING.md](UNDERSTANDING.md); for rules and recipes see [ENGINEERING_RULES.md](ENGINEERING_RULES.md) and [HOWTO.md](HOWTO.md).

## Contents
1. [What you get](#1-what-you-get) · 2. [Requirements](#2-requirements) · 3. [Install](#3-install) · 4. [Configure](#4-configure) · 5. [Run](#5-run) · 6. [First look: accounts and pages](#6-first-look-accounts-and-pages) · 7. [How everything works](#7-how-everything-works) · 8. [Using the API](#8-using-the-api) · 9. [The LLM assistant](#9-the-llm-assistant) · 10. [Commands cheat sheet](#10-commands-cheat-sheet) · 11. [Troubleshooting](#11-troubleshooting)

---

## 1. What you get

| Part | Where | Port |
|---|---|---|
| **API** (Django + Django REST Framework) with Swagger docs | `backend/` | `8000` (`/api/docs/`) |
| **Web app** (React + Vite), Persian by default with an English switch | `frontend/` | `5173` in development |
| **SQLite database** (created automatically) | `data/aramana.sqlite3` | – |

Nothing else is needed: no database server, no paid API, no API key (an LLM key is optional).

## 2. Requirements

| Tool | Version | Check | Get it |
|---|---|---|---|
| Git | any | `git --version` | https://git-scm.com |
| Python | **3.11 or newer** | `python --version` (Windows) · `python3 --version` | https://www.python.org/downloads (on Windows tick *Add python.exe to PATH*) |
| Node.js | **20.19+ or 22+** | `node -v` | https://nodejs.org (LTS). Older Node fails with `styleText` / `EBADENGINE` errors |
| Docker | optional | `docker -v` | only for the container route |

**Python packages** (installed from `backend/requirements.txt`): Django and Django REST Framework (web/API), drf-spectacular (Swagger), PyJWT (login tokens), dj-database-url (database setting), numpy / pandas / scipy / scikit-learn / networkx (the detection engine: statistics, Isolation Forest, graph analysis), PyYAML (detection config), httpx (calls the optional LLM), gunicorn (production server), pytest / pytest-django (tests).
**Frontend packages** (from `frontend/package.json`): React, React Router, TanStack Query, Vite, and the Vazirmatn font (Persian typography).

## 3. Install

```bash
git clone https://github.com/samahalati/AramanaChallenge.git
cd AramanaChallenge

# Python environment
python3 -m venv .venv
source .venv/bin/activate              # macOS / Linux
pip install -r backend/requirements.txt

# Frontend packages
cd frontend && npm install && cd ..
```

**Windows (PowerShell)** – same steps with these differences:
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1             # if blocked: Set-ExecutionPolicy -Scope Process Bypass
pip install -r backend\requirements.txt
cd frontend; npm install; cd ..
```
One-liner on macOS/Linux: `make install`.

## 4. Configure

Everything has a working default. To change something, copy the template and edit it – `backend/.env` is loaded automatically and is **never committed**:
```bash
cp backend/.env.example backend/.env      # Windows: copy backend\.env.example backend\.env
```

| Variable | Default | Meaning |
|---|---|---|
| `DEBUG` | `1` | `0` in production |
| `SECRET_KEY` | dev value | **change in production** (signs login tokens) |
| `ALLOWED_HOSTS` | `*` | comma-separated host names |
| `DATABASE_URL` | SQLite file in `data/` | PostgreSQL: `postgres://user:pass@host:5432/db` (+ `pip install "psycopg[binary]"`) |
| `ACCESS_TOKEN_MINUTES` | `60` | login token lifetime |
| `MAX_FAILED_LOGINS` / `LOCKOUT_MINUTES` | `5` / `15` | account lockout |
| `LLM_PROVIDER` | `none` | `gemini`, `groq` or `ollama` (see [section 9](#9-the-llm-assistant)) |
| `LLM_API_KEY` / `LLM_MODEL` / `LLM_BASE_URL` | empty | provider key, optional model override, optional endpoint override |
| `DETECTION_CONFIG` | `backend/detection/config.yaml` | weights and thresholds of the fraud engine |

## 5. Run

**First time only – create the data** (schema + synthetic organisation + first detection run):
```bash
cd backend
python manage.py migrate
python manage.py seed_demo --detect        # Persian demo data (default). English: add --lang en
```
Re-create everything from scratch any time with `python manage.py seed_demo --reset --detect`.

**Option A – development (two terminals)**
```bash
# terminal 1
cd backend && python manage.py runserver 0.0.0.0:8000
# terminal 2
cd frontend && npm run dev                 # open http://localhost:5173
```
**Option B – one process**: `cd frontend && npm run build`, then run only the backend; Django serves the built app at **http://localhost:8000**.
**Option C – Docker**: `docker build -t aramana . && docker run -p 8000:8000 aramana` → http://localhost:8000 (data is seeded during the build).
**Option D – Make**: `make install seed backend` and `make frontend`.

## 6. First look: accounts and pages

Open the app and press one of the demo buttons (password for all accounts: `Demo!2345`). The language switch **EN / فا** is in the header.

| Account | Role | Pages it sees | Good things to try |
|---|---|---|---|
| `compliance@aramana.test` | Compliance reviewer | Fraud & Anomaly · HR (read) · Audit | open an alert, read *why this score*, start review, ask the AI assistant, press **Run detection now** |
| `hr@aramana.test` | HR administrator | HR & Admin · Fraud & Anomaly (their alerts) | add a credential, record professional development, read a practitioner's *Activity & performance*, suspend/reactivate (a reason is required), reassign a supervisor |
| `supervisor1@aramana.test` | Clinical supervisor | Supervision · Fraud & Anomaly (operational/clinical) | open a review, record a decision, assign a corrective action, escalate a quality issue |
| `admin@aramana.test` | Platform admin | Accounts · Audit · security alerts | create an account; try `/hr` ("not available"); then call a clinical API → 403 and a security alert is raised |
| `admin2@aramana.test` | Platform admin (rogue) | – | the *subject* of a pre-seeded **critical** alert (scenario 4) |
| `hr2@aramana.test` | HR administrator | – | subject of an "edit burst" alert |
| `therapist1@aramana.test` | Therapist | My work | schedule two **overlapping** sessions, then run detection as compliance |
| `counselor1@aramana.test` | Assistant counselor | My work | create referrals |

The four required scenarios (suspicious sessions, abnormal referrals, unusual approvals, unauthorised admin activity) are pre-seeded; the README lists how to trigger each live.

## 7. How everything works

**Login and permissions.** `POST /api/auth/login` returns a signed token (HS256 JWT). Every request loads the user fresh from the database, so a suspended user is locked out immediately. Access is decided in two layers: the **role** (`backend/core/rbac.py`: what kind of action) and the **relationship** (which records: own, current supervisees, people named in an alert). Anything a view does not declare is denied. Denials are stored as access events and may themselves raise alerts. Administrators hold **no clinical permission** (separation of duties), and nobody can open an alert about themselves.

**Audit.** Sensitive reads/writes append a row to a **hash-chained** audit log (each row contains the previous row's hash), so tampering is detectable: the Audit page shows *chain verified*.

**Module A – HR & administration** (`hr`, `accounts`). Practitioner profiles, credentials (with expiry tracking), contracts, lifecycle (pending onboarding → active ⇄ suspended → terminated; every change needs a documented reason and is a human decision), organisation tree, effective-dated supervisor assignments (changing one end-dates the previous relationship), and an **activity & performance** view per practitioner (sessions, referrals, quality indicators, supervision attendance, professional development, trends, alerts about the person – aggregates only, no clinical content).

**Module B – clinical supervision** (`supervision`, `clinical`). Therapists schedule sessions (overlaps are *accepted but monitored*, not blocked). Supervisors see only their current supervisees: dashboard (overdue reviews, trend), review workflow (pending → in progress → decision → corrective actions → close), meetings, quality issues. Escalating a quality issue creates a traceable alert for compliance. Clients are pseudonymous references (`C-0001`), never real identities.

**Module C – fraud & anomaly detection** (`detection`, `monitoring`).
1. *Data → features:* `monitoring/loaders.py` turns database rows into tables; the engine itself (`backend/detection/`) is pure Python and never touches Django.
2. *Five layers of detectors* (`detection/detectors/`): **rules** (overlaps, impossible locations, rapid or undocumented approvals, denied-access bursts…), **robust statistics** (peer comparison), **Isolation Forest** (multivariate outliers), **graph analysis** (exclusive referral/approval clusters), and a **policy-aware test** that suppresses referral concentration explained by specialisation.
3. *Scoring* (`scoring.py`): every indicator has a weight in `config.yaml`; the score is `100 × (1 − Π(1 − weight × strength))`, so it equals the exact sum of indicator points you see in the UI. Levels: Low < 35 ≤ Medium < 60 ≤ High < 80 ≤ Critical. Alerts backed **only** by weak indicators (ML score, volume) are capped at Low.
4. *Alerts* carry evidence, an explanation, a recommended investigation step, the ruleset/model version, and are de-duplicated across runs.
5. *Investigation workflow* (human only): new → under review → info requested → escalated → closed (no action / substantiated) or false positive; notes are required where it matters, everything is on the timeline and audit log. No score or alert can change a person's status, role or contract.
6. *Evaluation:* `python manage.py evaluate` measures precision/recall/F1, an ablation by layer and hard negatives against the synthetic ground truth (the numbers are optimistic because the anomalies are self-authored – see the technical report).

**The LLM assistant** is optional and advisory – see [section 9](#9-the-llm-assistant).

**Language.** The database stores canonical English; text is translated when presented (request header `Accept-Language`). The web app is Persian/RTL by default, with Jalali dates; the switch reloads the page in the other language. Details: [I18N.md](I18N.md).

**Synthetic data.** `seed/generate.py` builds ~47 users, ~5k sessions, referrals, reviews and admin activity, injects the required anomalies **and look-alike innocent cases** (hard negatives), and writes `data/ground_truth.json` for evaluation. See [DATASET.md](DATASET.md).

**Frontend structure.** `frontend/src/features/<module>/` holds one folder per module; shared pieces are `DataTable`, `FormModal`, `Query` (loading/error states) and `useAct` (run a mutation, toast, refresh). The server decides what each role sees; the UI only reflects it.

## 8. Using the API

Interactive documentation: **http://localhost:8000/api/docs/** (Swagger). From the command line:
```bash
TOKEN=$(curl -s localhost:8000/api/auth/login -H 'content-type: application/json' \
  -d '{"email":"compliance@aramana.test","password":"Demo!2345"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')
curl -s -H "Authorization: Bearer $TOKEN" -H "Accept-Language: en" localhost:8000/api/alerts?limit=3
```
`Accept-Language: fa|en` selects the language of titles, explanations and error messages. Main groups: `/auth/*`, `/hr/*`, `/supervision/*`, `/clinical/*`, `/referrals/*`, `/alerts/*`, `/detection/*`, `/audit/*`, `/meta/*`.

## 9. The LLM assistant

On an alert page, reviewers (compliance, platform admin for security alerts) get **Generate briefing** and **Ask**. Without a key it runs in *deterministic mode* (no network): a template briefing built from the evidence. With a free key it uses a real model:

```bash
# backend/.env
LLM_PROVIDER=gemini                    # or groq, or ollama
LLM_API_KEY=your-free-key              # https://aistudio.google.com/apikey · https://console.groq.com/keys · not needed for ollama
```
Restart the backend. The badge on each answer shows who produced it: the model (Gemini/Groq/Ollama), *deterministic template*, or *deterministic template (fallback)* meaning the model failed or a check rejected its reply (open **details** to see why).

Safety model in one paragraph: the model only sees pseudonymised evidence with citable IDs; the prompt forbids sanctions/accusations and tells it to refuse decision-seeking, identity and off-topic questions; every reply must pass deterministic checks (JSON shape, existing citations, numbers present in the evidence, no e-mail/client/person names) **and** a second LLM call acting as a judge (tone, risk-level consistency); if the judge gives no verdict the reply is not shown. It cannot change anything, is rate-limited to 30 requests/hour per user, and every exchange is audited. Full design and honest measurements: [LLM_ASSISTANT.md](LLM_ASSISTANT.md).

## 10. Commands cheat sheet

| Command (from `backend/`) | What it does |
|---|---|
| `python manage.py migrate` | create/upgrade the database schema |
| `python manage.py seed_demo [--reset] [--detect] [--lang fa\|en] [--seed-value N]` | generate synthetic data (optionally wipe first / run detection after) |
| `python manage.py run_detection` | run the detection engine (idempotent) |
| `python manage.py evaluate [--write file.json]` | precision/recall/F1 vs ground truth |
| `python manage.py evaluate_llm [--live] [--alerts N]` | red-team the LLM guardrails (`--live` uses your key) |
| `python manage.py export_docs` | regenerate `docs/RBAC_MATRIX.md` and `docs/openapi.yaml` from the code |
| `python -m pytest -q` | run the 87 tests |
| `python scripts/multi_seed_eval.py 1 2 3 4 5 6 7 8` | robustness across synthetic worlds |

Frontend (from `frontend/`): `npm run dev` · `npm run build` · `npm run check:i18n` · `BASE=http://localhost:5173 node e2e/smoke.cjs` (browser smoke test; needs Playwright).

## 11. Troubleshooting

| Symptom | Cause → fix |
|---|---|
| `EBADENGINE` warnings, then `'node:util' does not provide an export named 'styleText'` | Node is too old → install Node 22 LTS (or 20.19+), reopen the terminal, delete `frontend/node_modules`, run `npm install` again |
| `python` / `pip` not found, or wrong version | use `python3` / `py -3`; on Windows reinstall Python with *Add to PATH* |
| PowerShell refuses `Activate.ps1` | `Set-ExecutionPolicy -Scope Process Bypass`, then activate again |
| `ModuleNotFoundError: No module named 'django'` | the virtual environment is not active (look for `(.venv)` in the prompt) → activate it and re-run `pip install -r backend/requirements.txt` |
| Page loads but shows errors / empty | the backend is not running or has no data → start `runserver`, run `seed_demo --detect` |
| `Address already in use` | another process uses the port → stop it or use `runserver 0.0.0.0:8001` (and change the proxy in `frontend/vite.config.js`) |
| Login fails after many tries | account lockout (5 failures, 15 minutes) → wait, or `seed_demo --reset` |
| Assistant shows *deterministic template* | no `LLM_PROVIDER`/key in `backend/.env`, or the backend was not restarted |
| Assistant shows *fallback* often | free-tier rate limit or overload (HTTP 429/503): it retries, then falls back safely; try again later |
| `429` on the assistant | the 30 requests/hour limit per user |
| English text in the Persian UI | the language is stored in the browser; use the EN/فا switch; for demo *data* re-seed with `--lang fa` |
| `npm run check:i18n` fails | a `t("…")` text has no Persian entry in `frontend/src/lib/fa.js` |

## Production notes
Set `DEBUG=0`, a long random `SECRET_KEY`, real `ALLOWED_HOSTS`, use PostgreSQL, terminate TLS in a reverse proxy, and run `gunicorn config.wsgi -b 0.0.0.0:8000` (the Dockerfile does). Authentication here is demo-grade (local passwords, no MFA/SSO); see the technical report for the full list of limitations.
