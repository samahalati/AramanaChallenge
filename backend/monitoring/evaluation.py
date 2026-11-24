"""Evaluation against synthetic ground truth. Unit = (user, category). Positive = alert at/above `min_level`. Ablation by detection layer."""
import json
from pathlib import Path

from django.conf import settings

from core.constants import RISK_LEVELS
from monitoring.models import Alert

RANK = {lv: i for i, lv in enumerate(RISK_LEVELS)}
LAYERS = {"rules_only": {"rule"}, "statistics_only": {"statistical"}, "ml_only": {"ml"}, "graph_only": {"graph"}, "rules+statistics": {"rule", "statistical"}, "full_ensemble": None}


def alert_pairs(a: Alert) -> set[tuple[int, str]]:
    """Subject only; for network (E) or subject-less alerts every listed user counts (the alert is about the group)."""
    if a.category == "E" or a.subject_user_id is None:
        return {(u, a.category) for u in a.users.values_list("user_id", flat=True)}
    return {(a.subject_user_id, a.category)}


def predicted(min_level: str, layers: set | None = None) -> set:
    floor = 35 if min_level == "medium" else 60
    out = set()
    for a in Alert.objects.prefetch_related("users"):
        if RANK[a.risk_level] >= RANK[min_level] and (layers is None or sum(b["points"] for b in a.score_breakdown if b["method"] in layers) >= floor):
            out |= alert_pairs(a)
    return out


def prf(pred: set, truth: set) -> dict:
    tp = len(pred & truth)
    p, r = tp / len(pred) if pred else 0.0, tp / len(truth) if truth else 0.0
    return {"tp": tp, "fp": len(pred - truth), "fn": len(truth - pred), "precision": round(p, 3), "recall": round(r, 3), "f1": round(2 * p * r / (p + r), 3) if p + r else 0.0}


def evaluate(min_level: str = "medium") -> dict:
    gt = json.loads(Path(settings.GROUND_TRUTH_PATH).read_text())
    truth = {(u, a["category"]) for a in gt["anomalies"] for u in a["users"]}
    hard = {u for h in gt["hard_negatives"] for u in h["users"]}
    pred = predicted(min_level)
    any_level = {}
    for a in Alert.objects.prefetch_related("users"):
        for uid, _ in alert_pairs(a):
            if uid in hard:
                any_level.setdefault(uid, []).append({"alert": a.alert_uid, "level": a.risk_level, "score": a.risk_score, "scenario": a.scenario})
    fp = sorted((u, c) for u, c in pred if u in hard and (u, c) not in truth)
    return {"min_level": min_level, "seed": gt["seed"], "alerts_total": Alert.objects.count(), "overall": prf(pred, truth),
            "per_category": {c: prf({p for p in pred if p[1] == c}, {t for t in truth if t[1] == c}) for c in sorted({c for _, c in truth})},
            "per_scenario": {a["scenario"]: {"category": a["category"], "detected": sum((u, a["category"]) in pred for u in a["users"]), "of": len(a["users"])} for a in gt["anomalies"]},
            "hard_negatives": {"n": len(hard), "false_positives_at_min_level": len(fp), "pairs": fp, "alerts_any_level": any_level},
            "ablation": {name: prf(predicted(min_level, layers), truth) for name, layers in LAYERS.items()}}


def format_report(r: dict) -> str:
    o, h = r["overall"], r["hard_negatives"]
    lines = [f"Detection evaluation  (min level = {r['min_level']}, seed = {r['seed']}, alerts = {r['alerts_total']})", "",
             f"OVERALL  precision={o['precision']}  recall={o['recall']}  F1={o['f1']}  (tp={o['tp']} fp={o['fp']} fn={o['fn']})", "", "Per category"]
    lines += [f"  {c}  P={m['precision']} R={m['recall']} F1={m['f1']}  tp={m['tp']} fp={m['fp']} fn={m['fn']}" for c, m in r["per_category"].items()]
    lines += ["", "Per injected scenario (detected / injected users)"] + [f"  {s:<28} {m['detected']}/{m['of']}" for s, m in r["per_scenario"].items()]
    lines += ["", f"Hard negatives: {h['false_positives_at_min_level']} false positives at >= {r['min_level']} among {h['n']} legit-but-unusual users"]
    lines += [f"    user {u}: {a['alert']} {a['level']} ({a['score']}) {a['scenario']}" for u, al in h["alerts_any_level"].items() for a in al]
    return "\n".join(lines + ["", "Ablation (layers used for scoring)"] + [f"  {n:<20} P={m['precision']} R={m['recall']} F1={m['f1']}" for n, m in r["ablation"].items()])
