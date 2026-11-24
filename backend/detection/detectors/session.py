"""Category A – therapist session integrity. Why rules: overlaps and unverifiable durations are logical impossibilities."""
import pandas as pd

from detection.base import Detector, register
from detection.features import find_overlaps, mismatch_mask
from detection.types import OPERATIONAL, MISCONDUCT, THERAPIST


class SessionDetector(Detector):
    category = THERAPIST

    def sessions(self) -> pd.DataFrame:
        return self.d.sessions[self.d.sessions.scheduled_start >= self.d.since(self.cfg.windows["lookback_days"])]


@register
class SessionOverlap(SessionDetector):
    scenario, domain = "session_overlap", OPERATIONAL

    def detect(self):
        t, ind, out = self.t, self.cfg.ind, []
        by: dict[int, list] = {}
        for p in find_overlaps(self.sessions(), t["overlap_tolerance_min"]):
            by.setdefault(p["practitioner_id"], []).append(p)
        for prac, ps in by.items():
            impossible = [p for p in ps if p["impossible"]]
            completed = [p for p in ps if p["a_status"] == p["b_status"] == "completed"]
            inds = [ind("overlap_pairs", "Overlapping session pairs", len(ps), f">= 1 (full at {t['overlap_pairs_full']})", min(1, len(ps) / t["overlap_pairs_full"]), note="Intervals overlap by more than the tolerance")]
            if impossible:
                inds.append(ind("impossible_location", "Physically impossible: in-person at two locations", len(impossible), ">= 1 (full at 2)", min(1, len(impossible) / 2),
                                note="Both sessions in person at different locations at the same time"))
            if completed:
                inds.append(ind("completed_overlap", "Overlap between sessions both recorded as completed", len(completed), ">= 1 (full at 3)", min(1, len(completed) / 3),
                                note="Completed (with check-in) – not merely a scheduling conflict"))
            ev = [{"type": "session_overlap", **p} for p in sorted(ps, key=lambda p: (-p["overlap_min"], p["a_start"]))[:15]]
            refs = sorted({f"session:{p[k]}" for p in ps for k in ("session_a", "session_b")})
            out.append(self.finding(prac, inds, ev, refs, title=f"Overlapping session records ({len(ps)} pairs) for {self.d.label(prac)}",
                                    action="Compare the overlapping records with check-in/out logs; ask the practitioner to confirm which session took place; "
                                           "correct the schedule data if it is a recording error."))
        return out


@register
class ExcessiveHours(SessionDetector):
    scenario, domain = "excessive_hours", OPERATIONAL

    def detect(self):
        s = self.sessions()
        s = s[s.status.isin(["completed", "scheduled"])].drop_duplicates(["practitioner_id", "scheduled_start", "group_id"]).copy()
        s["day"], s["dur"] = s.scheduled_start.dt.normalize(), (s.scheduled_end - s.scheduled_start).dt.total_seconds() / 60
        daily = s.groupby(["practitioner_id", "day"])["dur"].sum().reset_index()
        limit = self.t["max_daily_hours"]
        return [self.finding(int(prac), [self.cfg.ind("excessive_daily_hours", "Days with excessive session hours", len(g), f"> {limit} h/day", min(1, len(g) / 3))],
                             [{"type": "daily_hours", "day": str(r.day.date()), "minutes": round(r.dur)} for r in g.itertuples()],
                             [f"day:{prac}:{r.day.date()}" for r in g.itertuples()], title=f"Excessive daily session hours for {self.d.label(int(prac))}",
                             action="Verify the schedule for the listed days.")
                for prac, g in daily[daily.dur > limit * 60].groupby("practitioner_id")]


@register
class DurationDiscrepancy(SessionDetector):
    scenario, domain = "duration_discrepancy", MISCONDUCT

    def detect(self):
        t, ind, out = self.t, self.cfg.ind, []
        done = self.sessions()
        done = done[done.status == "completed"].drop_duplicates(["practitioner_id", "scheduled_start", "group_id"]).copy()
        done["bad"] = mismatch_mask(done, t["duration_slack_min"], t["duration_slack_ratio"])
        for prac, g in done.groupby("practitioner_id"):
            bad, n = g[g.bad], len(g)
            if len(bad) < t["duration_min_events"] or len(bad) / n < t["duration_min_share"]:
                continue
            nocheck = bad[bad.checkin_at.isna()]
            inds = [ind("inflated_duration_share", "Share of completed sessions with unsupported reported duration", round(len(bad) / n, 3), f">= {t['duration_min_share']}",
                        (len(bad) / n) / t["duration_share_full"], note=f"{len(bad) - len(nocheck)} inflated vs check-in/out span, {len(nocheck)} without check-in")]
            if len(nocheck) >= 2:
                inds.append(ind("no_checkin_share", "Completed sessions with no check-in record", len(nocheck), ">= 2 (full at 8)", len(nocheck) / 8))
            ev = [{"type": "duration_mismatch", "session": int(r.id), "start": r.scheduled_start.isoformat(timespec="minutes"), "reported_min": int(r.reported_duration_min or 0),
                   "verified_span_min": None if pd.isna(r.checkin_at) else round((r.checkout_at - r.checkin_at).total_seconds() / 60), "client_ref": r.client_ref}
                  for r in bad.sort_values("scheduled_start", ascending=False).head(15).itertuples()]
            out.append(self.finding(int(prac), inds, ev, [f"session:{int(i)}" for i in bad.id], title=f"Reported session durations not supported by check-in data for {self.d.label(int(prac))}",
                                    action="Request the practitioner's explanation; compare against platform check-in logs; review a sample of session notes. "
                                           "Possible manipulation of service records is a hypothesis only."))
        return out
