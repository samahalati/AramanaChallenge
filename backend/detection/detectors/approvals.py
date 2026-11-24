"""Category C – supervisor approval behaviour. Volume alone is NOT misconduct: only a weak statistical hint."""
from detection.base import Detector, register
from detection.data import bursts
from detection.types import MISCONDUCT, SUPERVISOR
import numpy as np


@register
class ApprovalAnomaly(Detector):
    category, domain, scenario = SUPERVISOR, MISCONDUCT, "approval_burst"

    def detect(self):
        t, ind, out = self.t, self.cfg.ind, []
        rv = self.d.reviews[self.d.reviews.decided_at >= self.d.since(self.cfg.windows["recent_days"])]
        peak = {k: n for k, n, _ in bursts(rv, "supervisor_id", t["burst_window_hours"] * 60, 1, ts="decided_at")}
        median_peak = max(1.0, float(np.median(list(peak.values())))) if peak else 1.0
        for sup, g in rv.groupby("supervisor_id"):
            appr = g[g.status == "approved"]
            if appr.empty:
                continue
            nodoc, rapid, n = appr[~appr.has_documentation.astype(bool)], appr[appr.decision_minutes < t["rapid_review_minutes"]], len(appr)
            inds = []
            if len(nodoc) >= t["approvals_missing_min"] and len(nodoc) / n >= t["approvals_missing_share"]:
                inds.append(ind("approvals_missing_docs", "Approvals without required supporting documentation", f"{len(nodoc)} of {n}",
                                f">= {t['approvals_missing_min']} and >= {int(t['approvals_missing_share'] * 100)}%", len(nodoc) / n / 0.4))
            if len(rapid) >= t["rapid_review_min"] and len(rapid) / n >= t["rapid_review_share"]:
                inds.append(ind("rapid_approvals", f"Approvals with < {t['rapid_review_minutes']:.0f} min review time", f"{len(rapid)} of {n}",
                                f">= {t['rapid_review_min']} and >= {int(t['rapid_review_share'] * 100)}%", len(rapid) / n / 0.5))
            ratio = peak[sup] / median_peak
            if ratio >= t["burst_ratio_min"] and peak[sup] >= 15:
                inds.append(ind("approval_burst", f"Decisions within {t['burst_window_hours']}h vs cohort median", peak[sup], f"{t['burst_ratio_min']}× median ({median_peak:.0f})",
                                (ratio - t["burst_ratio_min"]) / 5 + 0.5, "statistical", "" if len(inds) else "Volume only – documentation and review time are normal"))
            if not inds:
                continue
            flagged = appr[~appr.has_documentation.astype(bool) | (appr.decision_minutes < t["rapid_review_minutes"])]
            ev = [{"type": "approval", "review": int(x.id), "case_ref": x.case_ref, "decided_at": x.decided_at.isoformat(timespec="minutes"), "minutes": x.decision_minutes,
                   "has_documentation": bool(x.has_documentation), "supervisee": int(x.supervisee_id)} for x in flagged.sort_values("decided_at", ascending=False).head(20).itertuples()]
            out.append(self.finding(int(sup), inds, ev or [{"type": "volume", "decisions_in_window": peak[sup]}], [f"review:{int(i)}" for i in flagged.id] or [f"window:{self.d.as_of.date()}"],
                                    title=f"Unusual approval pattern for supervisor {self.d.label(int(sup))}", window_days=self.cfg.windows["recent_days"],
                                    action="Open the supervisor's recent approval history; request the missing documentation; ask whether reviews were delegated or "
                                           "backlog-cleared; consider second-review of flagged cases."))
        return out
