"""Effective-dating queries – the ONLY place that knows what "current assignment" means (DRY)."""
from datetime import date

from django.db.models import Q

from hr.models import SupervisionAssignment


def current_assignments(on: date | None = None):
    on = on or date.today()
    return SupervisionAssignment.objects.filter(Q(effective_to__isnull=True) | Q(effective_to__gte=on), effective_from__lte=on)


def current_supervisee_ids(supervisor_id: int, on=None) -> set[int]:
    return set(current_assignments(on).filter(supervisor_id=supervisor_id).values_list("supervisee_id", flat=True))


def current_supervisor_id(supervisee_id: int, on=None) -> int | None:
    return current_assignments(on).filter(supervisee_id=supervisee_id).order_by("-effective_from").values_list("supervisor_id", flat=True).first()
