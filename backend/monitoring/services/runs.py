"""Run the detection pipeline and persist its output: de-duplicated, recurrence-aware, idempotent."""
import math
import time
from datetime import UTC

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from core.audit import audit
from core.constants import AlertStatus
from detection.engine import analyse, load_config
from detection.types import ScoredAlert
from monitoring.loaders import load_data
from monitoring.models import Alert, AlertUser, DetectionRun, InvestigationEvent


def json_safe(x):
    """Make evidence valid JSON: datetimes -> ISO strings, numpy scalars -> Python, NaN/inf -> null."""
    if isinstance(x, dict):
        return {k: json_safe(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [json_safe(v) for v in x]
    if hasattr(x, "isoformat"):
        return x.isoformat(timespec="minutes")
    x = x.item() if hasattr(x, "item") and not isinstance(x, (str, bytes)) else x
    return None if isinstance(x, float) and not math.isfinite(x) else x


def aware(ts):
    return None if ts is None else ts.to_pydatetime().replace(tzinfo=UTC) if hasattr(ts, "to_pydatetime") else ts.replace(tzinfo=UTC)


def alert_fields(sa: ScoredAlert, run: DetectionRun, analysis) -> dict:
    f = sa.finding
    return dict(title=f.title, category=f.category, scenario=f.scenario, domain=f.domain, subject_user_id=f.subject_user_id, risk_score=sa.score, risk_level=sa.level,
                methods=sa.methods, explanation=sa.explanation, recommended_action=f.recommended_action, evidence=json_safe(f.evidence[:40]),
                score_breakdown=json_safe(sa.breakdown), record_refs=sorted(set(f.record_refs)), ruleset_version=analysis.ruleset_version,
                model_version=analysis.model_version, window_start=aware(f.window_start), window_end=aware(f.window_end), run=run, updated_at=timezone.now())


def upsert(sa: ScoredAlert, run: DetectionRun, analysis) -> str:
    """Returns 'created' | 'updated' | 'skipped'. An open alert is updated in place; a closed one is re-raised ONLY with new records."""
    f, fields = sa.finding, alert_fields(sa, run, analysis)
    history = list(Alert.objects.filter(dedup_key=f.dedup_key).order_by("-id"))
    open_alert = next((a for a in history if a.status in AlertStatus.open()), None)
    if open_alert:
        old = open_alert.risk_score
        for key, value in fields.items():
            setattr(open_alert, key, value)
        open_alert.save()
        if abs(old - sa.score) >= 5:
            InvestigationEvent.objects.create(alert=open_alert, action="rescored", note=f"Risk score updated {old:.0f} → {sa.score:.0f} by detection run #{run.id}")
        return "updated"
    if history and not set(f.record_refs) - {r for a in history for r in a.record_refs}:
        return "skipped"      # closed earlier and nothing new since: do not re-alert (false-positive management)
    alert = Alert.objects.create(alert_uid=f"tmp-{time.time_ns()}", dedup_key=f.dedup_key, status=AlertStatus.NEW, **fields)
    alert.alert_uid = f"ALR-{alert.id:06d}"
    alert.save(update_fields=["alert_uid"])
    users = {u: "related" for u in f.related_user_ids} | ({f.subject_user_id: "subject"} if f.subject_user_id is not None else {})
    AlertUser.objects.bulk_create([AlertUser(alert=alert, user_id=u, role_in_alert=r) for u, r in users.items()])
    recurrence = f" (recurrence; earlier alert {history[0].alert_uid} was {history[0].status})" if history else ""
    InvestigationEvent.objects.create(alert=alert, action="created", note=f"Alert created by detection run #{run.id}{recurrence}", to_status=AlertStatus.NEW)
    return "created"


@transaction.atomic
def run_detection(triggered_by: int | None = None) -> dict:
    started = time.time()
    cfg, cfg_hash = load_config(settings.DETECTION_CONFIG)
    data = load_data()
    analysis = analyse(data, cfg)
    run = DetectionRun.objects.create(triggered_by=triggered_by, ruleset_version=analysis.ruleset_version, model_version=analysis.model_version, config_hash=cfg_hash, as_of=aware(data.as_of))
    counts = {"created": 0, "updated": 0, "skipped": analysis.skipped}
    for sa in analysis.alerts:
        counts[upsert(sa, run, analysis)] += 1
    run.finished_at = timezone.now()
    run.stats = {"alerts_created": counts["created"], "alerts_updated": counts["updated"], "findings_below_threshold_or_duplicate": counts["skipped"],
                 "findings_total": len(analysis.alerts) + analysis.skipped, "suppressed": json_safe(analysis.suppressed), "seconds": round(time.time() - started, 2), "as_of": data.as_of.isoformat()}
    run.save()
    audit(triggered_by, "detection_run", "detection_run", run.id, created=counts["created"], updated=counts["updated"], ruleset=analysis.ruleset_version, model=analysis.model_version)
    return {"run_id": run.id, **run.stats, "ruleset_version": analysis.ruleset_version, "model_version": analysis.model_version}
