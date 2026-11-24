"""Shared vocabulary (TextChoices: usable in models, serializers and plain code)."""
from django.db import models


class Role(models.TextChoices):
    PLATFORM_ADMIN = "platform_admin"
    HR_ADMIN = "hr_admin"
    CLINICAL_SUPERVISOR = "clinical_supervisor"
    THERAPIST = "therapist"
    ASSISTANT_COUNSELOR = "assistant_counselor"
    COMPLIANCE_REVIEWER = "compliance_reviewer"


class UserStatus(models.TextChoices):
    ACTIVE = "active"
    PENDING = "pending_onboarding"
    SUSPENDED = "suspended"
    TERMINATED = "terminated"


class Domain(models.TextChoices):
    """Brief §4.4: operational alerts, clinical concerns and potential misconduct are distinct (+ security)."""
    OPERATIONAL = "operational"
    CLINICAL = "clinical"
    MISCONDUCT = "misconduct"
    SECURITY = "security"


class AlertStatus(models.TextChoices):
    NEW = "new"
    UNDER_REVIEW = "under_review"
    INFO_REQUESTED = "info_requested"
    ESCALATED = "escalated"
    FALSE_POSITIVE = "false_positive"
    CLOSED_SUBSTANTIATED = "closed_substantiated"
    CLOSED_NO_ACTION = "closed_no_action"

    @classmethod
    def open(cls):
        return [cls.NEW, cls.UNDER_REVIEW, cls.INFO_REQUESTED, cls.ESCALATED]

    @classmethod
    def closed(cls):
        return [cls.FALSE_POSITIVE, cls.CLOSED_SUBSTANTIATED, cls.CLOSED_NO_ACTION]


RISK_LEVELS = ["low", "medium", "high", "critical"]
SPECIALIZATIONS = ["trauma", "anxiety", "depression", "couples", "child", "addiction"]
CATEGORY_LABELS = {"A": "Therapist-related", "B": "Assistant-counselor-related", "C": "Supervisor-related",
                   "D": "Administrative / platform-related", "E": "Cross-user / network", "Q": "Supervisor escalation"}
ROLE_DESCRIPTIONS = {
    Role.PLATFORM_ADMIN: "Manages accounts, roles and platform configuration. No access to HR record content or clinical data.",
    Role.HR_ADMIN: "Manages professional profiles, credentials, contracts, lifecycle and org structure. No clinical data.",
    Role.CLINICAL_SUPERVISOR: "Supervises assigned practitioners: reviews, feedback, corrective actions, escalation.",
    Role.THERAPIST: "Delivers sessions; sees own sessions, own reviews and own corrective actions.",
    Role.ASSISTANT_COUNSELOR: "Creates referrals; sees own referrals only.",
    Role.COMPLIANCE_REVIEWER: "Investigates alerts across domains; read-only evidence access scoped to alerted subjects.",
}
