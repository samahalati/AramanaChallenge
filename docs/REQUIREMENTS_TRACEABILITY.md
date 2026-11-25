# Requirements traceability

**English** · [فارسی](fa/REQUIREMENTS_TRACEABILITY.md)

Every clause of the original challenge brief (*"AI Engineer – Technical Challenge"*, 10 pages) mapped to where it is implemented, where it is demonstrated, and which automated test proves it. Section numbers are the brief's. The conformance suite is `backend/tests/test_requirements.py`; deeper behaviour tests live in the other `backend/tests/` files.

Legend: **Code** = implementation · **UI** = where a person sees it · **Proof** = automated test or document.

## 2. Core mission – three modules on one foundation
| Clause | Code | Proof |
|---|---|---|
| Modules A, B, C on a shared, consistent foundation | `backend/core` (RBAC, audit, state machine, errors), one database, one auth | [ARCHITECTURE.md §1–2](ARCHITECTURE.md) |
| Detection engine is a central intelligence layer producing explainable alerts reviewed through HR / supervision interfaces | `backend/detection` → `monitoring` → alert pages; supervisor escalation signal | `test_e2e.py` flows 1–5 |

## 3. Module A – HR & platform administration
| Clause | Code | UI | Proof |
|---|---|---|---|
| 3.1 Professional profiles, user categories, specialisation | `hr/models.py` (`PractitionerProfile`), `accounts/models.py` (roles) | HR → Practitioners | `test_workflows.py` |
| Credentials, licence & certification tracking, expiry | `Credential`, `hr/services.dashboard` | HR dashboard (expiring ≤ 60 days) | `test_credentials_contracts_and_dashboard` |
| Employment/collaboration status, contracts | `PractitionerProfile.employment_type`, `Contract` | Practitioner page | same |
| Onboarding / offboarding; suspension, reactivation, termination | `hr/services.change_lifecycle` + `StateMachine`; reason required | Practitioner page buttons | `test_practitioner_lifecycle_state_machine`, `test_terminate_closes_assignments_and_contracts` |
| Complete activity & status history | `LifecycleEvent` | "Complete activity & status history" card | `test_workflows.py` |
| 3.2 Role definitions, supervisor–supervisee, teams, hierarchy | `core/rbac.py`, `SupervisionAssignment`, `OrgUnit` | Roles page, HR → Organisation | `test_permission_matrix_invariants` |
| Assignment / reassignment, effective dates, historical tracking | `hr/services.assign_supervisor` (end-dates the previous link) | HR → Supervision assignments | `test_assignment_history_preserved_and_validated` |
| **3.3 Performance & activity**: practitioner activity, completed/scheduled sessions, referrals, quality indicators, supervision participation, **professional development**, trends, unusual patterns | `hr/activity.py` (aggregates only, no clinical content), `ProfessionalDevelopment`, `GET /hr/practitioners/{id}/activity`, `POST …/development` | Practitioner page → "Activity & performance", "Professional development", "Unusual activity" | `test_3_3_*` |
| 3.4 RBAC: six roles + other authorised roles; restriction by role, relationship, responsibility, sensitivity | `core/rbac.py`, `core/permissions.py` (undeclared = denied), `hr/selectors.py`, `monitoring/visibility.py` | role-specific navigation | `test_security.py`, `test_3_4_six_roles_and_separation_of_clinical_data`; matrix: [RBAC_MATRIX.md](RBAC_MATRIX.md) |
| Clinical data separated from HR/admin data; unauthorised access prevented and demonstrable | administrative roles hold no `clinical:*`; client references masked (`C-****`) | – | `test_admin_roles_cannot_read_clinical_data_and_denials_are_recorded`, `test_client_refs_redacted_for_hr` |

## 4. Module B – clinical supervision & quality
| Clause | Code | UI | Proof |
|---|---|---|---|
| 4.1 Dashboard: assigned/active/inactive supervisees, pending & overdue reviews, open quality issues, escalation cases, recent activity, trends | `supervision/services.dashboard` | Supervision → Dashboard | `test_4_1_supervisor_dashboard_has_every_required_indicator` |
| 4.2 Assign practitioners, relationships, schedules, participation, history, unresolved issues, assignment changes | `SupervisionAssignment.schedule_every_days`, `SupervisionMeeting`, supervisees list (attendance), HR assignment endpoints | Supervision → Supervisees; HR → assignments | `test_supervisor_dashboard_and_supervisees` |
| 4.3 Review workflow: authorised case info, notes, evaluation, feedback, corrective actions, monitoring plans, closing | `supervision/services` (`start/decide/add_corrective_action/close_review`) | Supervision → Reviews | `test_review_workflow_end_to_end` |
| 4.4 Risk escalation; operational vs clinical vs potential-misconduct distinguished; clinical decisions stay human | `QualityIssue.category`, `escalate_issue` → alert, domains in `core/constants.py` | Supervision → Quality issues | `test_flow5_quality_concern_routed_to_supervisor_and_escalation_back` |
| 4.5 Auditability: who, when, what accessed, decision, corrective actions, completion | `core/audit.py` (hash-chained), review `viewed`/decision events | Audit page, review page | `test_4_5_*`, `test_audit_chain_verifies_and_detects_tampering` |

## 5. Module C – AI-powered fraud & anomaly detection
| Clause | Code | Proof |
|---|---|---|
| 5.1 A–E scenario categories (therapist, counselor, supervisor, admin/platform, cross-user/network) | `detection/detectors/{session,referral,approvals,security,graph,peer}.py` | `test_5_1_all_five_categories_are_detected_and_5_2_all_methods_are_used`, `test_detection.py` |
| 5.2 Rule-based / statistical / ML / graph / AI-assisted explanation, each justified; LLM is not the sole mechanism | rules, `peer.py` (robust statistics), Isolation Forest, `graph.py` (networkx), `detection/assistant/` (advisory only) | [ARCHITECTURE.md §5](ARCHITECTURE.md), [TECHNICAL_REPORT.md](TECHNICAL_REPORT.md), `test_detection_never_modifies_users` |
| 5.3 Configurable scoring; alert content (ID, users, category, timestamp, score, level, method, evidence, explanation, action, status); four levels; explainable & traceable | `detection/config.yaml`, `scoring.py` (noisy-OR), `explain.py`, `monitoring/models.Alert` | `test_5_3_every_alert_carries_the_required_content_and_is_explainable`, `test_noisy_or_points_sum_to_score`, `test_every_alert_is_explainable_and_traceable` |
| 5.4 Investigation workflow: review, evidence, **activity history**, findings, request info, false positive, escalate, close with documented decisions; complete history | `monitoring/services/alerts.WORKFLOW` + `StateMachine`, timeline; `user_history` | UI: alert page ("Activity history of this person") | `test_flow1…`, `test_5_4_*` |
| **Important:** no automatic penalty/suspension/accusation from a score; human review required | the engine only writes alerts; notes required; substantiation is a recorded human finding | `test_detection_never_modifies_users`, `test_assistant_never_changes_state` |

## 6. Integration requirements
| Example in the brief | Implementation | Proof |
|---|---|---|
| Unusual activity → alert | `monitoring/services/runs.run_detection` | `test_flow1…` |
| HR or compliance reviewer examines the alert | `ALERT_DOMAIN_VISIBILITY` in `core/rbac.py` | `test_alert_visibility_by_role` |
| Quality concern routed to the supervisor | `route_to_supervisor`; supervisor escalation back via Observer signal | `test_flow5…` |
| Supervisor review outcome reflected in operational records | `decide_review` → `hr_lifecycleevent(supervision_review)` | `test_4_5_review_decision_is_traceable_and_reflected_in_operational_records` |
| Repeated anomalies → longitudinal monitoring without presuming misconduct | `longitudinal_context`, `user_history` ("alerts are not findings") | `test_flow2…` |
| ≥ 3 end-to-end scenarios | four implemented (section 8) | `test_e2e.py` |
| Integration with the existing (Go) platform | [ARCHITECTURE.md §9](ARCHITECTURE.md) | – |

## 7. Technical & architectural requirements
| Clause | Where |
|---|---|
| 7.1 Well-structured API, modular services, authN/Z, validation, business-logic separation, error handling, **logging**, audit, API docs, transactions | `views → services → models`; DRF serializers; `core/errors.py`; `LOGGING` + `aramana.security` logger (`config/settings.py`, `core/permissions.py`, `accounts/services.py`); `core/audit.py`; Swagger at `/api/docs/` and [openapi.yaml](openapi.yaml); `transaction.atomic` in services. Tests: `test_7_4_denials_and_failed_logins_are_logged`, `test_api_docs_and_schema_are_served` |
| Python AI services compatible with a Go core; technology justified | [ARCHITECTURE.md §9](ARCHITECTURE.md), [TECHNICAL_REPORT.md](TECHNICAL_REPORT.md) |
| 7.2 ERD, schema, relationships, ownership boundaries, audit history, indexing, retention, clinical/administrative separation | [ARCHITECTURE.md §3](ARCHITECTURE.md) (Mermaid ERD, table list, retention note); app boundaries = data ownership |
| 7.3 Feature engineering, model selection, explainable scoring, evaluation, false-positive management, versioning, reproducibility; method without labelled data | `detection/features.py`, `config.yaml`, `evaluate`, `evaluate_llm`, false-positive feedback in the monitoring summary, `ruleset_version`/`model_version` on every alert; [DATASET.md](DATASET.md). Tests: `test_7_3_*`, `test_evaluation_meets_targets_and_no_hard_negative_false_positives`, `test_engine_is_deterministic_and_idempotent` |
| 7.4 Authentication, authorisation, least privilege, sensitive-data protection, secure API communication, audit logging, data minimisation, secrets, common vulnerabilities; no real client data | JWT + lockout; deny-by-default permissions; pseudonymous clients, redaction; hash-chained audit; **security headers (CSP, framing, sniffing, referrer, permissions policy, HSTS in production)** and no-store API responses; secrets only via environment; parameterised ORM; strict serializers; no `dangerouslySetInnerHTML`. Tests: `test_security.py`, `test_7_4_security_headers_on_api_and_app` |
| 7.5 Web UI: HR dashboard, supervisor dashboard, monitoring dashboard, alert details & workflow, role-specific navigation | `frontend/src/features/{hr,supervision,monitoring,…}`; navigation from the server (`/auth/me`) | `e2e/smoke.cjs` (all roles, Persian and English) |

## 8. Required scenarios
| Scenario | Seeded alert | Proof |
|---|---|---|
| 1 Suspicious session activity | overlapping session records (15 pairs) | `test_scenario1_overlapping_sessions`, `test_flow1…` |
| 2 Abnormal referral network (and legitimate specialisation not alerted) | referral concentration + "suppressed: explained by policy" | `test_scenario2_referral_network_and_policy_suppression`, `test_flow2…` |
| 3 Unusual supervisor approvals | approval burst / missing documentation | `test_scenario3…`, `test_flow3…` |
| 4 Unauthorised administrative activity | denied-access burst, security alert | `test_scenario4_admin_out_of_scope`, `test_flow4…` |

## 9. Data requirements
Synthetic dataset (users/roles, profiles, supervisors and supervisees, sessions, referrals, approvals, administrative activities, access events, investigation records, professional development) with normal **and** anomalous cases, plus explanation of structure, assumptions, features, anomaly methodology, limitations and the path to real data: `backend/seed/generate.py`, [DATASET.md](DATASET.md); test `test_9_dataset_has_every_required_record_type`. No real personal, clinical or confidential data is used.

## 10. Deliverables
| Deliverable | Where |
|---|---|
| **A. Architecture & design** (system diagram, module/service architecture, ERD, role & permission matrix, API documentation, data-flow diagram, fraud-detection architecture, security & privacy design) | [ARCHITECTURE.md](ARCHITECTURE.md), [RBAC_MATRIX.md](RBAC_MATRIX.md), [openapi.yaml](openapi.yaml), `/api/docs/` |
| **B. Executable prototype** (HR, supervisor and monitoring panels, integrated engine, ≥ 4 scenarios, investigation workflow, synthetic data) | `backend/` + `frontend/`; [GUIDE.md](GUIDE.md) |
| **C. Source & engineering docs** (code, structure, README/installation, environment example, tests, API docs, database initialisation/migrations, assumptions & limitations) | repository; [README.md](../README.md); `backend/.env.example`; `backend/tests/`; migrations in `backend/*/migrations/`; [GUIDE.md](GUIDE.md); [TECHNICAL_REPORT.md](TECHNICAL_REPORT.md) |
| **D. Technical report** (decisions, technology, methodology, detection performance, limitations/false positives, security, scalability, costs, roadmap) | [TECHNICAL_REPORT.md](TECHNICAL_REPORT.md) |
| **E. Technical presentation** | [PRESENTATION.md](PRESENTATION.md) (Marp-compatible) |

Test `test_10_deliverables_exist` fails if a deliverable file disappears.
