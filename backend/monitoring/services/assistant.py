"""Guarded LLM investigation assistant – the Django side (permissions, visibility, rate limit, persistence, audit).
The conversation logic and ALL guardrails live in `detection.assistant` (pure Python); this module only wires it to the platform.
The assistant is advisory: nothing here changes an alert's status, score, or any person's record."""
from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, Throttled

from accounts.selectors import briefs
from core import i18n
from core.audit import audit
from core.rbac import INVESTIGATE_DOMAINS, has_perm
from detection import assistant
from monitoring import localize
from monitoring.models import Alert, AssistantExchange, InvestigationEvent
from monitoring.services.alerts import get_visible

RATE_LIMIT_PER_HOUR = 30
TRANSPORT = None   # test hook: inject an httpx.MockTransport to script the model

ADVISORY = "AI output is advisory and may be wrong. Every statement must be checked against the cited evidence; decisions are made by authorised humans."


def _guard(user, alert_id: int) -> tuple[Alert, set[str]]:
    alert, users = get_visible(user, alert_id)
    if not has_perm(user.role, "alerts:investigate") or alert.domain not in INVESTIGATE_DOMAINS.get(user.role, ()):
        raise PermissionDenied("Only reviewers authorised to investigate this alert may use the AI assistant")
    recent = AssistantExchange.objects.filter(actor_id=user.id, ts__gte=timezone.now() - timedelta(hours=1)).count()
    if recent >= RATE_LIMIT_PER_HOUR:
        raise Throttled(detail=f"AI assistant limit reached ({RATE_LIMIT_PER_HOUR} requests per hour)")
    names = {b["name"] for b in briefs(set(users) | ({alert.subject_user_id} - {None})).values()}
    return alert, names | {n.split()[0] for n in names if len(n.split()[0]) > 3}   # also guard against first-name-only leaks


def _alert_input(a: Alert) -> dict:
    farsi = i18n.lang() == "fa"        # Persian pack: localised indicator rows and action; evidence keys/values are translated inside build_pack
    return {"category": a.category, "scenario": a.scenario, "domain": a.domain, "risk_score": a.risk_score, "risk_level": a.risk_level, "methods": a.methods,
            "subject_user_id": a.subject_user_id, "score_breakdown": localize.breakdown(a) if farsi else a.score_breakdown, "evidence": a.evidence,
            "window_start": a.window_start, "window_end": a.window_end,
            "recommended_action": localize.det.tr_text(a.recommended_action) if farsi else a.recommended_action}


def _run(fn, alert: Alert, *args, names: set[str]):
    lang = i18n.lang()
    return fn(_alert_input(alert), *args, settings.LLM, names, TRANSPORT, lang, i18n.TERMS if lang == "fa" else None)


def _store(user, alert: Alert, r: dict) -> dict:
    ex = AssistantExchange.objects.create(alert=alert, actor_id=user.id, kind=r["kind"], question=r["question"], provider=r["provider"], refused=r["refused"],
                                          content=r["content"], citations=r["citations"], guardrails=r["guardrails"])
    out, passed = r["guardrails"]["output"], sum(v == "pass" for v in r["guardrails"]["output"]["checks"].values())
    note = ("AI question refused by input guardrail" if r["refused"] else
            f"AI {r['kind']} via {r['provider']}; output guardrails {passed}/{len(out['checks'])} passed; attempts={out['attempts']}; fallback={out['fallback_used']}")
    InvestigationEvent.objects.create(alert=alert, actor_id=user.id, action="ai_assistant", note=note)
    audit(user, f"alert_ai_{r['kind']}", "alert", alert.alert_uid, provider=r["provider"], refused=r["refused"], attempts=out["attempts"], fallback=out["fallback_used"],
          redacted=r["guardrails"]["input"]["redacted"], question_chars=len(r["question"] or ""))
    return view(ex)


def view(ex: AssistantExchange) -> dict:
    return {"id": ex.id, "kind": ex.kind, "question": ex.question, "provider": ex.provider, "refused": ex.refused, "content": ex.content, "citations": ex.citations,
            "guardrails": ex.guardrails, "created_at": ex.ts, "advisory": i18n.t(ADVISORY)}


def brief(user, alert_id: int) -> dict:
    alert, names = _guard(user, alert_id)
    return _store(user, alert, _run(assistant.brief, alert, names=names))


def ask(user, alert_id: int, question: str) -> dict:
    alert, names = _guard(user, alert_id)
    return _store(user, alert, _run(assistant.ask, alert, question, names=names))


def history(user, alert_id: int) -> list[dict]:
    alert, _ = get_visible(user, alert_id)
    if not has_perm(user.role, "alerts:investigate"):
        raise PermissionDenied("Only investigating reviewers may see the AI assistant history")
    return [view(e) for e in alert.assistant_exchanges.order_by("-id")[:20]]
