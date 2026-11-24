"""Explainable, configurable risk scoring.

score = 100 · (1 − Π (1 − cᵢ)),  cᵢ = weightᵢ × strengthᵢ    (noisy-OR)

Independent weak signals corroborate each other, one strong rule can dominate, the score stays in [0, 100], and it decomposes
EXACTLY into per-indicator points – every point is traceable. Corroboration rule: if every indicator is weak (ML score,
workload volume) the score is capped, so volume or an opaque model score alone never looks like a serious finding.
"""
from detection.types import Indicator


def attribute(indicators: list[Indicator], max_c: float = 0.97, weak: set[str] = frozenset(), weak_cap: float | None = None):
    """Return (score, breakdown, capped); breakdown points sum to the uncapped score."""
    remaining, rows = 1.0, []
    for ind in sorted(indicators, key=lambda i: i.contribution, reverse=True):
        c = min(ind.contribution, max_c)
        rows.append({**ind.to_dict(), "contribution": round(c, 4), "points": round(100 * remaining * c, 2)})
        remaining *= 1 - c
    score = round(100 * (1 - remaining), 1)
    capped = weak_cap is not None and bool(indicators) and all(i.name in weak for i in indicators) and score > weak_cap
    return (weak_cap if capped else score), rows, capped


def level_for(score: float, levels: dict[str, float]) -> str:
    return max((name for name, floor in levels.items() if score >= floor), key=lambda n: levels[n], default="low")
