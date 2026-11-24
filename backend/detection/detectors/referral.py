"""Category B – referral concentration. Policy-aware Monte-Carlo goodness-of-fit (see ARCHITECTURE §5).

Expected distribution per referral = therapists whose specialisation matches the need, weighted by capacity, plus a small
"policy slack" (client requests / exceptions). A naive uniform test runs alongside: if ONLY the naive test fires, the pattern
is explained by specialisation/assignment policy and is logged as *suppressed* instead of alerting.
"""
import numpy as np
from scipy.special import xlogy

from detection.base import Context, Detector, register
from detection.types import COUNSELOR, MISCONDUCT


def js_distance(p: np.ndarray, q: np.ndarray) -> np.ndarray:
    p = np.atleast_2d(p)
    m = 0.5 * (p + q)
    kl = lambda a, b: np.sum(xlogy(a, a) - xlogy(a, b), axis=1)  # noqa: E731
    return np.sqrt(np.maximum(0.5 * kl(p, m) + 0.5 * kl(np.broadcast_to(q, p.shape), m), 0) / np.log(2))


def mc_test(obs: np.ndarray, P: np.ndarray, sims: int, rng) -> dict:
    """Statistic Σ(o−e)²/max(e,.5) against a simulated null of independent per-referral categorical draws."""
    n, T = P.shape
    e, denom = P.sum(0), np.maximum(P.sum(0), 0.5)
    stat = float((((obs - e) ** 2) / denom).sum())
    idx = np.minimum((rng.random((sims, n, 1)) > P.cumsum(1)[None]).sum(2), T - 1)
    counts = np.stack([(idx == k).sum(1) for k in range(T)], axis=1).astype(float)
    q = e / e.sum()
    return {"p": (1 + int((((counts - e) ** 2 / denom).sum(1) >= stat).sum())) / (sims + 1), "e": e,
            "js_obs": float(js_distance(obs / n, q)[0]), "js_null": float(js_distance(counts / n, q).mean())}


def referral_analysis(ctx: Context) -> dict:
    """Per-counselor policy-aware vs naive analysis (memoised: the graph detector reuses it)."""
    d, t = ctx.data, ctx.cfg.t
    start = d.since(ctx.cfg.windows["lookback_days"])
    ths = d.users[(d.users.role == "therapist") & (d.users.status == "active")].id.tolist()
    prof = d.profiles.set_index("user_id")
    spec = {u: prof.specialization.get(u) for u in ths}
    cap = np.array([max(1, prof.capacity_weekly_sessions.get(u, 25)) for u in ths], dtype=float)
    rng, idx, per = np.random.default_rng(ctx.cfg.seed), {u: k for k, u in enumerate(ths)}, {}
    for cid, g in d.referrals[d.referrals.created_at >= start].groupby("from_user_id"):
        if len(g) < t["min_referrals"] or d.roles.get(cid) != "assistant_counselor":
            continue
        P = np.zeros((len(g), len(ths)))
        for i, need in enumerate(g.need):
            mask = np.array([spec[u] == need for u in ths])
            mask = mask if mask.any() else ~mask
            policy = np.where(mask, cap, 0) / np.where(mask, cap, 0).sum()
            P[i] = (1 - t["referral_policy_slack"]) * policy + t["referral_policy_slack"] / len(ths)   # policy is soft
        obs = np.bincount([idx[x] for x in g.to_practitioner_id], minlength=len(ths)).astype(float)
        per[int(cid)] = {"n": len(g), "obs": obs, "policy": mc_test(obs, P, t["referral_simulations"], rng),
                         "naive": mc_test(obs, np.tile(np.ones(len(ths)) / len(ths), (len(g), 1)), t["referral_simulations"], rng),
                         "mismatch": float(np.mean([spec.get(x) != need for x, need in zip(g.to_practitioner_id, g.need)])), "refs": [int(x) for x in g.id]}
    return {"therapists": ths, "spec": spec, "per_counselor": per, "window_start": start}


@register
class ReferralConcentration(Detector):
    category, domain, scenario = COUNSELOR, MISCONDUCT, "referral_concentration"

    def detect(self):
        t, ind, ra, out = self.t, self.cfg.ind, self.ctx.memo("referrals", lambda: referral_analysis(self.ctx)), []
        ths, per = ra["therapists"], ra["per_counselor"]
        median_mismatch = float(np.median([v["mismatch"] for v in per.values()])) if per else 0.0
        for cid, v in per.items():
            pol, nai, n = v["policy"], v["naive"], v["n"]
            top = np.argsort(-v["obs"])[:5]
            if not (pol["p"] <= t["referral_alpha"] and pol["js_obs"] > pol["js_null"]):
                if nai["p"] <= t["referral_alpha"]:
                    self.ctx.suppressed.append({
                        "type": "suppressed_referral_concentration", "counselor": cid, "category": COUNSELOR, "reason": "Concentration is explained by specialisation/assignment policy",
                        "naive_p": round(nai["p"], 4), "policy_aware_p": round(pol["p"], 4),
                        "top_therapists": [{"therapist": int(ths[k]), "share": round(float(v["obs"][k] / n), 3), "policy_expected_share": round(float(pol["e"][k] / n), 3)} for k in top[:3]]})
                continue
            top2 = top[:2]
            obs_share, exp_share = float(v["obs"][top2].sum() / n), float(pol["e"][top2].sum() / n)
            inds = [ind("referral_concentration_p", "Referral distribution vs policy-expected (Monte-Carlo GOF p-value)", round(pol["p"], 5), f"<= {t['referral_alpha']}",
                        -np.log10(pol["p"]) / np.log10(t["referral_simulations"] + 1), "statistical", f"naive-uniform test p={nai['p']:.4f}"),
                    ind("referral_js_divergence", "Jensen-Shannon distance observed vs expected", round(pol["js_obs"], 3), f"null mean {pol['js_null']:.2f}",
                        (pol["js_obs"] - pol["js_null"]) / max(1e-6, t["referral_js_full"] - pol["js_null"]), "statistical"),
                    ind("referral_top2_excess", "Share sent to the two most-used practitioners (observed vs expected)", f"{obs_share:.0%} vs {exp_share:.0%}", "excess >= 0",
                        (obs_share - exp_share) / 0.5, "statistical")]
            if v["mismatch"] - median_mismatch > 0.1:
                inds.append(ind("referral_spec_mismatch", "Referrals to practitioners whose specialisation does not match the need", f"{v['mismatch']:.0%}", f"peer median {median_mismatch:.0%}",
                                (v["mismatch"] - median_mismatch) / 0.5))
            ev = [{"type": "referral_distribution", "therapist": int(ths[k]), "referrals": int(v["obs"][k]), "share": round(float(v["obs"][k] / n), 3),
                   "policy_expected_share": round(float(pol["e"][k] / n), 3), "specialisation": ra["spec"][ths[k]]} for k in top]
            out.append(self.finding(cid, inds, ev, [f"referral:{x}" for x in v["refs"]], title=f"Abnormal referral concentration for {self.d.label(cid)}",
                                    related=[int(ths[k]) for k in top2], action="Compare the distribution with assignment policy and client requests; check declared relationships/conflicts of "
                                    "interest between the counselor and the top practitioners. Rule out specialisation or capacity constraints before drawing any conclusion."))
        return out
