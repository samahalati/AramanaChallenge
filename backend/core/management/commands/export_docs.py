from pathlib import Path

from django.core.management import call_command
from django.core.management.base import BaseCommand

from core import constants as C
from core.rbac import ALERT_DOMAIN_VISIBILITY, INVESTIGATE_DOMAINS, ROLE_PERMISSIONS

DOCS = Path(__file__).resolve().parents[4] / "docs"


class Command(BaseCommand):
    help = "Generate docs/RBAC_MATRIX.md (from core/rbac.py) and docs/openapi.yaml (from the DRF schema) so documentation cannot drift from code."

    def handle(self, *args, **o):
        roles, perms = C.Role.values, sorted({p for s in ROLE_PERMISSIONS.values() for p in s})
        lines = ["# Role & permission matrix (generated from `backend/core/rbac.py` – run `python manage.py export_docs`)", "",
                 "| Permission | " + " | ".join(roles) + " |", "|---|" + "---|" * len(roles)]
        lines += [f"| `{p}` | " + " | ".join("✔" if p in ROLE_PERMISSIONS[r] else "" for r in roles) + " |" for p in perms]
        lines += ["", "## Alert visibility and investigation rights by domain", "", "| Role | Sees alert domains | May investigate |", "|---|---|---|"]
        lines += [f"| {r} | {', '.join(sorted(ALERT_DOMAIN_VISIBILITY.get(r, []))) or '–'} | {', '.join(sorted(INVESTIGATE_DOMAINS.get(r, []))) or '–'} |" for r in roles]
        lines += ["", "## Relationship scoping (ABAC) applied on top of the matrix", "",
                  "- **Clinical records** (`monitoring/visibility.py`): `clinical:read:own` → only own; `clinical:read:supervisees` → only *current* (effective-dated) supervisees; `clinical:read:alerted` → only users named in an alert.",
                  "- **Alerts**: never visible to a user who is the subject/related user of that alert (conflict of interest); supervisors only see operational/clinical alerts about their current supervisees.",
                  "- **Client references** are redacted (`C-****`) for roles without clinical access.", "- **Reviews**: a supervisor can only open/decide reviews they own for current supervisees.",
                  "- **Self-service limits**: administrators cannot change their own role/status.", "", "## Role descriptions", ""]
        lines += [f"- **{r}** – {C.ROLE_DESCRIPTIONS[r]}" for r in roles]
        (DOCS / "RBAC_MATRIX.md").write_text("\n".join(lines) + "\n")
        call_command("spectacular", file=str(DOCS / "openapi.yaml"), verbosity=0)
        self.stdout.write("docs/RBAC_MATRIX.md and docs/openapi.yaml written")
