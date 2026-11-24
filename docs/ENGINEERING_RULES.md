# Engineering rules

**English** · [فارسی](fa/ENGINEERING_RULES.md)

The rules that keep the codebase small, safe and consistent. They are enforced by tests where possible. Read [UNDERSTANDING.md](UNDERSTANDING.md) first for the big picture; step-by-step recipes are in [HOWTO.md](HOWTO.md).

## Commands

| Task | Command |
|---|---|
| Setup | `python3 -m venv .venv && . .venv/bin/activate && pip install -r backend/requirements.txt && (cd frontend && npm install)` |
| Backend (from `backend/`) | `python manage.py migrate && python manage.py seed_demo --detect && python manage.py runserver 0.0.0.0:8000` |
| Frontend (from `frontend/`) | `npm run dev` (proxies to :8000) · `npm run build` (Django then serves it) |
| Tests | `cd backend && python -m pytest -q` |
| Translation check | `cd frontend && npm run check:i18n` |
| Detection quality | `python manage.py evaluate` |
| LLM guardrails | `python manage.py evaluate_llm` (add `--live` with a key) |
| UI smoke test | `node frontend/e2e/smoke.cjs` |
| Regenerate generated docs | `python manage.py export_docs` |

## Architecture rules (do not break)

1. **Layers**: `views` (HTTP + serializer validation) → `services` (business rules, transactions, audit) → `models`. No business logic in views.
2. **Boundaries are Django apps** (`accounts/hr`, `clinical/supervision`, `core`, `monitoring`). Cross-boundary references to people are integer IDs, never FKs. Clients are pseudonyms – never add real PII.
3. **Authorization** only via `core/rbac.py` + the declarative `perms = {...}` on each view (`core/permissions.py`; undeclared ⇒ denied). Relationship scoping lives in `hr/selectors.py` and `monitoring/visibility.py`. Changing it ⇒ run `export_docs` and update `tests/test_security.py`.
4. **Human-in-the-loop**: no code path may change a user's status/role/contract from an alert or score. `detection/` is pure Python and must not import Django. A test enforces this.
5. **LLMs never score or decide.** They only see the pseudonymised, sanitised evidence pack (`detection/assistant/pack.py`). Behaviour rules (refusals, tone, language) live in the **prompt** (`investigator.SYSTEM`) – no keyword/regex lists. Every reply must pass the list-free deterministic checks in `guardrails.validate()` (schema, citations, numbers, identity) **and** the LLM judge (`judge.py`: tone, consistency, disguised identity) or be replaced by the deterministic fallback; no judge verdict ⇒ fallback. The assistant has no write path. A new LLM behaviour ⇒ add a scenario in `detection/assistant/redteam.py`; run `python manage.py evaluate_llm` (and `--live` with a key).
6. **State changes** go through a `StateMachine` (`core/statemachine.py`); **sensitive reads/writes** call `core.audit.audit()` / `log_admin()`; denials are recorded by `RolePermission`.
7. Audit rows written just before raising must happen **outside** `transaction.atomic()` (otherwise they roll back).
8. Detection weights/thresholds live in `backend/detection/config.yaml` (versioned) – never hard-code them; detectors build indicators with `cfg.ind(...)`.
9. DRY first: reuse `bursts()`, `StateMachine`, `validated()`, `DataTable`/`FormModal`/`Query`/`useAct` before adding new helpers.
10. **i18n**: the DB stores canonical English; localise only at presentation (`core/i18n.py`, `detection/i18n.py`, `monitoring/localize.py`, frontend `t()` + `src/lib/fa.js`). New user-visible text ⇒ add its Persian (`npm run check:i18n`, `tests/test_i18n.py` must stay green); LLM guardrails must hold in both languages.
11. Secrets only via env (`backend/.env` is git-ignored; keep `.env.example` current).
