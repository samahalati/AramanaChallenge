# Role & permission matrix (generated from `backend/core/rbac.py` – run `python manage.py export_docs`)

| Permission | platform_admin | hr_admin | clinical_supervisor | therapist | assistant_counselor | compliance_reviewer |
|---|---|---|---|---|---|---|
| `alerts:comment` | ✔ | ✔ | ✔ |  |  | ✔ |
| `alerts:investigate` | ✔ |  |  |  |  | ✔ |
| `alerts:read` | ✔ | ✔ | ✔ |  |  | ✔ |
| `audit:read` | ✔ |  |  |  |  | ✔ |
| `clinical:read:alerted` |  |  |  |  |  | ✔ |
| `clinical:read:own` |  |  |  | ✔ |  |  |
| `clinical:read:supervisees` |  |  | ✔ |  |  |  |
| `clinical:write:own` |  |  |  | ✔ |  |  |
| `detection:read` | ✔ | ✔ |  |  |  | ✔ |
| `detection:run` | ✔ |  |  |  |  | ✔ |
| `hr:read` |  | ✔ |  |  |  | ✔ |
| `hr:write` |  | ✔ |  |  |  |  |
| `quality:write` |  |  | ✔ |  |  |  |
| `referrals:read:own` |  |  |  |  | ✔ |  |
| `referrals:write:own` |  |  |  |  | ✔ |  |
| `supervision:read` |  |  | ✔ |  |  |  |
| `supervision:read:own` |  |  |  | ✔ |  |  |
| `supervision:write` |  |  | ✔ |  |  |  |
| `users:manage` | ✔ |  |  |  |  |  |
| `users:read` | ✔ | ✔ | ✔ |  |  | ✔ |

## Alert visibility and investigation rights by domain

| Role | Sees alert domains | May investigate |
|---|---|---|
| platform_admin | security | security |
| hr_admin | misconduct, operational | – |
| clinical_supervisor | clinical, operational | – |
| therapist | – | – |
| assistant_counselor | – | – |
| compliance_reviewer | clinical, misconduct, operational, security | clinical, misconduct, operational, security |

## Relationship scoping (ABAC) applied on top of the matrix

- **Clinical records** (`monitoring/visibility.py`): `clinical:read:own` → only own; `clinical:read:supervisees` → only *current* (effective-dated) supervisees; `clinical:read:alerted` → only users named in an alert.
- **Alerts**: never visible to a user who is the subject/related user of that alert (conflict of interest); supervisors only see operational/clinical alerts about their current supervisees.
- **Client references** are redacted (`C-****`) for roles without clinical access.
- **Reviews**: a supervisor can only open/decide reviews they own for current supervisees.
- **Self-service limits**: administrators cannot change their own role/status.

## Role descriptions

- **platform_admin** – Manages accounts, roles and platform configuration. No access to HR record content or clinical data.
- **hr_admin** – Manages professional profiles, credentials, contracts, lifecycle and org structure. No clinical data.
- **clinical_supervisor** – Supervises assigned practitioners: reviews, feedback, corrective actions, escalation.
- **therapist** – Delivers sessions; sees own sessions, own reviews and own corrective actions.
- **assistant_counselor** – Creates referrals; sees own referrals only.
- **compliance_reviewer** – Investigates alerts across domains; read-only evidence access scoped to alerted subjects.
