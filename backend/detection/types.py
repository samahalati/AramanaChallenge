"""Plain data structures shared by every detector (no framework imports: this package is pure Python)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

# alert categories (brief §5.1) and domains (brief §4.4)
THERAPIST, COUNSELOR, SUPERVISOR, ADMIN, NETWORK = "A", "B", "C", "D", "E"
OPERATIONAL, CLINICAL, MISCONDUCT, SECURITY = "operational", "clinical", "misconduct", "security"


def jsonable(v: Any) -> Any:
    if hasattr(v, "item"):
        v = v.item()
    if isinstance(v, float):
        return round(v, 4)
    return v.isoformat(timespec="minutes") if isinstance(v, datetime) else v


@dataclass
class Indicator:
    """One explainable signal: contribution = weight × strength (both in [0, 1])."""
    name: str
    label: str
    value: Any
    threshold: Any
    weight: float
    strength: float
    method: str            # rule | statistical | ml | graph | manual
    note: str = ""

    @property
    def contribution(self) -> float:
        return max(0.0, min(1.0, self.weight * self.strength))

    def to_dict(self) -> dict:
        return {"name": self.name, "label": self.label, "value": jsonable(self.value), "threshold": jsonable(self.threshold),
                "weight": round(self.weight, 3), "strength": round(self.strength, 3), "method": self.method, "note": self.note}


@dataclass
class Finding:
    category: str
    scenario: str
    domain: str
    title: str
    subject_user_id: int | None
    related_user_ids: list[int] = field(default_factory=list)
    indicators: list[Indicator] = field(default_factory=list)
    evidence: list[dict] = field(default_factory=list)
    record_refs: list[str] = field(default_factory=list)
    recommended_action: str = ""
    window_start: datetime | None = None
    window_end: datetime | None = None
    key_suffix: str = ""

    @property
    def dedup_key(self) -> str:
        return f"{self.category}:{self.scenario}:{self.subject_user_id or 'n/a'}:{self.key_suffix}".rstrip(":")


@dataclass
class ScoredAlert:
    finding: Finding
    score: float
    level: str
    breakdown: list[dict]
    explanation: str
    methods: list[str]
    capped: bool = False


@dataclass
class Analysis:
    alerts: list[ScoredAlert]
    suppressed: list[dict]
    skipped: int
    ruleset_version: str
    model_version: str
