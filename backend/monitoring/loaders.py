"""Adapter (Dependency Inversion): turns Django ORM rows into the DataFrames the framework-free detection package consumes."""
import pandas as pd

from accounts.models import User
from clinical.models import Referral, Session
from core.models import AccessEvent, AdminActivity
from detection.data import Data
from hr.models import PractitionerProfile
from supervision.models import Review


def frame(qs, columns: list[str], datetimes: tuple = ()) -> pd.DataFrame:
    df = pd.DataFrame.from_records(qs.values(*columns), columns=columns)
    for c in datetimes:   # detection works on naive UTC timestamps
        df[c] = pd.to_datetime(df[c], utc=True).dt.tz_convert(None)
    return df


def load_data() -> Data:
    users = frame(User.objects.all(), ["id", "role", "status", "full_name"])
    profiles = frame(PractitionerProfile.objects.all(), ["user_id", "specialization", "capacity_weekly_sessions"])
    sessions = frame(Session.objects.all(), ["id", "practitioner_id", "client__client_ref", "group_id", "scheduled_start", "scheduled_end", "status", "mode",
                                             "location_code", "reported_duration_min", "checkin_at", "checkout_at", "modification_count"],
                     ("scheduled_start", "scheduled_end", "checkin_at", "checkout_at")).rename(columns={"client__client_ref": "client_ref"})
    referrals = frame(Referral.objects.all(), ["id", "from_user_id", "to_practitioner_id", "need", "created_at"], ("created_at",))
    reviews = frame(Review.objects.all(), ["id", "supervisor_id", "supervisee_id", "case_ref", "status", "decided_at", "decision_minutes", "has_documentation"], ("decided_at",))
    access = frame(AccessEvent.objects.all(), ["id", "ts", "user_id", "event", "resource_type", "permission", "path", "ip"], ("ts",))
    admin = frame(AdminActivity.objects.all(), ["id", "ts", "actor_id", "action", "target_user_id", "detail"], ("ts",))
    stamps = [sessions.loc[sessions.status != "scheduled", "scheduled_end"].max(), reviews.decided_at.max(), access.ts.max(), admin.ts.max(), referrals.created_at.max()]
    return Data(users, profiles, sessions, referrals, reviews, access, admin, pd.Timestamp(max(s for s in stamps if pd.notna(s))),
                names=dict(zip(users.id, users.full_name)), roles=dict(zip(users.id, users.role)))
