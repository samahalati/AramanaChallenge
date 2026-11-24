"""Feature engineering: overlap detection, duration verification, weekly behavioural vectors."""
from __future__ import annotations

import numpy as np
import pandas as pd

from detection.data import Cfg, Data


def week_floor(ts: pd.Series) -> pd.Series:
    return ts.dt.normalize() - pd.to_timedelta(ts.dt.day_of_week, unit="D")


def mismatch_mask(s: pd.DataFrame, slack_min: float, slack_ratio: float) -> pd.Series:
    """Completed sessions whose reported duration is not supported by check-in/out (or that have no check-in)."""
    span = (s["checkout_at"] - s["checkin_at"]).dt.total_seconds() / 60
    rep = s["reported_duration_min"].fillna(0)
    inflated = ((rep - span) > np.maximum(slack_min, slack_ratio * rep)).fillna(False)
    return (s["status"] == "completed") & (s["checkin_at"].isna() | inflated)


def find_overlaps(sessions: pd.DataFrame, tol_min: float) -> list[dict]:
    """Interval sweep per practitioner. Cancelled/no-show ignored; sessions sharing a group_id never conflict."""
    s = sessions[sessions.status.isin(["scheduled", "completed"])]
    s = s.astype(object).where(s.notna(), None)  # missing -> None (NaN is not valid JSON)
    tol, out = pd.Timedelta(minutes=tol_min), []
    for prac, g in s.groupby("practitioner_id"):
        rows = g.sort_values("scheduled_start").to_dict("records")
        for i, a in enumerate(rows):
            for b in rows[i + 1:]:
                if b["scheduled_start"] >= a["scheduled_end"] - tol:
                    break                                    # sorted by start: nothing later can overlap `a`
                if a["group_id"] and a["group_id"] == b["group_id"]:
                    continue
                ov = (min(a["scheduled_end"], b["scheduled_end"]) - b["scheduled_start"]).total_seconds() / 60
                if ov > tol_min:
                    out.append({"practitioner_id": int(prac), "session_a": int(a["id"]), "session_b": int(b["id"]), "a_start": a["scheduled_start"],
                                "a_end": a["scheduled_end"], "b_start": b["scheduled_start"], "b_end": b["scheduled_end"], "overlap_min": round(ov),
                                "a_loc": a["location_code"], "b_loc": b["location_code"], "a_mode": a["mode"], "b_mode": b["mode"],
                                "a_status": a["status"], "b_status": b["status"], "client_a": a["client_ref"], "client_b": b["client_ref"],
                                "impossible": a["mode"] == "in_person" and b["mode"] == "in_person" and a["location_code"] != b["location_code"]})
    return out


def therapist_weekly(d: Data, cfg: Cfg) -> pd.DataFrame:
    s = d.sessions[d.sessions.status != "scheduled"].copy()
    s["unit"] = s["group_id"].fillna(s["id"].astype(str))
    s = s.drop_duplicates(["practitioner_id", "unit"])     # a group session counts once
    s["week"] = week_floor(s["scheduled_start"])
    s["cancel_rate"], s["noshow_rate"] = (s.status == "cancelled") * 1.0, (s.status == "no_show") * 1.0
    s["heavy_mod_rate"] = (s.modification_count >= 2) * 1.0
    s["mismatch_rate"] = mismatch_mask(s, cfg.t["duration_slack_min"], cfg.t["duration_slack_ratio"]) * 1.0
    g = s.groupby(["practitioner_id", "week"]).agg(n=("id", "size"), cancel_rate=("cancel_rate", "mean"), noshow_rate=("noshow_rate", "mean"),
                                                   heavy_mod_rate=("heavy_mod_rate", "mean"), mismatch_rate=("mismatch_rate", "mean")).reset_index()
    cap = d.profiles.set_index("user_id")["capacity_weekly_sessions"]
    g["load"] = g.n / g.practitioner_id.map(cap).fillna(25).clip(lower=1)
    ov = pd.DataFrame(find_overlaps(d.sessions, cfg.t["overlap_tolerance_min"]), columns=["practitioner_id", "a_start"])
    ov["week"] = week_floor(pd.to_datetime(ov["a_start"]))
    counts = ov.groupby(["practitioner_id", "week"]).size().rename("overlap_pairs").reset_index()
    return g.merge(counts, on=["practitioner_id", "week"], how="left").fillna({"overlap_pairs": 0.0})


def supervisor_weekly(d: Data, cfg: Cfg) -> pd.DataFrame:
    r = d.reviews[d.reviews.decided_at.notna()].copy()
    r["week"] = week_floor(r["decided_at"])
    r["approved"] = (r.status == "approved") * 1.0
    r["doc_missing"] = ((r.status == "approved") & ~r.has_documentation.astype(bool)) * 1.0
    r["rapid"] = (r.decision_minutes < cfg.t["rapid_review_minutes"]) * 1.0
    return r.groupby(["supervisor_id", "week"]).agg(n_decided=("id", "size"), approve_rate=("approved", "mean"), doc_missing_rate=("doc_missing", "mean"),
                                                    mean_minutes=("decision_minutes", "mean"), rapid_rate=("rapid", "mean")).reset_index()
