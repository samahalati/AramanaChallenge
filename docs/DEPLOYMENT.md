# Deployment, high availability, CI and load test

Everything here was executed and measured on the prototype (numbers below come from real runs); what was **not** verified is listed at the end.

## 1. Three ways to run it

| Mode | Command | Database | Use |
|---|---|---|---|
| Local dev | `python manage.py runserver` + `npm run dev` | SQLite file | development, demo |
| Single container | `docker build -t aramana . && docker run -p 8000:8000 aramana` | SQLite inside the image (demo data baked in) | quick demo |
| **Replicated stack** | `docker compose up -d --build` | PostgreSQL 16 | production-shaped (below) |

## 2. Replicated stack (`docker-compose.yml`)

```
                 ┌──────────┐      ┌─ app replica 1 (gunicorn ×2 workers) ─┐
 browser ──8080─▶│  nginx   │─────▶│                                        │──▶ PostgreSQL 16
                 │ (lb)     │      └─ app replica 2 (gunicorn ×2 workers) ─┘     (volume pgdata)
                 └──────────┘   health-checked, dead replica skipped
```

```bash
export SECRET_KEY=$(python3 -c "import secrets;print(secrets.token_urlsafe(48))")   # SAME value for every replica (JWTs are verified by any of them)
export POSTGRES_PASSWORD=$(python3 -c "import secrets;print(secrets.token_urlsafe(18))")
docker compose up -d --build              # db → init (migrate + demo data, once) → 2 app replicas → nginx
docker compose up -d --scale app=3        # add replicas
open http://localhost:8080                # compliance@aramana.test / Demo!2345
```

Design points that make the replicas interchangeable:

* **Stateless app.** No session in memory, no local files: JWT signed with the shared `SECRET_KEY`; accounts, lockout counters, rate-limit counters, alerts and the audit chain live in PostgreSQL. A suspended account is refused by *every* replica on its next request (the user is re-loaded per request).
* **Readiness probe.** `GET /api/health` runs `SELECT 1` and answers 503 when the database is unreachable; compose uses it to mark replicas healthy, the load balancer retries another replica on connect errors/502/503.
* **Race-safe audit chain.** `AuditLog.prev_hash` is `UNIQUE`: two workers that read the same chain tail cannot both append – the loser retries on the new tail (`core/audit.py`, test `test_audit_append_survives_a_lost_race`). Without this the hash chain would fork when more than one worker writes.
* **One-shot init.** `init` runs migrations and seeds only when the database is empty; replicas wait for it.
* **No secrets in the image.** `.dockerignore` excludes every `.env`, the local database and `node_modules`.

## 3. Measured behaviour (`backend/scripts/loadtest.py`)

Setup: one machine (shared sandbox), PostgreSQL 16 + 2 replicas × 2 gunicorn workers + nginx, 16 client threads, 30 s, mixed workload (5 read endpoints + audited writes), seed data of 47 users / 5.1k sessions.

| Run | Throughput | Errors | p50 / p95 latency | Audit chain |
|---|---|---|---|---|
| Steady state | **130 req/s** (3 922 requests) | **0** | 112–133 ms / 203–227 ms | `ok` (2 018 rows, written concurrently by 4 workers) |
| One replica killed (`docker kill`) 10 s into the run | 89 req/s | **1** (the one in-flight write on the killed replica) | 186–207 ms / 245–274 ms | `ok` (3 364 rows) |

Reading: the stack keeps serving when a replica dies; the request that was being processed by the killed replica fails (POSTs are not retried automatically – they are not idempotent), every other request is served by the surviving replica at lower throughput. These are single-machine numbers for sizing orientation, **not** a capacity guarantee.

```bash
python backend/scripts/loadtest.py --base http://localhost:8080 --seconds 30 --threads 16   # exit code 1 on any error or broken chain
```

## 4. What "HA" means here – and what it does not

| Covered (verified above) | Not covered (needs infrastructure outside this repository) |
|---|---|
| Several identical app replicas behind a load balancer; loss of one replica is tolerated | The **database is a single instance** here. Production: managed PostgreSQL with a standby (multi-AZ), automated failover, PITR backups, tested restores |
| Health-checked rotation, automatic restart (`restart: unless-stopped`) | The load balancer itself is single; production: managed LB / two LBs with a virtual IP, TLS termination, WAF |
| Concurrent writers cannot corrupt the audit chain | Multi-region, disaster-recovery drills, zero-downtime migration procedure, autoscaling, long soak tests |
| Config via environment variables, no secrets in the image | A secrets manager and key rotation (the JWT key is a plain environment variable) |

## 5. Continuous integration (`.github/workflows/ci.yml`)

Runs on every push to `main` and every pull request:

| Job | What it enforces |
|---|---|
| `backend` (Python 3.11 / 3.12 / 3.13) | `ruff` (real errors), `manage.py check`, migrations match models, **all tests**, detection quality (`evaluate`), deterministic LLM guardrail red-team (`evaluate_llm`), and that `docs/openapi.yaml` + `docs/RBAC_MATRIX.md` are regenerated from the code (stale docs fail the build) |
| `postgres` | migrate + seed + evaluation + all tests on PostgreSQL 16 |
| `frontend` | `npm ci`, every UI string has a Persian translation (`check:i18n`), production build |
| `docker` | the image builds, starts, answers `/api/health`, serves the SPA and Swagger, sends `X-Frame-Options: DENY` |

The live-LLM evaluation (`evaluate_llm --live`) is deliberately **not** in CI (needs a key, is rate-limited, is not deterministic). The workflow was validated locally step by step (every `run:` command was executed); the hosted runner has not run it yet – the first push will show it.
