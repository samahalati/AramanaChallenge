"""Observer pattern: supervision announces escalations; monitoring subscribes. Supervision never imports monitoring,
so the dependency points one way (monitoring -> supervision) and neither module needs to know the other's internals."""
from django.dispatch import Signal

issue_escalated = Signal()   # kwargs: issue, supervisor, reason ; receiver returns the created alert
