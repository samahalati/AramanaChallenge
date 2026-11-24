# How-to playbooks

**English** · [فارسی](fa/HOWTO.md)

Short checklists for the changes you are most likely to make. Concepts and file map: [UNDERSTANDING.md](UNDERSTANDING.md). Rules: [ENGINEERING_RULES.md](ENGINEERING_RULES.md).

## Run and verify the demo end to end
1. `cd backend && python manage.py migrate && python manage.py seed_demo --detect` (add `--reset` to wipe first).
2. `python manage.py runserver 0.0.0.0:8000` (API + Swagger at `/api/docs/`); in `frontend/`: `npm install && npm run dev` → http://localhost:5173 (or `npm run build` and use :8000).
3. Demo logins (password `Demo!2345`): `compliance@`, `hr@`, `supervisor1@`, `admin@`, `admin2@`, `therapist1@`, `counselor1@aramana.test`.
4. The four required scenarios are listed in the README. Scenario 4 live: as `admin@` call `GET /api/clinical/practitioners/15/sessions` five times (403), then run detection as compliance.
5. Verify: `cd backend && python -m pytest -q`, `python manage.py evaluate`, and `BASE=http://localhost:5173 node frontend/e2e/smoke.cjs` (reseed first for a pristine state).

## Add a detector
1. New class in `backend/detection/detectors/<file>.py` subclassing `Detector`: set `category/domain/scenario` (and `kind="behavioral"` only for corroborating signals), implement `detect()` returning `self.finding(...)` objects built with `self.cfg.ind(...)`; decorate with `@register`; import the module in `detectors/__init__.py` if it is a new file.
2. Weights and thresholds go to `backend/detection/config.yaml`; bump `ruleset_version`. Reuse `bursts()` for window rules.
3. A new scenario name needs its explanation text in `detection/explain.py` (and the Persian text in `detection/i18n.py`).
4. Add an injected anomaly **and a hard negative** to `backend/seed/generate.py` (+ ground-truth entry).
5. Tests in `backend/tests/test_detection.py`; run `python manage.py evaluate` and `python scripts/multi_seed_eval.py 1 2 3 4 5`; update the numbers in `docs/TECHNICAL_REPORT.md`.
6. The explanation must trace to indicators – no opaque scores. `detection/` must not import Django.

## Change roles, permissions or visibility
1. Edit `backend/core/rbac.py` (matrix, `ALERT_DOMAIN_VISIBILITY`, `INVESTIGATE_DOMAINS`, `ROLE_NAV`). Views declare needs via `perms = {...}`; relationship rules live in `hr/selectors.py` and `monitoring/visibility.py`.
2. Keep clinical data separate from HR data: `hr_admin` and `platform_admin` must never hold `clinical:*`.
3. Run `python manage.py export_docs` (regenerates `docs/RBAC_MATRIX.md`), add or adjust cases in `backend/tests/test_security.py`.
4. `cd backend && python -m pytest tests/test_security.py -q`.

## Evaluate the detection engine and refresh the report numbers
1. `cd backend && python manage.py seed_demo --reset --seed-value 42 --detect`
2. `python manage.py evaluate` (add `--write ../docs/eval_results.json` to save JSON)
3. `python scripts/multi_seed_eval.py 1 2 3 4 5 6 7 8 | tee ../docs/eval_multi_seed.txt`
4. Copy the tables into `docs/TECHNICAL_REPORT.md`. If a metric regresses, fix the detector or its config – never edit the ground truth.

## Add a workflow, endpoint or screen
* **Workflow:** define a `StateMachine({...})`; call `.apply(action, current)` in the service.
* **Endpoint:** serializer → service function → thin view with `perms = {...}` → URL. Auth, denial logging and audit conventions come for free.
* **Screen:** a page under `frontend/src/features/<module>/` using `Query`, `DataTable`, `useForm` and `useAct`; every visible string goes through `t("…")` and gets its Persian in `src/lib/fa.js` (`npm run check:i18n`).

## Change the LLM assistant
Rules live in the prompt (`detection/assistant/investigator.py::SYSTEM`) and the judge rubric (`judge.py::RUBRIC`). Add an attack to `redteam.py`, run `python manage.py evaluate_llm` and, with a key in `backend/.env`, `evaluate_llm --live`. See [LLM_ASSISTANT.md](LLM_ASSISTANT.md).
