"""Synthetic data generator (NO real data).

Produces 12 weeks of plausible platform activity + *injected anomalies* + *hard negatives* and a
ground-truth file used by `python -m app.cli evaluate`.

Determinism: everything is driven by one seed (default 42).

Injected anomalies (positives)               scenario key
  A  therapist overlapping / impossible sessions   session_overlap          (brief scenario 1)
  A  therapist inflated reported durations         duration_discrepancy
  A  therapist cancellation / modification surge   cancellation_pattern
  B  counselor referral concentration              referral_concentration   (brief scenario 2)
  C  supervisor mass approval w/o documentation    approval_burst           (brief scenario 3)
  D  platform admin out-of-scope access + account  admin_out_of_scope       (brief scenario 4)
     creation + privilege grants
  D  HR admin credential-edit burst                admin_modification_burst
  D  brute-force / credential stuffing             failed_login_burst, multi_account_ip
  E  counselor–therapist–supervisor ring           referral_approval_ring

Hard negatives (must NOT raise medium+ alerts)
  busy-but-legit therapist (high volume, high capacity) · group sessions (shared interval) ·
  back-to-back sessions (touching, not overlapping) · counselor in a specialisation unit
  (concentration explained by assignment policy) · supervisor with legit end-of-quarter volume
  (complete documentation, normal review time) · normal HR admin · normal platform admin.
"""
from __future__ import annotations

import json
import random
import warnings
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from django.contrib.auth.hashers import make_password
from django.db import transaction

from accounts.models import User
from clinical.models import Client, Referral, Session
from core.audit import audit
from core.constants import SPECIALIZATIONS, Role, UserStatus
from core.models import AccessEvent, AdminActivity
from hr.models import Contract, Credential, LifecycleEvent, OrgUnit, PractitionerProfile, SupervisionAssignment
from supervision.models import CorrectiveAction, QualityIssue, Review, SupervisionMeeting

warnings.filterwarnings("ignore", message=".*received a naive datetime.*")   # the generator reasons in naive UTC


class UnitOfWork:
    """Tiny unit-of-work: add()/add_all() collect model instances, flush() bulk-inserts them per model class (parents first)."""

    def __init__(self):
        self.pending: dict[type, list] = {}

    def add(self, obj):
        self.pending.setdefault(type(obj), []).append(obj)

    def add_all(self, objs):
        for o in objs:
            self.add(o)

    def flush(self):
        for model, objs in self.pending.items():
            model.objects.bulk_create(objs, batch_size=500)
        self.pending = {}


DEMO_PASSWORD = "Demo!2345"
FIRST = ["Amira", "Basil", "Carmen", "Dario", "Elena", "Farid", "Gina", "Hugo", "Ines", "Jamal", "Kira", "Lukas",
         "Mona", "Nabil", "Olga", "Pavel", "Quinn", "Rania", "Sven", "Tala", "Uma", "Viktor", "Wafa", "Xenia",
         "Yara", "Zane", "Alina", "Bruno", "Celia", "Dimitri", "Edda", "Felix", "Greta", "Hana", "Ivo", "Jada"]
LAST = ["Ardent", "Brook", "Calder", "Dane", "Ellery", "Fenwick", "Garnet", "Hollis", "Iverson", "Jarrow", "Keane",
        "Lorne", "Marlow", "Nash", "Oakes", "Pryce", "Quill", "Rowan", "Sutter", "Thorne", "Underhill", "Vance",
        "Wren", "Yardley", "Zeller"]
FIRST_FA = ["آرزو", "بهراد", "پریسا", "داریوش", "الهام", "فرید", "گلناز", "هومن", "ایلیا", "جمال", "کیانا", "لادن", "مینا", "نیما", "اشکان", "پویا", "ندا", "رضا", "سپیده", "طاها",
            "شبنم", "وحید", "یاسمن", "زهره", "آیدا", "بابک", "سیما", "دانیال", "الناز", "فرهاد", "گیتا", "حسام", "ایرج", "جاوید", "کامیار", "لیلی"]
LAST_FA = ["احمدی", "بهرامی", "پورمحمد", "دهقان", "رحیمی", "فرهادی", "گودرزی", "حسینی", "ایزدی", "جلالی", "کریمی", "لطفی", "مرادی", "نوری", "اسدی", "پاکزاد", "قاسمی", "رضوی",
           "صادقی", "طاهری", "امینی", "وکیلی", "یزدانی", "زارعی", "شریفی"]
TEXT = {
    "en": {"north": "ARAMANA North", "south": "ARAMANA South", "teams": ["Team Alpha", "Team Beta", "Team Gamma", "Team Delta", "Trauma Unit"],
           "admin1": "Platform Admin One", "admin2": "Platform Admin Two", "hr1": "Hana HR", "hr2": "Hugo HR-Two", "comp1": "Corin Compliance", "comp2": "Cleo Compliance",
           "temp": "Temp Account {}", "initial": "Initial assignment", "rebalance": "Caseload rebalancing", "license": "Professional practice license",
           "cert": "Clinical supervision / counselling cert.", "issuer1": "Regional Health Authority", "issuer2": "Professional Counselling Board", "onboarded": "Onboarding completed",
           "susp": "Pending licence renewal", "react": "Licence renewed", "notes": "Reviewed case documentation.", "good": "Good practice; maintain documentation standards.",
           "fix": "Please complete the missing treatment-plan updates.", "action": "Update treatment plan and resubmit documentation.",
           "issues": ["Late note submission pattern", "Treatment plan not updated", "Repeated rescheduling feedback from clients"],
           "routine": "routine update", "reset": "password reset / unlock", "expiry": "expiry date extended", "enddate": "end date removed"},
    "fa": {"north": "آرامانا – شمال", "south": "آرامانا – جنوب", "teams": ["تیم آلفا", "تیم بتا", "تیم گاما", "تیم دلتا", "واحد تروما"],
           "admin1": "مدیر پلتفرم ۱", "admin2": "مدیر پلتفرم ۲", "hr1": "هانیه رحیمی", "hr2": "هومن کاظمی", "comp1": "کامران صادقی", "comp2": "کیانا سلطانی",
           "temp": "حساب موقت {}", "initial": "انتساب اولیه", "rebalance": "توازن‌بخشی مجدد پرونده‌ها", "license": "پروانه‌ی فعالیت حرفه‌ای",
           "cert": "گواهی نظارت بالینی / مشاوره", "issuer1": "سازمان نظام سلامت منطقه‌ای", "issuer2": "هیئت حرفه‌ای مشاوره", "onboarded": "فرایند جذب کامل شد",
           "susp": "در انتظار تمدید پروانه", "react": "پروانه تمدید شد", "notes": "مستندات پرونده بررسی شد.", "good": "عملکرد خوب؛ رعایت استانداردهای مستندسازی ادامه یابد.",
           "fix": "لطفاً به‌روزرسانی‌های ناقصِ طرح درمان را تکمیل کنید.", "action": "طرح درمان را به‌روزرسانی و مستندات را دوباره ارسال کنید.",
           "issues": ["الگوی تأخیر در ثبت یادداشت", "طرح درمان به‌روز نشده است", "بازخورد مکرر مراجعان درباره‌ی جابه‌جایی جلسه‌ها"],
           "routine": "به‌روزرسانی روتین", "reset": "بازنشانی رمز / رفع قفل", "expiry": "تاریخ انقضا تمدید شد", "enddate": "تاریخ پایان حذف شد"},
}
# 24 therapists. trauma has only 2 eligible practitioners (assignment-policy hard negative).
SPEC_PLAN = (["trauma"] * 2 + ["anxiety"] * 5 + ["depression"] * 5 + ["couples"] * 4 + ["child"] * 4 +
             ["addiction"] * 4)
DATE0 = date(2026, 8, 31)  # Monday of week 0; week 11 = Mon 2026-11-16 .. Fri 2026-11-20
N_WEEKS = 12


def _dt(d: date, h: int, m: int = 0) -> datetime:
    return datetime(d.year, d.month, d.day, h, m)


@transaction.atomic
def generate(seed: int = 42, ground_truth_path: str | None = None, lang: str = "fa") -> dict:
    X = TEXT[lang]
    first, last = (FIRST_FA, LAST_FA) if lang == "fa" else (FIRST, LAST)
    db, rng = UnitOfWork(), random.Random(seed)
    pw_hash = make_password(DEMO_PASSWORD)  # one hash shared by all demo accounts (fast seeding)
    names_used: set[str] = set()

    def name() -> str:
        while True:
            n = f"{rng.choice(first)} {rng.choice(last)}"
            if n not in names_used:
                names_used.add(n)
                return n

    def mk_user(email: str, role: str, full: str | None = None, status: str = "active",
                created_by=None, created_at=None) -> User:
        u = User(email=email, full_name=full or name(), password=pw_hash, role=role, status=status,
                 created_by=created_by, created_at=created_at or datetime(2026, 8, 1, 9, 0))
        db.add(u)
        db.flush()
        return u

    # ---------------------------------------------------------------- org
    north = OrgUnit(name=X["north"], kind="region")
    south = OrgUnit(name=X["south"], kind="region")
    db.add_all([north, south])
    db.flush()
    teams = []
    for i, (nm, par) in enumerate(list(zip(X["teams"], [north, north, south, south, north]))):
        t = OrgUnit(name=nm, kind="team", parent_id=par.id)
        db.add(t)
        teams.append(t)
    db.flush()

    # ---------------------------------------------------------------- staff accounts
    admin = mk_user("admin@aramana.test", Role.PLATFORM_ADMIN, X["admin1"])
    admin2 = mk_user("admin2@aramana.test", Role.PLATFORM_ADMIN, X["admin2"])
    hr1 = mk_user("hr@aramana.test", Role.HR_ADMIN, X["hr1"])
    hr2 = mk_user("hr2@aramana.test", Role.HR_ADMIN, X["hr2"])
    comp1 = mk_user("compliance@aramana.test", Role.COMPLIANCE_REVIEWER, X["comp1"])
    comp2 = mk_user("compliance2@aramana.test", Role.COMPLIANCE_REVIEWER, X["comp2"])
    sups = [mk_user(f"supervisor{i}@aramana.test", Role.CLINICAL_SUPERVISOR) for i in range(1, 9)]
    ths = [mk_user(f"therapist{i}@aramana.test", Role.THERAPIST) for i in range(1, 25)]
    cns = [mk_user(f"counselor{i}@aramana.test", Role.ASSISTANT_COUNSELOR) for i in range(1, 7)]

    caps = {}
    for i, t in enumerate(ths):
        cap = 25
        if i == 10:  # busy-but-legit therapist
            cap = 38
        caps[t.id] = cap
        # trauma specialists belong to the Trauma Unit
        spec = SPEC_PLAN[i]
        unit = teams[4] if spec == "trauma" else teams[i % 4]
        db.add(PractitionerProfile(user_id=t.id, specialization=spec, org_unit_id=unit.id,
                                   employment_type=rng.choice(["employee", "employee", "contractor"]),
                                   hire_date=DATE0 - timedelta(days=rng.randint(200, 1500)),
                                   capacity_weekly_sessions=cap))
    for i, s in enumerate(sups):
        db.add(PractitionerProfile(user_id=s.id, specialization=SPEC_PLAN[i * 3] if i * 3 < 24 else None,
                                   org_unit_id=teams[i % 4].id, employment_type="employee",
                                   hire_date=DATE0 - timedelta(days=rng.randint(800, 2500)),
                                   capacity_weekly_sessions=0))
    for i, c in enumerate(cns):
        db.add(PractitionerProfile(user_id=c.id, specialization=None,
                                   org_unit_id=teams[4].id if i == 2 else teams[i % 4].id,
                                   employment_type="employee", hire_date=DATE0 - timedelta(days=rng.randint(100, 900)),
                                   capacity_weekly_sessions=0))
    db.flush()

    # roles in the story
    T = {i + 1: t for i, t in enumerate(ths)}     # therapist N -> user
    S = {i + 1: s for i, s in enumerate(sups)}
    CN = {i + 1: c for i, c in enumerate(cns)}
    T_overlap, T_inflate, T_cancel, T_busy, T_group, T_b2b = T[5], T[7], T[9], T[11], T[13], T[14]
    T_ring, T_attacked = T[4], T[16]   # T4 is an *anxiety* specialist: ring is policy-consistent on the surface
    C_conc, C_spec, C_ring = CN[2], CN[3], CN[4]
    S_rubber, S_busy, S_ring = S[4], S[5], S[6]
    # supervisee mapping: supervisor i supervises therapists 3(i-1)+1..3i; then make S_ring (S6) supervise T_ring
    # by swapping T_ring with S6's first supervisee
    groups = {i: [T[3 * (i - 1) + k] for k in (1, 2, 3)] for i in range(1, 9)}
    # move T_ring under S_ring (swap with first therapist of S6)
    s6_first = groups[6][0]
    for gi, lst in groups.items():
        if T_ring in lst:
            lst[lst.index(T_ring)] = s6_first
    groups[6][0] = T_ring
    sup_of: dict[int, User] = {}
    for si, lst in groups.items():
        for th in lst:
            sup_of[th.id] = S[si]
            db.add(SupervisionAssignment(supervisor_id=S[si].id, supervisee_id=th.id,
                                         effective_from=DATE0 - timedelta(days=60), schedule_every_days=7,
                                         created_by=hr1.id, reason=X["initial"]))
    # one historical reassignment (history preserved, not overwritten)
    old_sup = S[1]
    moved = groups[2][0]
    db.add(SupervisionAssignment(supervisor_id=old_sup.id, supervisee_id=moved.id,
                                 effective_from=DATE0 - timedelta(days=200),
                                 effective_to=DATE0 - timedelta(days=61), reason=X["rebalance"],
                                 created_by=hr1.id))
    db.flush()

    # credentials, contracts, lifecycle ---------------------------------------
    today_ref = date(2026, 11, 20)
    all_staff = ths + sups + cns
    for u in all_staff:
        exp1 = today_ref + timedelta(days=rng.randint(120, 900))
        db.add(Credential(user_id=u.id, kind="license", title=X["license"],
                          number=f"LIC-{u.id:04d}-{rng.randint(1000, 9999)}", issuer=X["issuer1"],
                          issued_on=exp1 - timedelta(days=1095), expires_on=exp1, status="valid"))
        db.add(Credential(user_id=u.id, kind="certification", title=X["cert"],
                          number=f"CERT-{u.id:04d}", issuer=X["issuer2"],
                          issued_on=today_ref - timedelta(days=400),
                          expires_on=today_ref + timedelta(days=rng.randint(20, 700)), status="valid"))
        db.add(Contract(user_id=u.id, kind=rng.choice(["permanent", "fixed_term", "contractor"]),
                        start_date=DATE0 - timedelta(days=rng.randint(100, 900)),
                        end_date=today_ref + timedelta(days=rng.randint(30, 500)) if rng.random() < 0.4 else None,
                        status="active", document_ref=f"DOC-{u.id:05d}"))
        db.add(LifecycleEvent(user_id=u.id, event="onboarded", reason=X["onboarded"],
                              effective_date=DATE0 - timedelta(days=rng.randint(100, 900)), actor_id=hr1.id))
    db.flush()
    # a couple of expiring/expired credentials for the HR dashboard
    exp_cred = Credential.objects.get(user_id=T[2].id, kind="license")
    exp_cred.expires_on = today_ref + timedelta(days=21)
    exp_cred.save()
    exp_cred2 = Credential.objects.get(user_id=T[19].id, kind="certification")
    exp_cred2.expires_on = today_ref - timedelta(days=9)
    exp_cred2.status = "expired"
    exp_cred2.save()
    db.add(LifecycleEvent(user_id=T[20].id, event="suspended", reason=X["susp"],
                          effective_date=DATE0 + timedelta(days=14), actor_id=hr1.id))
    db.add(LifecycleEvent(user_id=T[20].id, event="reactivated", reason=X["react"],
                          effective_date=DATE0 + timedelta(days=35), actor_id=hr1.id))
    db.flush()

    # ---------------------------------------------------------------- clients (pseudonymous)
    needs = SPECIALIZATIONS
    clients = []
    for i in range(1, 361):
        cl = Client(client_ref=f"C-{i:04d}", primary_need=rng.choice(needs))
        db.add(cl)
        clients.append(cl)
    db.flush()
    by_need: dict[str, list[Client]] = {n: [c for c in clients if c.primary_need == n] for n in needs}

    # ---------------------------------------------------------------- sessions
    sess_rows: list[Session] = []
    week_start = lambda w: DATE0 + timedelta(days=7 * w)  # noqa: E731

    def add_session(prac: User, cl: Client, start: datetime, status="completed", mode="online", loc=None,
                    dur=50, group_id=None, reported=None, checkin=True, ci_span=None, mods=0) -> Session:
        end = start + timedelta(minutes=dur)
        s = Session(practitioner_id=prac.id, client_id=cl.id, group_id=group_id, scheduled_start=start,
                    scheduled_end=end, status=status, mode=mode, location_code=loc, modification_count=mods,
                    last_modified_at=start - timedelta(hours=rng.randint(2, 40)) if mods else None,
                    created_at=start - timedelta(days=rng.randint(2, 14)))
        if status == "completed":
            if checkin:
                ci = start + timedelta(minutes=max(0, round(rng.gauss(1.5, 2))))
                span = ci_span if ci_span is not None else max(40, round(rng.gauss(dur, 2)))
                s.checkin_at, s.checkout_at = ci, ci + timedelta(minutes=span)
            s.reported_duration_min = reported if reported is not None else dur
        sess_rows.append(s)
        return s

    def week_slots(prac: User, w: int, n: int, step: int = 60) -> list[datetime]:
        slots = []
        days = [week_start(w) + timedelta(days=d) for d in range(5)]
        pool = [(d, k) for d in days for k in range(8)]
        rng.shuffle(pool)
        for d, k in sorted(pool[:n]):
            slots.append(_dt(d, 9) + timedelta(minutes=k * step))
        return slots

    loc_of = {t.id: f"LOC-{(i % 6) + 1}" for i, t in enumerate(ths)}
    for t in ths:
        cap = caps[t.id]
        for w in range(N_WEEKS):
            if t is T_busy:
                n = 33
            elif t is T_group:
                n = int(cap * rng.uniform(0.55, 0.75))
            else:
                n = int(cap * rng.uniform(0.55, 0.8))
            # anomaly: cancel/mod surge for T_cancel in the last 4 weeks
            step = 50 if t is T_b2b else 60
            for start in week_slots(t, w, min(n, 40), step):
                cl = rng.choice(clients)
                r = rng.random()
                recent = w >= N_WEEKS - 4
                if t is T_cancel and recent:
                    status = "cancelled" if r < 0.38 else "completed"
                    mods = 0 if rng.random() < 0.40 else rng.randint(2, 4)
                else:
                    status = "completed" if r < 0.86 else ("cancelled" if r < 0.94 else "no_show")
                    mods = 1 if rng.random() < 0.04 else 0
                mode = "in_person" if rng.random() < 0.3 else "online"
                reported, ci_span, checkin = None, None, True
                if t is T_inflate and w >= N_WEEKS - 5 and status == "completed":
                    x = rng.random()
                    if x < 0.45:
                        ci_span, reported = rng.randint(22, 30), 50       # reports 50 min, was present ~26
                    elif x < 0.57:
                        checkin = False                                      # completed w/o any check-in
                add_session(t, cl, start, status, mode, loc_of[t.id] if mode == "in_person" else None,
                            reported=reported, ci_span=ci_span, checkin=checkin, mods=mods)

    # hard negative: group sessions (same interval, same group_id, multiple clients) for T_group
    for w in range(N_WEEKS):
        for d in (1, 3):
            start = _dt(week_start(w) + timedelta(days=d), 17)  # 17:00 – outside normal slots
            gid = f"GRP-{T_group.id}-{w}-{d}"
            for _ in range(4):
                add_session(T_group, rng.choice(clients), start, "completed", "in_person", loc_of[T_group.id],
                            group_id=gid)

    # anomaly A1: T_overlap – overlapping & physically impossible sessions (last 3 weeks)
    gt_overlap_pairs = []
    for k, w in enumerate([9, 9, 10, 10, 10, 11, 11]):
        d = week_start(w) + timedelta(days=k % 5)
        start1 = _dt(d, 14 if k % 2 else 10)
        impossible = k % 2 == 0
        a = add_session(T_overlap, rng.choice(clients), start1, "completed", "in_person", "LOC-1")
        b = add_session(T_overlap, rng.choice(clients), start1 + timedelta(minutes=rng.choice([15, 20, 25, 30])),
                        "completed", "in_person" if impossible else "online", "LOC-5" if impossible else None)
        gt_overlap_pairs.append((a, b))

    db.add_all(sess_rows)
    db.flush()

    # a few future scheduled sessions for dashboards
    fut = []
    for t in ths:
        for k in range(3):
            d = date(2026, 11, 23) + timedelta(days=rng.randint(0, 4))
            fut.append(Session(practitioner_id=t.id, client_id=rng.choice(clients).id,
                               scheduled_start=_dt(d, 9 + k * 2), scheduled_end=_dt(d, 9 + k * 2, 50),
                               status="scheduled", mode="online", created_at=datetime(2026, 11, 18, 10)))
    db.add_all(fut)
    db.flush()

    # ---------------------------------------------------------------- referrals
    by_spec: dict[str, list[User]] = {n: [t for i, t in enumerate(ths) if SPEC_PLAN[i] == n] for n in needs}
    refs: list[Referral] = []

    def eligible(need: str) -> list[User]:
        return by_spec[need]

    def pick(need: str) -> User:
        el = eligible(need)
        return rng.choices(el, weights=[caps[t.id] for t in el], k=1)[0]

    conc_pair = [T[1 + 2], T[18]]  # T3, T18 – mismatched specialisations most of the time
    counselor_need_weights = {c.id: [rng.uniform(0.7, 1.3) for _ in needs] for c in cns}
    for c in cns:
        for w in range(N_WEEKS):
            for _ in range(12):
                day = week_start(w) + timedelta(days=rng.randint(0, 4))
                when = _dt(day, rng.randint(8, 17), rng.randint(0, 59))
                if c is C_spec:
                    need = "trauma"
                elif c is C_ring:
                    need = "anxiety" if rng.random() < 0.6 else rng.choice(needs)
                else:
                    need = rng.choices(needs, weights=counselor_need_weights[c.id], k=1)[0]
                cl = rng.choice(by_need[need])
                recent = w >= N_WEEKS - 6
                if c is C_conc and recent and rng.random() < 0.82:
                    to = rng.choice(conc_pair)
                elif c is C_ring and recent and need == "anxiety" and rng.random() < 0.92:
                    to = T_ring
                elif c is C_spec:
                    to = pick("trauma") if rng.random() < 0.97 else rng.choice(ths)
                else:
                    to = pick(need)
                refs.append(Referral(from_user_id=c.id, to_practitioner_id=to.id, client_id=cl.id, need=need,
                                     created_at=when))
    db.add_all(refs)
    db.flush()

    # ---------------------------------------------------------------- reviews (supervision)
    reviews: list[Review] = []
    comp_sessions: dict[int, list[Session]] = {}
    for s in sess_rows:
        if s.status == "completed" and s.checkin_at is not None:
            comp_sessions.setdefault(s.practitioner_id, []).append(s)
    used: set[int] = set()

    def mk_review(sup: User, sub: User, sess: Session, decided: datetime | None, minutes=None, doc=True,
                  outcome="approved", due: date | None = None, status=None) -> Review:
        used.add(sess.id)
        r = Review(supervisor_id=sup.id, supervisee_id=sub.id, session_id=sess.id, case_ref=f"CASE-{sess.id:06d}",
                   status=status or (outcome if decided else "pending"),
                   due_date=due or (sess.scheduled_start.date() + timedelta(days=7)),
                   opened_at=sess.scheduled_end + timedelta(hours=2), decided_at=decided,
                   decision_minutes=minutes, has_documentation=doc,
                   supervision_notes=X["notes"] if decided and doc else None,
                   feedback=X["good"] if outcome == "approved" and decided else (
                       X["fix"] if decided else None),
                   performance_score=rng.randint(3, 5) if decided else None)
        reviews.append(r)
        return r

    for th in ths:
        sup = sup_of[th.id]
        pool = [s for s in comp_sessions.get(th.id, []) if s.scheduled_start.date() < date(2026, 11, 17)]
        rng.shuffle(pool)
        for w in range(N_WEEKS - 1):
            wk = [s for s in pool if week_start(w) <= s.scheduled_start.date() < week_start(w + 1) and s.id not in used]
            for s in wk[:3]:
                decided = s.scheduled_end + timedelta(days=rng.randint(1, 4), hours=rng.randint(0, 6))
                doc = rng.random() > 0.04
                outcome = "approved" if rng.random() < 0.82 else "needs_changes"
                minutes = max(4.0, rng.gauss(14, 4))
                if sup is S_ring and th is T_ring and w >= 3:
                    outcome, minutes, doc = "approved", max(5.0, rng.gauss(6.5, 1.0)), True  # ring: lax-but-documented
                mk_review(sup, th, s, decided, round(minutes, 1), doc, outcome)
    # pending / overdue reviews in the latest week
    for th in ths:
        pool = [s for s in comp_sessions.get(th.id, []) if s.id not in used and s.scheduled_start.date() >= date(2026, 11, 9)]
        for s in pool[:2]:
            overdue = rng.random() < 0.35
            mk_review(sup_of[th.id], th, s, None, None, False, "pending",
                      due=date(2026, 11, 18) if overdue else date(2026, 11, 27),
                      status="pending" if rng.random() < 0.6 else "in_progress")
    # anomaly C: S_rubber – mass approval in the last 2 days, rapid, 45% without documentation
    rub_supervisees = [t for t in ths if sup_of[t.id] is S_rubber]
    backlog = [s for t in rub_supervisees for s in comp_sessions.get(t.id, []) if s.id not in used]
    rng.shuffle(backlog)
    for i, s in enumerate(backlog[:58]):
        decided = datetime(2026, 11, 18, 9, 0) + timedelta(minutes=rng.randint(0, 1800))
        mk_review(S_rubber, next(t for t in ths if t.id == s.practitioner_id), s, decided,
                  round(max(0.4, rng.gauss(1.2, 0.4)), 1), doc=rng.random() > 0.45, outcome="approved",
                  due=s.scheduled_start.date() + timedelta(days=7))
    # hard negative: S_busy – legit end-of-quarter volume, complete docs, normal time on task
    busy_supervisees = [t for t in ths if sup_of[t.id] is S_busy]
    backlog2 = [s for t in busy_supervisees for s in comp_sessions.get(t.id, []) if s.id not in used]
    rng.shuffle(backlog2)
    for s in backlog2[:42]:
        decided = datetime(2026, 11, 17, 8, 0) + timedelta(minutes=rng.randint(0, 2200))
        mk_review(S_busy, next(t for t in ths if t.id == s.practitioner_id), s, decided,
                  round(max(6.0, rng.gauss(13, 3)), 1), doc=True,
                  outcome="approved" if rng.random() < 0.85 else "needs_changes",
                  due=s.scheduled_start.date() + timedelta(days=7))
    db.add_all(reviews)
    db.flush()

    # corrective actions & quality issues for supervisor dashboards
    for r in [x for x in reviews if x.status == "needs_changes"][:25]:
        if rng.random() < 0.6:
            db.add(CorrectiveAction(review_id=r.id, description=X["action"],
                                    assigned_to=r.supervisee_id, due_date=(r.decided_at + timedelta(days=10)).date(),
                                    status="open" if rng.random() < 0.5 else "completed",
                                    completed_at=r.decided_at + timedelta(days=4) if rng.random() < 0.5 else None))
    for th in rng.sample(ths, 6):
        db.add(QualityIssue(practitioner_id=th.id, supervisor_id=sup_of[th.id].id,
                            category=rng.choice(["operational", "clinical"]),
                            title=rng.choice(X["issues"]),
                            severity=rng.choice(["low", "medium", "high"]), status="open",
                            created_at=datetime(2026, 11, rng.randint(2, 18), 10)))
    # supervision meetings (participation)
    for th in ths:
        for w in range(N_WEEKS):
            st = rng.random()
            db.add(SupervisionMeeting(supervisor_id=sup_of[th.id].id, supervisee_id=th.id,
                                      scheduled_at=_dt(week_start(w) + timedelta(days=rng.randint(0, 4)), 13),
                                      status="completed" if st < 0.85 else "missed"))
    db.flush()

    # ---------------------------------------------------------------- security: access & admin activity
    acc: list[AccessEvent] = []
    for u in [admin, admin2, hr1, hr2, comp1, comp2] + sups + ths + cns:
        for w in range(N_WEEKS):
            for _ in range(rng.randint(2, 4)):
                day = week_start(w) + timedelta(days=rng.randint(0, 4))
                acc.append(AccessEvent(ts=_dt(day, rng.randint(7, 17), rng.randint(0, 59)), user_id=u.id,
                                       email_attempted=u.email, event="login_ok", ip=f"10.0.{rng.randint(0, 9)}.{rng.randint(2, 250)}"))
    noise_users = rng.sample(ths + cns + sups, 25)
    for u in noise_users:  # isolated typos: far below any burst threshold
        day = week_start(rng.randint(0, 11)) + timedelta(days=rng.randint(0, 4))
        acc.append(AccessEvent(ts=_dt(day, rng.randint(7, 17), rng.randint(0, 59)), user_id=u.id,
                               email_attempted=u.email, event="login_failed", ip="10.0.1.77"))
    for u in rng.sample(ths, 4):  # isolated, legitimate denials (one-off)
        day = week_start(rng.randint(0, 10)) + timedelta(days=rng.randint(0, 4))
        acc.append(AccessEvent(ts=_dt(day, 11, 5), user_id=u.id, event="access_denied", resource_type="hr",
                               permission="hr:read", path="/hr/practitioners", ip="10.0.2.4"))
    # anomaly D1: admin2 out-of-scope attempts (2026-11-19 15:10-15:35)
    base = datetime(2026, 11, 19, 15, 10)
    for k, (res, perm, path) in enumerate([
            ("clinical", "clinical:read:supervisees", "/clinical/practitioners/5/sessions"),
            ("clinical", "clinical:read:supervisees", "/clinical/practitioners/6/sessions"),
            ("clinical", "clinical:read:supervisees", "/clinical/practitioners/7/sessions"),
            ("clinical", "clinical:read:supervisees", "/clinical/practitioners/9/sessions"),
            ("hr", "hr:write", "/hr/practitioners/9/contracts"),
            ("hr", "hr:write", "/hr/credentials/12"),
            ("supervision", "supervision:read", "/supervision/reviews"),
            ("clinical", "clinical:read:supervisees", "/clinical/practitioners/11/sessions"),
            ("hr", "hr:write", "/hr/practitioners/9/lifecycle/terminate")]):
        acc.append(AccessEvent(ts=base + timedelta(minutes=k * 3), user_id=admin2.id, event="access_denied",
                               resource_type=res, permission=perm, path=path, ip="10.0.9.9"))
    # anomaly D3: brute force on T_attacked + credential-stuffing IP across several accounts
    atk_ip = "203.0.113.50"
    t0 = datetime(2026, 11, 20, 2, 12)
    for k in range(14):
        acc.append(AccessEvent(ts=t0 + timedelta(minutes=k), user_id=T_attacked.id, email_attempted=T_attacked.email,
                               event="login_failed", ip=atk_ip if k % 3 else "198.51.100.23"))
    for other in (CN[5], CN[6], T[20], T[21]):
        for k in range(2):
            acc.append(AccessEvent(ts=t0 + timedelta(minutes=16 + k), user_id=other.id, email_attempted=other.email,
                                   event="login_failed", ip=atk_ip))
    db.add_all(acc)

    adm: list[AdminActivity] = []
    for w in range(N_WEEKS):  # normal HR admin (hr1): 1-3 edits per working day
        for d in range(5):
            for _ in range(rng.randint(0, 3)):
                tgt = rng.choice(ths + sups + cns)
                adm.append(AdminActivity(ts=_dt(week_start(w) + timedelta(days=d), rng.randint(9, 16), rng.randint(0, 59)),
                                         actor_id=hr1.id, target_user_id=tgt.id,
                                         action=rng.choice(["credential_edit", "contract_edit", "profile_edit", "assignment_edit"]),
                                         detail={"summary": X["routine"]}))
    for w in range(N_WEEKS):  # normal platform admin (admin): a few account/status ops
        if rng.random() < 0.5:
            tgt = rng.choice(ths)
            adm.append(AdminActivity(ts=_dt(week_start(w) + timedelta(days=rng.randint(0, 4)), 10, 30),
                                     actor_id=admin.id, target_user_id=tgt.id, action="status_change",
                                     detail={"summary": X["reset"]}))
    # anomaly D2: hr2 credential-edit burst (14 edits in 40 min) + contract edits
    hb = datetime(2026, 11, 19, 22, 5)
    for k in range(14):
        tgt = ths[(k * 2) % 24]
        adm.append(AdminActivity(ts=hb + timedelta(minutes=k * 3), actor_id=hr2.id, target_user_id=tgt.id,
                                 action="credential_edit", detail={"summary": X["expiry"], "field": "expires_on"}))
    for k in range(4):
        adm.append(AdminActivity(ts=hb + timedelta(minutes=45 + k), actor_id=hr2.id, target_user_id=ths[k].id,
                                 action="contract_edit", detail={"summary": X["enddate"]}))
    # anomaly D1b: admin2 suspicious account creation burst + privilege grants
    new_users = []
    for k, role in enumerate([Role.COMPLIANCE_REVIEWER, Role.CLINICAL_SUPERVISOR, Role.HR_ADMIN]):
        nu = mk_user(f"temp.account{k + 1}@aramana.test", role, X["temp"].format(k + 1), status=UserStatus.PENDING,
                     created_by=admin2.id, created_at=datetime(2026, 11, 19, 14, 40 + k * 3))
        new_users.append(nu)
        adm.append(AdminActivity(ts=datetime(2026, 11, 19, 14, 40 + k * 3), actor_id=admin2.id, target_user_id=nu.id,
                                 action="account_create", detail={"role": role}))
        adm.append(AdminActivity(ts=datetime(2026, 11, 19, 14, 42 + k * 3), actor_id=admin2.id, target_user_id=nu.id,
                                 action="role_change", detail={"from": "therapist", "to": role}))
    db.add_all(adm)
    db.flush()

    # audit-chain entries for seeded admin activity (so the chain is non-trivial)
    for a in sorted(adm, key=lambda x: x.ts)[-60:]:
        audit(a.actor_id, a.action, "user", a.target_user_id, ts=a.ts.replace(tzinfo=UTC), **(a.detail or {}))

    db.flush()

    # ---------------------------------------------------------------- ground truth
    uid = lambda u: u.id  # noqa: E731
    gt = {
        "seed": seed,
        "anomalies": [
            {"category": "A", "scenario": "session_overlap", "users": [uid(T_overlap)]},
            {"category": "A", "scenario": "duration_discrepancy", "users": [uid(T_inflate)]},
            {"category": "A", "scenario": "cancellation_pattern", "users": [uid(T_cancel)]},
            {"category": "B", "scenario": "referral_concentration", "users": [uid(C_conc), uid(C_ring)]},
            {"category": "C", "scenario": "approval_burst", "users": [uid(S_rubber)]},
            {"category": "D", "scenario": "admin_out_of_scope", "users": [uid(admin2)]},
            {"category": "D", "scenario": "admin_modification_burst", "users": [uid(hr2)]},
            {"category": "D", "scenario": "failed_login_burst", "users": [uid(T_attacked)]},
            {"category": "D", "scenario": "multi_account_ip", "users": [uid(T_attacked), uid(CN[5]), uid(CN[6]), uid(T[20]), uid(T[21])]},
            {"category": "E", "scenario": "referral_approval_ring", "users": [uid(C_ring), uid(T_ring), uid(S_ring)]},
        ],
        "hard_negatives": [
            {"scenario": "busy_but_legit_therapist", "users": [uid(T_busy)]},
            {"scenario": "group_sessions", "users": [uid(T_group)]},
            {"scenario": "back_to_back_sessions", "users": [uid(T_b2b)]},
            {"scenario": "specialisation_unit_concentration", "users": [uid(C_spec)]},
            {"scenario": "legit_high_volume_supervisor", "users": [uid(S_busy)]},
            {"scenario": "normal_hr_admin", "users": [uid(hr1)]},
            {"scenario": "normal_platform_admin", "users": [uid(admin)]},
        ],
        "roles": {"T_overlap": uid(T_overlap), "T_inflate": uid(T_inflate), "T_cancel": uid(T_cancel),
                  "C_conc": uid(C_conc), "C_spec": uid(C_spec), "C_ring": uid(C_ring), "T_ring": uid(T_ring),
                  "S_rubber": uid(S_rubber), "S_busy": uid(S_busy), "S_ring": uid(S_ring),
                  "admin2": uid(admin2), "hr2": uid(hr2), "T_attacked": uid(T_attacked)},
    }
    if ground_truth_path:
        p = Path(ground_truth_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(gt, indent=2))
    return gt
