"""Deterministic, evidence-grounded explanations. (The optional LLM only paraphrases these; it never scores.)"""
SCENARIO_TEXT = {
    "session_overlap": ("Scheduling inconsistency: the practitioner has session records whose time intervals overlap (a practitioner cannot deliver two 1:1 sessions at once).",
                        ["double-booking or calendar sync error", "a session recorded against the wrong slot", "unrecorded group session (should carry a shared group id)"]),
    "excessive_hours": ("Unusually many session hours scheduled in a single day.", ["a long clinic day that was approved", "data-entry error"]),
    "duration_discrepancy": ("Discrepancy between reported and verifiable session duration: reported durations exceed the check-in/check-out span, or completed sessions carry no check-in at all.",
                             ["late/forgotten check-out", "technical problems with the check-in tool", "sessions delivered through a channel that is not instrumented"]),
    "cancellation_pattern": ("Unusual cancellation / modification pattern compared with peers and with the practitioner's own history.",
                             ["illness, leave or caseload transition", "platform outage", "client-driven rescheduling"]),
    "referral_behavior_shift": ("The counselor's referral targets changed between the previous and the recent period by more than chance explains.",
                                ["a change in the client mix or needs", "a new assignment policy or practitioner capacity", "client requests for specific practitioners"]),
    "referral_concentration": ("Referral distribution differs significantly from what the assignment policy (specialisation + capacity) would predict: referrals are concentrated on very few practitioners.",
                               ["a niche specialisation with few eligible practitioners (policy-explained)", "a client request for a specific practitioner", "capacity/availability constraints not captured in the data"]),
    "approval_burst": ("Supervisor approval pattern is unusual: approvals were issued without the required supporting documentation and/or with implausibly short review time.",
                       ["end-of-period backlog clearing", "documentation stored outside the platform", "delegated reviews recorded under the supervisor's account"]),
    "admin_out_of_scope": ("Administrative account attempted actions outside its permission scope and/or created or elevated accounts in an unusual pattern. The attempts were blocked and fully audited.",
                           ["misconfigured automation or integration", "admin exploring the UI without understanding scope", "genuine insider-threat or compromised-credential scenario"]),
    "admin_modification_burst": ("Unusually many modifications to sensitive records (credentials/contracts) in a short window.",
                                 ["legitimate bulk renewal campaign (should be documented in a change ticket)", "data migration or clean-up task"]),
    "failed_login_burst": ("Burst of failed login attempts against one account, possibly from several addresses (brute force).", ["user forgot password", "shared device with stale saved credentials"]),
    "multi_account_ip": ("A single network address failed to authenticate against several different accounts (credential stuffing / password spraying pattern).",
                         ["shared corporate NAT address", "misconfigured service account"]),
    "referral_approval_ring": ("Network pattern: a counselor, a practitioner and that practitioner's supervisor form an exclusive cluster — the counselor routes an unusually large share of referrals to the "
                               "practitioner (above what policy predicts), who receives almost all referrals from that counselor, while the supervisor approves that practitioner's work unconditionally.",
                               ["small, well-functioning team with natural referral habits", "specialisation not captured in the data"]),
    "behavioral_anomaly": ("Behavioural outlier versus peers / own history, detected statistically and by an unsupervised model. Low standalone confidence; use as a prompt for review, not as evidence.",
                           ["seasonal workload", "role change", "new caseload mix"]),
    "supervisor_escalation": ("A clinical supervisor escalated this case for additional review.", []),
}
DISCLAIMER = ("This alert is advisory. It is a statistical/rule-based signal and does NOT establish fraud or misconduct. "
              "Decisions require authorised human review, evidence and a documented process.")


def build_explanation(scenario: str, subject: str, score: float, level: str, breakdown: list[dict]) -> str:
    summary, benign = SCENARIO_TEXT.get(scenario, (scenario, []))
    lines = [summary, "", f"Subject: {subject}. Risk score {score:.0f}/100 ({level.upper()}).", "", "Why this score (indicator → points):"]
    lines += [f"  • [{b['method']}] {b['label']}: value={b['value']} (ref {b['threshold']}), weight {b['weight']} × strength {b['strength']} → {b['points']:.1f} pts"
              + (f" — {b['note']}" if b.get("note") else "") for b in breakdown]
    if benign:
        lines += ["", "Possible benign explanations to rule out: " + "; ".join(benign) + "."]
    return "\n".join(lines + ["", DISCLAIMER])
