"""Configuration + the data the detectors read (DataFrames) + small shared helpers."""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from detection.types import Indicator


@dataclass
class Cfg:
    raw: dict

    t = property(lambda s: s.raw["thresholds"])
    w = property(lambda s: s.raw["weights"])
    windows = property(lambda s: s.raw["windows"])
    risk = property(lambda s: s.raw["risk"])
    seed = property(lambda s: int(s.raw.get("random_seed", 42)))

    def ind(self, name: str, label: str, value, threshold, strength: float, method: str = "rule", note: str = "",
            weight_key: str | None = None) -> Indicator:
        """Indicator factory: the weight always comes from the versioned config (never hard-coded in a detector)."""
        return Indicator(name, label, value, threshold, self.w[weight_key or name], clip01(strength), method, note)


@dataclass
class Data:
    users: pd.DataFrame
    profiles: pd.DataFrame
    sessions: pd.DataFrame
    referrals: pd.DataFrame
    reviews: pd.DataFrame
    access: pd.DataFrame
    admin: pd.DataFrame
    as_of: pd.Timestamp
    names: dict = field(default_factory=dict)
    roles: dict = field(default_factory=dict)

    def since(self, days: float) -> pd.Timestamp:
        return self.as_of - pd.Timedelta(days=days)

    def label(self, uid: int | None) -> str:
        return "multiple accounts" if uid is None else f"{self.names.get(uid, 'user')} (#{uid}, {self.roles.get(uid, '?')})"


def bursts(df: pd.DataFrame, key: str, window_min: float, min_count: int, distinct: str | None = None, ts: str = "ts"):
    """Sliding-window peak per group (two pointers). Yields (group, peak, rows_in_peak_window) when peak >= min_count.
    `distinct` counts distinct values of that column instead of rows. One helper serves every burst-style rule (DRY)."""
    width = pd.Timedelta(minutes=window_min)
    for k, g in df.groupby(key):
        g = g.sort_values(ts).reset_index(drop=True)
        best, lo, left = (0, 0, 0), 0, 0
        for i in range(len(g)):
            while g[ts][i] - g[ts][left] > width:
                left += 1
            n = g.iloc[left:i + 1][distinct].nunique() if distinct else i - left + 1
            if n > best[0]:
                best = (n, left, i)
        if best[0] >= min_count:
            yield k, best[0], g.iloc[best[1]:best[2] + 1]


def clip01(x: float) -> float:
    return float(min(1.0, max(0.0, x)))
