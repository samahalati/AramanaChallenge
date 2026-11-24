"""Detection pipeline: detectors (Strategy) → merge corroborating findings → score (noisy-OR) → explain.

Pure functions over DataFrames: no database, no web framework. Persistence lives in `monitoring.services.runs`.
There is deliberately NO code path from here to any user/contract/credential change (human-in-the-loop).
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import yaml

from detection import detectors  # noqa: F401  (registers all detectors)
from detection.base import REGISTRY, Context
from detection.data import Cfg, Data
from detection.detectors.peer import model_version
from detection.explain import build_explanation
from detection.scoring import attribute, level_for
from detection.types import Analysis, Finding, ScoredAlert

CANCEL_KEYS = {"peer_outlier_cancel_rate", "peer_outlier_heavy_mod_rate", "peer_outlier_noshow_rate"}


def load_config(path: str) -> tuple[Cfg, str]:
    text = Path(path).read_text()
    return Cfg(yaml.safe_load(text)), hashlib.sha256(text.encode()).hexdigest()


def merge(primary: list[Finding], behavioral: list[Finding]) -> list[Finding]:
    """Behavioural evidence is attached to a matching primary finding; otherwise it becomes one standalone (Low-capped) alert."""
    standalone: dict[tuple, Finding] = {}
    for b in behavioral:
        match = [p for p in primary if (p.category, p.subject_user_id) == (b.category, b.subject_user_id)]
        target = max(match, key=lambda p: sum(i.contribution for i in p.indicators)) if match else standalone.setdefault((b.category, b.subject_user_id), b)
        if target is not b:
            target.indicators, target.evidence = target.indicators + b.indicators, target.evidence + b.evidence
    for f in standalone.values():
        if any(i.name in CANCEL_KEYS for i in f.indicators):
            f.scenario, f.title = "cancellation_pattern", f.title.replace("Behavioural outlier vs peers", "Cancellation/modification pattern").replace("Unsupervised behavioural anomaly", "Cancellation/modification pattern")
    return primary + list(standalone.values())


def score(f: Finding, data: Data, cfg: Cfg) -> ScoredAlert:
    risk = cfg.risk
    value, breakdown, capped = attribute(f.indicators, risk["max_indicator_contribution"], set(risk.get("weak_indicators", [])), risk.get("weak_only_cap"))
    level = level_for(value, risk["levels"])
    text = build_explanation(f.scenario, data.label(f.subject_user_id), value, level, breakdown)
    text += "\n\nNote: only weak evidence (volume / unexplained model score) supports this alert, so its score is capped at Low." if capped else ""
    return ScoredAlert(f, value, level, breakdown, text, sorted({i.method for i in f.indicators}), capped)


def analyse(data: Data, cfg: Cfg) -> Analysis:
    ctx, primary, behavioral = Context(data, cfg), [], []
    for cls in REGISTRY:
        detector = cls(ctx)
        (behavioral if detector.kind == "behavioral" else primary).extend(detector.detect())
    findings = merge(primary, behavioral)
    scored = [score(f, data, cfg) for f in findings]
    keep = [a for a in scored if a.score >= cfg.risk["min_alert_score"]]
    return Analysis(keep, ctx.suppressed, len(scored) - len(keep), cfg.raw["ruleset_version"], model_version(cfg))
