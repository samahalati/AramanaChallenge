"""Strategy pattern + registry (Open/Closed): a detector is one small class; the engine discovers all registered
detectors, so adding a detector never touches the engine, scoring or persistence code.

    @register
    class MyDetector(Detector):
        category, domain, scenario = THERAPIST, OPERATIONAL, "my_scenario"
        def detect(self): ... return [self.finding(subject, indicators, evidence, refs, title=..., action=...)]
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Callable

from detection.data import Cfg, Data
from detection.types import Finding, Indicator

REGISTRY: list[type["Detector"]] = []


def register(cls):
    REGISTRY.append(cls)
    return cls


@dataclass
class Context:
    """What every detector receives: data, config, a memo for shared expensive computations, and a 'suppressed' log."""
    data: Data
    cfg: Cfg
    suppressed: list[dict] = field(default_factory=list)
    _memo: dict = field(default_factory=dict)

    def memo(self, key: str, compute: Callable):
        if key not in self._memo:
            self._memo[key] = compute()
        return self._memo[key]


class Detector(ABC):
    kind = "primary"          # "primary": stands alone | "behavioral": corroborates (or raises a Low alert on its own)
    category = scenario = domain = ""

    def __init__(self, ctx: Context):
        self.ctx, self.d, self.cfg, self.t = ctx, ctx.data, ctx.cfg, ctx.cfg.t

    @abstractmethod
    def detect(self) -> list[Finding]: ...

    def finding(self, subject: int | None, indicators: list[Indicator], evidence: list[dict], refs: list[str], *, title: str, action: str,
                related: list[int] | None = None, window_days: float | None = None, **over) -> Finding:
        w = self.cfg.windows
        days = window_days or w["lookback_days"]
        return Finding(**{"category": self.category, "scenario": self.scenario, "domain": self.domain, "title": title, "subject_user_id": subject,
                          "related_user_ids": related or [], "indicators": indicators, "evidence": evidence, "record_refs": refs,
                          "recommended_action": action, "window_start": self.d.since(days), "window_end": self.d.as_of, **over})
