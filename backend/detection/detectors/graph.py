"""Relationship / graph analysis (networkx) – used where individual-level tests cannot see the signal.

Ring = a therapist that has BOTH (a) an exclusive referral dependency – one counselor sends >=25% of its referrals there
(above policy lift) and supplies >=50% of the therapist's intake – AND (b) an unconditional approval edge: its supervisor
approved >=97% of >=8 reviews. Either edge alone is ordinary; their co-occurrence in one component is what graph analysis adds.
"""
import networkx as nx

from detection.base import Detector, register
from detection.detectors.referral import referral_analysis
from detection.types import MISCONDUCT, NETWORK


@register
class ReferralApprovalRing(Detector):
    category, domain, scenario = NETWORK, MISCONDUCT, "referral_approval_ring"

    def detect(self):
        t, ind, ra = self.t, self.cfg.ind, self.ctx.memo("referrals", lambda: referral_analysis(self.ctx))
        start = self.d.since(self.cfg.windows["lookback_days"])
        intake = self.d.referrals[self.d.referrals.created_at >= start].groupby("to_practitioner_id").size().to_dict()
        G, dep, lax = nx.DiGraph(), {}, {}
        for cid, v in ra["per_counselor"].items():
            for k, tid in enumerate(ra["therapists"]):
                o = v["obs"][k]
                if o < t["graph_min_referrals"]:
                    continue
                out_share, in_share, lift = o / v["n"], o / max(1, intake.get(tid, 1)), o / max(0.5, v["policy"]["e"][k])
                G.add_edge(f"C{cid}", f"T{tid}", kind="referral", weight=int(o))
                if out_share >= t["graph_out_share_min"] and in_share >= t["graph_in_share_min"] and lift >= t["graph_lift_min"] and in_share > dep.get(tid, {}).get("in_share", 0):
                    dep[tid] = {"counselor": cid, "out_share": out_share, "in_share": in_share, "lift": lift}
        rv = self.d.reviews[self.d.reviews.decided_at >= start]
        for (sid, tid), g in rv.groupby(["supervisor_id", "supervisee_id"]):
            rate = float((g.status == "approved").mean())
            G.add_edge(f"S{sid}", f"T{tid}", kind="approval", weight=len(g))
            if len(g) >= t["graph_min_reviews"] and rate >= t["graph_approve_rate_min"]:
                others = rv[(rv.supervisor_id == sid) & (rv.supervisee_id != tid)]
                lax[tid] = {"supervisor": int(sid), "n": len(g), "others_rate": float((others.status == "approved").mean()) if len(others) else None,
                            "median_minutes": float(g.decision_minutes.median())}
        out = []
        for tid in set(dep) & set(lax):
            a, b = dep[tid], lax[tid]
            nodes = {f"C{a['counselor']}", f"T{tid}", f"S{b['supervisor']}"}
            others_txt = f"{b['others_rate']:.0%}" if b["others_rate"] is not None else "n/a"
            inds = [ind("exclusive_referral_dependency", "Counselor ↔ practitioner exclusive referral dependency",
                        f"{a['out_share']:.0%} of counselor's referrals; {a['in_share']:.0%} of practitioner's intake; lift {a['lift']:.1f}×",
                        f"out>={t['graph_out_share_min']:.0%}, in>={t['graph_in_share_min']:.0%}, lift>={t['graph_lift_min']}×", 0.5 + (a["in_share"] - t["graph_in_share_min"]) / 0.4, "graph"),
                    ind("lax_approval_edge", "Supervisor approves this practitioner's work unconditionally", f"{b['n']}/{b['n']} approved (supervisor's other supervisees: {others_txt})",
                        f">= {t['graph_approve_rate_min']:.0%} over >= {t['graph_min_reviews']} reviews", 0.5 + (b["n"] - t["graph_min_reviews"]) / 24, "graph", f"median review time {b['median_minutes']:.1f} min")]
            ev = [{"type": "graph_cluster", "counselor": int(a["counselor"]), "therapist": int(tid), "supervisor": b["supervisor"],
                   "cluster_density": round(nx.density(G.subgraph(nodes)), 2), "component_size": len(nx.node_connected_component(G.to_undirected(), f"T{tid}"))},
                  {"type": "referral_edge", **{k: round(float(v), 3) for k, v in a.items()}}, {"type": "approval_edge", **{k: v for k, v in b.items() if v is not None}}]
            out.append(self.finding(int(tid), inds, ev, [f"edge:C{a['counselor']}-T{tid}", f"edge:S{b['supervisor']}-T{tid}"], related=[int(a["counselor"]), b["supervisor"]],
                                    title=f"Exclusive referral/approval cluster around {self.d.label(int(tid))}",
                                    action="Review whether a relationship or conflict of interest exists among the three users; audit a sample of the practitioner's reviewed cases independently of the supervisor."))
        return out
