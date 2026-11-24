"""Category D – administrative / platform security. Why rules: authorization violations are violations by definition."""
from collections import defaultdict

from detection.base import Detector, register
from detection.data import bursts
from detection.types import ADMIN, SECURITY

EDIT_ACTIONS = ["credential_edit", "contract_edit", "assignment_edit", "profile_edit"]
iso = lambda ts: ts.isoformat(timespec="minutes")  # noqa: E731


class SecurityDetector(Detector):
    category, domain = ADMIN, SECURITY

    def recent(self, frame, event=None, action=None):
        f = frame[frame.ts >= self.d.since(14)]
        f = f[f.event == event] if event else f
        return f[f.action.isin(action if isinstance(action, list) else [action])] if action else f

    def security_finding(self, subject, inds, ev, refs, **kw):
        return self.finding(subject, inds, ev, refs, window_days=14, **kw)


@register
class AdminScopeAbuse(SecurityDetector):
    """Denied-access bursts + scope probing + account-creation bursts + privilege grants -> ONE alert per account."""
    scenario = "admin_out_of_scope"

    def detect(self):
        t, ind, acc = self.t, self.cfg.ind, defaultdict(lambda: ([], [], []))   # actor -> (indicators, evidence, refs)
        den = self.recent(self.d.access, event="access_denied").dropna(subset=["user_id"])
        for uid, n, win in bursts(den, "user_id", t["denied_burst_window_min"], t["denied_burst_min"]):
            inds, ev, refs = acc[int(uid)]
            inds.append(ind("denied_access_burst", "Denied access attempts in one window", n, f">= {t['denied_burst_min']} in {t['denied_burst_window_min']} min", n / 8,
                            note="Each attempt was blocked and audited"))
            areas = sorted(set(win.resource_type.dropna()))
            if len(areas) >= 2:
                inds.append(ind("scope_probing", "Distinct resource areas probed", len(areas), ">= 2 (full at 3)", len(areas) / 3, note=", ".join(areas)))
            ev += [{"type": "access_denied", "ts": iso(r.ts), "path": r.path, "permission": r.permission, "ip": r.ip} for r in win.itertuples()]
            refs += [f"access:{int(r.id)}" for r in win.itertuples()]
        for uid, n, win in bursts(self.recent(self.d.admin, action="account_create"), "actor_id", t["account_burst_window_min"], t["account_burst_min"]):
            inds, ev, refs = acc[int(uid)]
            inds.append(ind("account_creation_burst", "Accounts created in a short window", n, f">= {t['account_burst_min']} in {t['account_burst_window_min']} min", n / 5))
            ev += [{"type": "account_create", "ts": iso(r.ts), "target_user": int(r.target_user_id), "role": (r.detail or {}).get("role")} for r in win.itertuples()]
            refs += [f"admin:{int(r.id)}" for r in win.itertuples()]
        grants = self.recent(self.d.admin, action="role_change")
        grants = grants[grants.detail.apply(lambda x: isinstance(x, dict) and x.get("to") in self.cfg.raw["privileged_roles"])]
        for uid, g in grants.groupby("actor_id"):
            if int(uid) in acc:      # a privileged grant alone is a normal admin task – it only counts alongside other anomalies
                inds, ev, refs = acc[int(uid)]
                inds.append(ind("privilege_grants", "Privileged roles granted in the same period", len(g), ">= 1 alongside other admin anomalies", len(g) / 3))
                ev += [{"type": "role_change", "ts": iso(r.ts), "target_user": int(r.target_user_id), "to": (r.detail or {}).get("to")} for r in g.itertuples()]
                refs += [f"admin:{int(r.id)}" for r in g.itertuples()]
        return [self.security_finding(uid, inds, ev, refs, title=f"Administrative account activity outside permission scope: {self.d.label(uid)}",
                                      action="Confirm with the account owner what the intent was; review the audit trail; consider temporary credential reset. Do not sanction on the score alone.")
                for uid, (inds, ev, refs) in acc.items()]


@register
class ModificationBurst(SecurityDetector):
    scenario = "admin_modification_burst"

    def detect(self):
        t = self.t
        return [self.security_finding(int(uid), [self.cfg.ind("admin_modification_burst", "Sensitive-record edits in one hour", n,
                                                              f">= {t['admin_burst_min']} per {t['admin_burst_window_min']} min (typical <= 3)", 0.5 + (n - t["admin_burst_min"]) / (2 * t["admin_burst_min"]))],
                                      [{"type": r.action, "ts": iso(r.ts), "target_user": int(r.target_user_id), "detail": r.detail} for r in win.itertuples()],
                                      [f"admin:{int(r.id)}" for r in win.itertuples()], title=f"Burst of {n} credential/contract modifications by {self.d.label(int(uid))}",
                                      action="Check for an approved change request; compare modified values with source documents; verify the credentials/contracts changed are valid.")
                for uid, n, win in bursts(self.recent(self.d.admin, action=EDIT_ACTIONS), "actor_id", t["admin_burst_window_min"], t["admin_burst_min"])]


@register
class FailedLoginBurst(SecurityDetector):
    scenario = "failed_login_burst"

    def detect(self):
        t = self.t
        failed = self.recent(self.d.access, event="login_failed").dropna(subset=["user_id"])
        return [self.security_finding(int(uid), [self.cfg.ind("failed_login_burst", "Failed logins in one window", n, f">= {t['failed_login_min']} in {t['failed_login_window_min']} min", n / 15,
                                                              note=f"{win.ip.nunique()} distinct source addresses")],
                                      [{"type": "login_failed", "ts": iso(r.ts), "ip": r.ip} for r in win.itertuples()], [f"access:{int(r.id)}" for r in win.itertuples()],
                                      title=f"Repeated failed logins against {self.d.label(int(uid))}", action="Lock/reset the account, notify the owner, review source addresses.")
                for uid, n, win in bursts(failed, "user_id", t["failed_login_window_min"], t["failed_login_min"])]


@register
class MultiAccountIp(SecurityDetector):
    scenario = "multi_account_ip"

    def detect(self):
        t = self.t
        failed = self.recent(self.d.access, event="login_failed").dropna(subset=["ip"])
        return [self.security_finding(None, [self.cfg.ind("multi_account_ip", "Distinct accounts targeted from one address", n, f">= {t['multi_ip_min_accounts']} in {t['multi_ip_window_min']} min", n / 6)],
                                      [{"type": "login_failed", "ts": iso(r.ts), "ip": r.ip, "user": int(r.user_id)} for r in win.itertuples()], [f"access:{int(r.id)}" for r in win.itertuples()],
                                      title=f"Address {ip} failed to authenticate against {n} different accounts", related=sorted({int(u) for u in win.user_id.dropna()}), key_suffix=ip,
                                      action="Block/rate-limit the address; reset targeted accounts; check whether any attempt succeeded.")
                for ip, n, win in bursts(failed, "ip", t["multi_ip_window_min"], t["multi_ip_min_accounts"], distinct="user_id")]
