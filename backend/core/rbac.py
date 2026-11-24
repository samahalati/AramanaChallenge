"""Single source of truth for authorisation: role -> permission matrix (+ alert-domain visibility).
Relationship scoping (own / current supervisee / alerted subject) lives next to the data it scopes
(`hr.selectors`, `clinical.access`, `monitoring.visibility`) and builds on these tables.
Administrative roles hold NO clinical permission (separation of duties)."""
from core.constants import Domain, Role as R

D = Domain
ROLE_PERMISSIONS: dict[str, set[str]] = {
    R.PLATFORM_ADMIN: {"users:read", "users:manage", "audit:read", "alerts:read", "alerts:investigate", "alerts:comment", "detection:run", "detection:read"},
    R.HR_ADMIN: {"users:read", "hr:read", "hr:write", "alerts:read", "alerts:comment", "detection:read"},
    R.CLINICAL_SUPERVISOR: {"users:read", "supervision:read", "supervision:write", "clinical:read:supervisees", "quality:write", "alerts:read", "alerts:comment"},
    R.THERAPIST: {"clinical:read:own", "clinical:write:own", "supervision:read:own"},
    R.ASSISTANT_COUNSELOR: {"referrals:read:own", "referrals:write:own"},
    R.COMPLIANCE_REVIEWER: {"users:read", "hr:read", "alerts:read", "alerts:investigate", "alerts:comment", "clinical:read:alerted", "audit:read", "detection:run", "detection:read"},
}
ALERT_DOMAIN_VISIBILITY = {
    R.PLATFORM_ADMIN: {D.SECURITY}, R.HR_ADMIN: {D.OPERATIONAL, D.MISCONDUCT}, R.CLINICAL_SUPERVISOR: {D.OPERATIONAL, D.CLINICAL},
    R.COMPLIANCE_REVIEWER: set(D.values),
}
INVESTIGATE_DOMAINS = {R.PLATFORM_ADMIN: {D.SECURITY}, R.COMPLIANCE_REVIEWER: set(D.values)}
ROLE_NAV = {
    R.PLATFORM_ADMIN: ["admin", "monitoring", "audit"], R.HR_ADMIN: ["hr", "monitoring"], R.CLINICAL_SUPERVISOR: ["supervision", "monitoring"],
    R.THERAPIST: ["mywork"], R.ASSISTANT_COUNSELOR: ["mywork"], R.COMPLIANCE_REVIEWER: ["monitoring", "hr", "audit"],
}


def has_perm(role: str, perm: str) -> bool:
    return perm in ROLE_PERMISSIONS.get(role, ())


def can_see_client_refs(role: str) -> bool:
    return has_perm(role, "clinical:read:alerted") or has_perm(role, "clinical:read:supervisees")
