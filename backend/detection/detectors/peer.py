"""Behavioural detectors (kind="behavioral"): they corroborate other findings, or raise a Low-capped alert on their own."""
import hashlib

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import RobustScaler

from detection.base import Detector, register
from detection.features import supervisor_weekly, therapist_weekly
from detection.types import OPERATIONAL, SUPERVISOR, THERAPIST


def robust_z(x: float, cohort: np.ndarray, min_scale: float) -> tuple[float, float]:
    """Modified z-score from median/MAD – robust, because the outliers being hunted must not inflate the baseline."""
    med = float(np.median(cohort))
    return (x - med) / max(float(np.median(np.abs(cohort - med))) * 1.4826, min_scale), med


# cohort spec: (weekly table builder, id column, category, {feature: (label, min_scale, weight key)})
COHORTS = [
    (therapist_weekly, "practitioner_id", THERAPIST, {
        "cancel_rate": ("Cancellation rate", 0.04, "peer_outlier_rate"), "heavy_mod_rate": ("Share of sessions modified 2+ times", 0.04, "peer_outlier_rate"),
        "mismatch_rate": ("Unsupported duration/check-in rate", 0.04, "peer_outlier_rate"), "noshow_rate": ("No-show rate", 0.04, "peer_outlier_rate"),
        "load": ("Weekly load vs capacity", 0.12, "peer_outlier_volume")}),
    (supervisor_weekly, "supervisor_id", SUPERVISOR, {
        "rapid_rate": ("Share of reviews under 3 minutes", 0.04, "peer_outlier_rate"), "doc_missing_rate": ("Approvals without documentation", 0.04, "peer_outlier_rate"),
        "n_decided": ("Weekly reviews decided", 2.0, "peer_outlier_volume")}),
]


class Behavioral(Detector):
    kind, domain, scenario = "behavioral", OPERATIONAL, "behavioral_anomaly"

    def weekly(self, build):
        return self.ctx.memo(build.__name__, lambda: build(self.d, self.cfg))   # computed once, shared by both detectors


@register
class PeerOutliers(Behavioral):
    def detect(self):
        t, out, since = self.t, [], self.d.since(self.cfg.windows["recent_days"])
        for build, id_col, category, feats in COHORTS:
            weekly = self.weekly(build)
            agg = weekly[weekly.week >= since.normalize() - pd.Timedelta(days=6)].groupby(id_col)[list(feats)].mean()
            if len(agg) < t["min_cohort"]:
                continue
            for uid, row in agg.iterrows():
                inds, ev = [], []
                for f, (label, scale, wkey) in feats.items():
                    z, med = robust_z(row[f], agg[f].to_numpy(), scale)
                    if z >= t["robust_z_min"]:
                        inds.append(self.cfg.ind(f"peer_outlier_{f}", f"{label} vs peers (robust z)", round(z, 1), f">= {t['robust_z_min']}",
                                                 max(0.5, (z - t["robust_z_min"]) / (2 * t["robust_z_min"]) + 0.5), "statistical", f"value {row[f]:.2f}, cohort median {med:.2f}",
                                                 weight_key=wkey))
                        ev.append({"type": "peer_comparison", "feature": f, "value": round(float(row[f]), 3), "cohort_median": round(med, 3), "robust_z": round(z, 1)})
                if inds:
                    out.append(self.finding(int(uid), inds, ev, [f"window:{self.d.as_of.isocalendar().year}-W{self.d.as_of.isocalendar().week:02d}"], category=category,
                                            title=f"Behavioural outlier vs peers: {self.d.label(int(uid))}", window_days=self.cfg.windows["recent_days"],
                                            action="Discuss in the next supervision session; check for legitimate causes (leave, caseload change)."))
        return out


N_ESTIMATORS = 200


def model_version(cfg) -> str:
    sig = hashlib.sha1(f"{[list(c[3]) for c in COHORTS]}{N_ESTIMATORS}{cfg.seed}".encode()).hexdigest()[:6]
    return f"iforest-v2(n={N_ESTIMATORS},seed={cfg.seed},feat={sig})"


ML_FEATURES = {THERAPIST: ["load", "cancel_rate", "noshow_rate", "heavy_mod_rate", "mismatch_rate", "overlap_pairs"],
               SUPERVISOR: ["n_decided", "doc_missing_rate", "mean_minutes", "approve_rate", "rapid_rate"]}


@register
class IsolationForestDetector(Behavioral):
    """Unsupervised (no labelled fraud exists). Always explained by robust-z drivers; unexplainable flags are dropped."""

    def detect(self):
        t, out = self.t, []
        for build, id_col, category, _ in COHORTS:
            feats, df = ML_FEATURES[category], self.weekly(build).dropna(subset=ML_FEATURES[category]).reset_index(drop=True)
            if len(df) < 50 or df[id_col].nunique() < t["min_cohort"]:
                continue
            X = RobustScaler().fit_transform(df[feats].to_numpy())
            df["anom"] = -IsolationForest(n_estimators=N_ESTIMATORS, contamination="auto", random_state=self.cfg.seed).fit(X).score_samples(X)
            thr, last = float(df.anom.quantile(t["ml_percentile"])), df.week.max()
            for uid, g in df[df.week > last - pd.Timedelta(weeks=t["ml_recent_weeks"])].groupby(id_col):
                score = float(g.anom.max())
                if score < thr:
                    continue
                recent = g[feats].mean()
                drivers = []
                for f in feats:
                    z, med = robust_z(float(recent[f]), df[f].to_numpy(), 0.04 if f.endswith("rate") else 1.0)
                    z = -z if f == "mean_minutes" else z                      # shorter review time is the suspicious direction
                    if z >= 2.0:
                        drivers.append((f, z, float(recent[f]), med))
                if not drivers:
                    continue
                drivers.sort(key=lambda x: -x[1])
                strength = 0.3 + 0.7 * (score - thr) / max(1e-9, df.anom.max() - thr)
                out.append(self.finding(int(uid), [self.cfg.ind("ml_isolation_forest", "Isolation-Forest anomaly score (recent weeks)", round(score, 3), f"> {thr:.3f} (p{int(t['ml_percentile'] * 100)} of cohort history)",
                                                                strength, "ml", "Top drivers: " + ", ".join(f"{f} (z={z:.1f})" for f, z, _, _ in drivers[:3]))],
                                        [{"type": "ml_feature_contribution", "feature": f, "value": round(v, 3), "cohort_median": round(m, 3), "robust_z": round(z, 1)} for f, z, v, m in drivers[:5]],
                                        [f"window:{self.d.as_of.isocalendar().year}-W{self.d.as_of.isocalendar().week:02d}"], category=category,
                                        title=f"Unsupervised behavioural anomaly: {self.d.label(int(uid))}", window_days=t["ml_recent_weeks"] * 7,
                                        action="Use as a prompt for review only; corroborate with rule/statistical evidence."))
        return out
