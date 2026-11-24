"""Localisation kernel (Persian `fa` / English `en`).

* the request language lives in a ContextVar (set by `core.middleware.LanguageMiddleware` from `Accept-Language`)
* TERMS: one flat token -> Persian dictionary for every enum / action / evidence key the UI shows (served to the frontend by /api/meta/labels)
* translate(): API error messages (exact + templates), applied centrally by the exception handler
The database always stores canonical English; text is localised only when presented.
"""
from __future__ import annotations

import re
from contextvars import ContextVar

from detection import i18n as det

_lang: ContextVar[str] = ContextVar("lang", default="en")
SUPPORTED = ("fa", "en")


def lang() -> str:
    return _lang.get()


def set_lang(value: str):
    return _lang.set(value if value in SUPPORTED else "en")


def parse_accept_language(header: str | None) -> str:
    first = (header or "").split(",")[0].strip().lower()
    return "fa" if first.startswith("fa") else "en"


TERMS = {
    # roles
    "platform_admin": "مدیر پلتفرم", "hr_admin": "مدیر منابع انسانی", "clinical_supervisor": "سوپروایزر بالینی", "therapist": "درمانگر",
    "assistant_counselor": "مشاور کمکی", "compliance_reviewer": "بازبین انطباق",
    # user / contract / credential / employment statuses
    "active": "فعال", "pending_onboarding": "در انتظار جذب", "suspended": "تعلیق‌شده", "terminated": "خاتمه‌یافته", "draft": "پیش‌نویس", "ended": "پایان‌یافته",
    "valid": "معتبر", "expired": "منقضی", "revoked": "ابطال‌شده", "pending": "در انتظار", "license": "پروانه", "certification": "گواهی", "degree": "مدرک تحصیلی",
    "permanent": "دائمی", "fixed_term": "مدت‌دار", "contractor": "پیمانکار", "volunteer": "داوطلب", "employee": "کارمند",
    # alerts
    "new": "جدید", "under_review": "در حال بررسی", "info_requested": "اطلاعات درخواست‌شده", "escalated": "ارجاع‌شده", "false_positive": "مثبت کاذب",
    "closed_substantiated": "بسته – اثبات‌شده", "closed_no_action": "بسته – بدون اقدام",
    "low": "کم", "medium": "متوسط", "high": "بالا", "critical": "بحرانی",
    "operational": "عملیاتی", "clinical": "بالینی", "misconduct": "تخلف بالقوه", "security": "امنیتی", "supervision": "نظارت", "hr": "منابع انسانی",
    "rule": "قاعده", "statistical": "آماری", "ml": "یادگیری ماشین", "graph": "گراف", "manual": "دستی",
    "template": "قالب قطعی", "template(fallback)": "قالب قطعی (جایگزین)", "groq": "Groq", "gemini": "Gemini", "ollama": "Ollama",
    # sessions / reviews / issues / meetings
    "scheduled": "زمان‌بندی‌شده", "completed": "انجام‌شده", "cancelled": "لغوشده", "no_show": "غیبت", "online": "آنلاین", "in_person": "حضوری",
    "in_progress": "در جریان", "needs_changes": "نیازمند اصلاح", "approved": "تأییدشده", "open": "باز", "resolved": "حل‌شده", "missed": "غایب",
    "trauma": "تروما", "anxiety": "اضطراب", "depression": "افسردگی", "couples": "زوج‌درمانی", "child": "کودک", "addiction": "اعتیاد",
    # workflow / activity / audit actions
    "start_review": "شروع بررسی", "assign": "واگذاری", "comment": "یادداشت", "request_info": "درخواست اطلاعات", "provide_info": "ثبت اطلاعات دریافتی",
    "escalate": "ارجاع", "close_no_action": "بستن – بدون اقدام", "close_substantiated": "بستن – اثبات‌شده", "reopen": "بازگشایی",
    "activate": "فعال‌سازی", "suspend": "تعلیق", "reactivate": "بازگشت به کار", "terminate": "خاتمه‌ی همکاری",
    "created": "ایجاد شد", "viewed": "مشاهده شد", "rescored": "امتیاز به‌روزرسانی شد", "assigned": "واگذار شد", "routed_to_supervisor": "به سوپروایزر ارجاع شد",
    "ai_assistant": "دستیار هوش مصنوعی", "ai_summary": "خلاصه‌ی هوش مصنوعی", "onboarding_started": "آغاز جذب", "onboarded": "جذب شد", "reactivated": "بازگشت به کار",
    "supervision_review": "بازبینی نظارتی", "supervisor_assigned": "سوپروایزر تعیین شد", "supervisor_reassigned": "سوپروایزر تغییر کرد",
    "login": "ورود", "login_ok": "ورود موفق", "login_failed": "ورود ناموفق", "access_denied": "دسترسی ردشده", "alert_access_denied": "دسترسی ردشده به هشدار",
    "alert_view": "مشاهده‌ی هشدار", "alert_ai_briefing": "خلاصه‌ی هوش مصنوعی هشدار", "alert_ai_answer": "پرسش از دستیار هوش مصنوعی", "alert_route_to_supervisor": "ارجاع هشدار به سوپروایزر",
    **{f"alert_{a}": v for a, v in {"start_review": "شروع بررسی هشدار", "assign": "واگذاری هشدار", "comment": "یادداشت روی هشدار", "request_info": "درخواست اطلاعات برای هشدار",
                                    "provide_info": "ثبت اطلاعات هشدار", "escalate": "ارجاع هشدار", "false_positive": "علامت مثبت کاذب", "close_no_action": "بستن هشدار – بدون اقدام",
                                    "close_substantiated": "بستن هشدار – اثبات‌شده", "reopen": "بازگشایی هشدار"}.items()},
    "account_create": "ساخت حساب", "role_change": "تغییر نقش", "status_change": "تغییر وضعیت", "self_role_change_blocked": "تغییر نقش خود مسدود شد",
    "profile_edit": "ویرایش پروفایل", "credential_edit": "ویرایش مدرک", "contract_edit": "ویرایش قرارداد", "assignment_edit": "ویرایش انتساب", "clinical_read": "خواندن داده‌ی بالینی",
    "corrective_action_assign": "تعیین اقدام اصلاحی", "corrective_action_completed": "اقدام اصلاحی انجام شد", "corrective_action_cancelled": "اقدام اصلاحی لغو شد",
    "detection_run": "اجرای تشخیص", "meeting_schedule": "زمان‌بندی جلسه‌ی نظارت", "meeting_update": "به‌روزرسانی جلسه‌ی نظارت",
    "quality_issue_create": "ثبت مسئله‌ی کیفیت", "quality_issue_escalate": "ارجاع مسئله‌ی کیفیت", "quality_issue_resolve": "حل مسئله‌ی کیفیت", "referral_create": "ثبت ارجاع",
    "review_close": "بستن بازبینی", "review_create": "ایجاد بازبینی", "review_decision": "تصمیم بازبینی", "review_start": "شروع بازبینی", "review_view": "مشاهده‌ی بازبینی",
    "session_checkout": "ثبت خروج", "session_checkin": "ثبت ورود", "session_create": "ایجاد جلسه", "session_update": "به‌روزرسانی جلسه", "supervisee_view": "مشاهده‌ی زیردست",
    "review_approved": "بازبینی تأیید شد", "review_needs_changes": "بازبینی نیازمند اصلاح", "review_pending": "بازبینی در انتظار", "review_in_progress": "بازبینی در جریان",
    "meeting_completed": "جلسه‌ی نظارت انجام شد", "meeting_missed": "جلسه‌ی نظارت از دست رفت", "meeting_scheduled": "جلسه‌ی نظارت زمان‌بندی شد",
    "ok": "موفق", "denied": "ردشده",
    # evidence types
    "approval": "تأیید", "approval_edge": "یال تأیید", "duration_mismatch": "ناهمخوانی مدت", "graph_cluster": "خوشه‌ی گراف", "ml_feature_contribution": "سهم ویژگی‌ها در مدل ML",
    "peer_comparison": "مقایسه با همتایان", "referral_distribution": "توزیع ارجاع", "referral_edge": "یال ارجاع", "session_overlap": "هم‌پوشانی جلسه", "volume": "حجم",
    "quality_issue": "مسئله‌ی کیفیت", "daily_hours": "ساعات روزانه",
    # evidence keys
    "a_end": "پایان (الف)", "a_loc": "مکان (الف)", "a_mode": "نوع (الف)", "a_start": "شروع (الف)", "a_status": "وضعیت (الف)", "b_end": "پایان (ب)", "b_loc": "مکان (ب)",
    "b_mode": "نوع (ب)", "b_start": "شروع (ب)", "b_status": "وضعیت (ب)", "case_ref": "شناسه‌ی پرونده", "client_a": "مراجع (الف)", "client_b": "مراجع (ب)", "client_ref": "مراجع",
    "cluster_density": "چگالی خوشه", "cohort_median": "میانه‌ی گروه", "component_size": "اندازه‌ی مؤلفه", "counselor": "مشاور", "decided_at": "زمان تصمیم", "detail": "جزئیات",
    "feature": "ویژگی", "has_documentation": "دارای مستندات", "impossible": "ناممکن", "in_share": "سهم ورودی", "ip": "نشانی IP", "lift": "lift", "median_minutes": "میانه‌ی دقیقه‌ها",
    "minutes": "دقیقه", "n": "تعداد", "others_rate": "نرخ سایرین", "out_share": "سهم خروجی", "overlap_min": "دقیقه‌ی هم‌پوشانی", "path": "مسیر", "permission": "مجوز",
    "policy_expected_share": "سهم مورد انتظار از سیاست", "practitioner_id": "شناسه‌ی متخصص", "referrals": "ارجاع‌ها", "reported_min": "دقیقه‌ی گزارش‌شده", "review": "بازبینی",
    "robust_z": "z مقاوم", "role": "نقش", "session": "جلسه", "session_a": "جلسه (الف)", "session_b": "جلسه (ب)", "share": "سهم", "specialisation": "تخصص", "start": "شروع",
    "supervisee": "زیردست", "supervisor": "سوپروایزر", "target_user": "کاربر هدف", "therapist": "درمانگر", "to": "به", "ts": "زمان", "user": "کاربر", "value": "مقدار",
    "verified_span_min": "بازه‌ی راستی‌آزمایی‌شده (دقیقه)", "day": "روز", "issue_id": "شناسه‌ی مسئله", "category": "دسته", "severity": "شدت", "decisions_in_window": "تصمیم‌ها در بازه",
    "op": "عملیات", "record": "رکورد", "summary": "خلاصه", "field": "فیلد", "after": "پس از", "before": "پیش از", "from": "از", "action": "اقدام", "reason": "دلیل", "new_status": "وضعیت جدید",
    # form fields (validation messages)
    "email": "ایمیل", "password": "رمز عبور", "full_name": "نام کامل", "note": "یادداشت", "notes": "یادداشت‌ها", "feedback": "بازخورد", "question": "پرسش", "title": "عنوان",
    "due_date": "سررسید", "start_date": "تاریخ شروع", "end_date": "تاریخ پایان", "number": "شماره", "kind": "نوع", "description": "شرح", "monitoring_plan": "طرح پایش",
    "performance_score": "امتیاز عملکرد", "initial_password": "رمز اولیه", "specialization": "تخصص", "status": "وضعیت", "scheduled_start": "زمان شروع", "duration_min": "مدت (دقیقه)",
    "scheduled_at": "زمان", "supervisee_id": "زیردست", "supervisor_id": "سوپروایزر", "outcome": "نتیجه", "expires_on": "تاریخ انقضا",
    "effective_from": "اعتبار از", "to_practitioner_id": "متخصص مقصد", "need": "نیاز", "mode": "نوع جلسه", "location_code": "مکان", "capacity_weekly_sessions": "ظرفیت هفتگی",
    "minutes_spent": "دقایق صرف‌شده", "assign_to": "واگذاری به", "non_field_errors": "خطا",
    # misc UI vocabulary shared with the backend
    "status_unknown": "نامشخص", "none": "هیچ", "yes": "بله", "no": "خیر", "system": "سامانه",
}
TERMS.update({k: v["name"] for k, v in det.SCENARIOS.items()})
TERMS.update({
    "overlap_pairs": "جفت‌جلسه‌های هم‌پوشان", "impossible_location": "مکان فیزیکاً ناممکن", "completed_overlap": "هم‌پوشانی جلسه‌های انجام‌شده", "excessive_daily_hours": "ساعات روزانه‌ی بیش‌ازحد",
    "inflated_duration_share": "سهم مدت بی‌پشتوانه", "no_checkin_share": "جلسه‌ی انجام‌شده بدون ورود", "referral_concentration_p": "مقدار p تمرکز ارجاع", "referral_js_divergence": "واگرایی ینسن–شانون ارجاع",
    "referral_top2_excess": "مازاد دو متخصص برتر", "referral_spec_mismatch": "ناهمخوانی تخصصِ ارجاع", "approvals_missing_docs": "تأیید بدون مستندات", "rapid_approvals": "تأیید سریع",
    "approval_burst": "انفجار تأیید", "denied_access_burst": "انفجار دسترسی ردشده", "scope_probing": "کاوش دامنه", "account_creation_burst": "انفجار ساخت حساب", "privilege_grants": "اعطای دسترسی ویژه",
    "admin_modification_burst": "انفجار ویرایش مدیریتی", "failed_login_burst": "انفجار ورود ناموفق", "multi_account_ip": "یک نشانی، چند حساب", "exclusive_referral_dependency": "وابستگی انحصاری ارجاع",
    "lax_approval_edge": "تأیید بی‌قیدوشرط", "peer_outlier_rate": "پرتِ نرخی نسبت به همتایان", "peer_outlier_volume": "پرتِ حجمی نسبت به همتایان", "ml_isolation_forest": "Isolation Forest",
})
CATEGORY = {"A": "مرتبط با درمانگر", "B": "مرتبط با مشاور کمکی", "C": "مرتبط با سوپروایزر", "D": "مدیریتی / پلتفرمی", "E": "بین‌کاربری / شبکه‌ای", "Q": "ارجاع سوپروایزر"}
ROLE_DESCRIPTIONS = {
    "platform_admin": "حساب‌ها، نقش‌ها و پیکربندی پلتفرم را مدیریت می‌کند. به محتوای سوابق منابع انسانی و داده‌ی بالینی دسترسی ندارد.",
    "hr_admin": "پروفایل متخصصان، مدارک، قراردادها، چرخه‌ی حیات و ساختار سازمانی را مدیریت می‌کند. به داده‌ی بالینی دسترسی ندارد.",
    "clinical_supervisor": "بر متخصصانِ تحت نظارت خود نظارت می‌کند: بازبینی، بازخورد، اقدام اصلاحی و ارجاع.",
    "therapist": "جلسه برگزار می‌کند؛ جلسه‌ها، بازبینی‌ها و اقدام‌های اصلاحیِ خودش را می‌بیند.",
    "assistant_counselor": "ارجاع ثبت می‌کند؛ فقط ارجاع‌های خودش را می‌بیند.",
    "compliance_reviewer": "هشدارها را در همه‌ی حوزه‌ها بررسی می‌کند؛ دسترسی فقط‌خواندنیِ شواهد، محدود به موضوعِ هشدارها.",
}
TERMS.update({   # permission tokens shown on the roles page
    "alerts:comment": "ثبت یادداشت روی هشدار", "alerts:investigate": "تحقیق روی هشدار", "alerts:read": "مشاهده‌ی هشدارها", "audit:read": "مشاهده‌ی حسابرسی",
    "clinical:read:alerted": "خواندن داده‌ی بالینیِ هشدارشده", "clinical:read:own": "خواندن داده‌ی بالینیِ خود", "clinical:read:supervisees": "خواندن داده‌ی بالینیِ زیردستان",
    "clinical:write:own": "ثبت داده‌ی بالینیِ خود", "detection:read": "مشاهده‌ی تشخیص", "detection:run": "اجرای تشخیص", "hr:read": "مشاهده‌ی منابع انسانی", "hr:write": "ویرایش منابع انسانی",
    "quality:write": "ثبت مسائل کیفیت", "referrals:read:own": "خواندن ارجاع‌های خود", "referrals:write:own": "ثبت ارجاعِ خود", "supervision:read": "مشاهده‌ی نظارت",
    "supervision:read:own": "مشاهده‌ی نظارتِ خود", "supervision:write": "ثبت نظارت", "users:manage": "مدیریت حساب‌ها", "users:read": "مشاهده‌ی حساب‌ها"})


MESSAGES = {
    "Account not active": "حساب فعال نیست", "Account temporarily locked": "حساب موقتاً قفل شده است", "Action not found": "اقدام یافت نشد",
    "Administrators cannot change their own role": "مدیران نمی‌توانند نقش خود را تغییر دهند", "Administrators cannot change their own status": "مدیران نمی‌توانند وضعیت خود را تغییر دهند",
    "Alert not found": "هشدار یافت نشد", "Already escalated": "قبلاً ارجاع شده است", "Assignee is involved in this alert (conflict of interest)": "واگذارشونده در این هشدار دخیل است (تعارض منافع)",
    "Assignee must be an active reviewer authorised for this alert's domain": "واگذارشونده باید بازبینِ فعالِ مجاز برای حوزه‌ی این هشدار باشد",
    "Client is not in your caseload": "این مراجع در پرونده‌های شما نیست", "E-mail already registered": "این ایمیل قبلاً ثبت شده است", "Invalid credentials": "ایمیل یا رمز عبور نادرست است",
    "Invalid or expired token": "توکن نامعتبر یا منقضی است", "Issue not found": "مسئله یافت نشد", "Meeting not found": "جلسه‌ی نظارت یافت نشد", "No check-in recorded": "ورودی ثبت نشده است",
    "Approved without supporting documentation. This is recorded and visible to compliance monitoring.": "بدون مستندات پشتیبان تأیید شد. این مورد ثبت شده و برای پایش انطباق قابل مشاهده است.",
    "Not allowed to route this alert": "اجازه‌ی ارجاع این هشدار را ندارید", "Only investigating reviewers may see the AI assistant history": "فقط بازبین‌های تحقیق‌کننده می‌توانند تاریخچه‌ی دستیار هوش مصنوعی را ببینند",
    "Only operational/clinical concerns are routed to supervisors; potential misconduct stays with compliance/HR": "فقط نگرانی‌های عملیاتی/بالینی به سوپروایزرها ارجاع می‌شود؛ تخلف بالقوه نزد انطباق/منابع انسانی می‌ماند",
    "Only reviewers authorised to investigate this alert may use the AI assistant": "فقط بازبین‌های مجاز به تحقیقِ این هشدار می‌توانند از دستیار هوش مصنوعی استفاده کنند",
    "Only the assignee or the supervisor can update this action": "فقط مسئولِ اقدام یا سوپروایزر می‌تواند این اقدام را به‌روزرسانی کند",
    "Open corrective actions remain: provide a monitoring/improvement plan to close the review": "اقدام‌های اصلاحیِ باز مانده است: برای بستن بازبینی، طرح پایش/بهبود ارائه دهید",
    "Practitioner has no current supervisor": "متخصص سوپروایزر فعلی ندارد", "Practitioner is not your current supervisee": "این متخصص هم‌اکنون زیردست شما نیست",
    "Practitioner not found": "متخصص یافت نشد", "Review is closed": "بازبینی بسته شده است", "Review must be decided before it can be closed": "بازبینی باید پیش از بسته‌شدن تصمیم‌گیری شود",
    "Review not found": "بازبینی یافت نشد", "Session does not belong to this supervisee": "این جلسه متعلق به این زیردست نیست", "Session not found": "جلسه یافت نشد",
    "Target must be an active therapist": "مقصد باید یک درمانگرِ فعال باشد", "Terminated accounts cannot be re-enabled here (HR lifecycle)": "حساب‌های خاتمه‌یافته را از اینجا نمی‌توان دوباره فعال کرد (چرخه‌ی حیات منابع انسانی)",
    "The evidence must be reviewed by the closing reviewer before an alert can be closed as substantiated": "پیش از بستنِ هشدار به‌عنوان «اثبات‌شده»، بازبینِ بسته‌کننده باید شواهد را دیده باشد",
    "The practitioner's supervisor is involved in this alert (conflict of interest)": "سوپروایزر این متخصص در این هشدار دخیل است (تعارض منافع)",
    "This supervision relationship already exists": "این رابطه‌ی نظارتی از قبل وجود دارد", "Unknown client reference": "شناسه‌ی مراجع ناشناخته است", "User not found": "کاربر یافت نشد",
    "end_date is before start_date": "تاریخ پایان پیش از تاریخ شروع است", "self-supervision is not allowed": "نظارت بر خود مجاز نیست",
    "supervisee must be an active therapist or assistant counselor": "زیردست باید درمانگر یا مشاور کمکیِ فعال باشد", "supervisor must be an active clinical supervisor": "سوپروایزر باید سوپروایزر بالینیِ فعال باشد",
    "Insufficient permissions for this resource": "مجوز کافی برای این منبع ندارید", "No relationship permits reading this practitioner's clinical records": "هیچ رابطه‌ای خواندن سوابق بالینی این متخصص را مجاز نمی‌کند",
    "Authentication credentials were not provided.": "احراز هویت انجام نشده است.", "Not authenticated": "احراز هویت انجام نشده است", "Conflicting or invalid data": "داده‌ی متعارض یا نامعتبر",
    "You do not have permission to perform this action.": "اجازه‌ی انجام این کار را ندارید.", "Not found.": "یافت نشد.", "Conflict": "تعارض", "Internal server error": "خطای داخلی سرور",
    "This field is required.": "این فیلد الزامی است.", "This field may not be null.": "این فیلد نمی‌تواند تهی باشد.", "This field may not be blank.": "این فیلد نمی‌تواند خالی باشد.",
    "Enter a valid email address.": "یک ایمیل معتبر وارد کنید.", "A valid integer is required.": "یک عدد صحیح معتبر لازم است.", "A valid number is required.": "یک عدد معتبر لازم است.",
    "Not a valid string.": "رشته‌ی معتبر نیست.", "Must be a valid boolean.": "باید درست یا نادرست باشد.",
    "Advisory only. This alert does not establish fraud or misconduct; decisions require authorised human review.": "فقط توصیه‌ای. این هشدار تقلب یا تخلف را اثبات نمی‌کند؛ تصمیم‌گیری مستلزم بازبینی انسانیِ مجاز است.",
    "Prior alerts are context for reviewers only. They are not findings, do not alter this risk score, and create no presumption of misconduct.": "هشدارهای قبلی فقط زمینه‌ی کار بازبین‌ها هستند. یافته نیستند، این امتیاز ریسک را تغییر نمی‌دهند و هیچ پیش‌داوریِ تخلفی ایجاد نمی‌کنند.",
    "Longitudinal monitoring context only: alerts are not findings; false positives and closed-no-action outcomes are part of this record.": "فقط زمینه‌ی پایش طولی: هشدارها یافته نیستند؛ مثبت‌های کاذب و نتیجه‌ی «بسته – بدون اقدام» بخشی از این سابقه‌اند.",
    "AI output is advisory and may be wrong. Every statement must be checked against the cited evidence; decisions are made by authorised humans.": "خروجی هوش مصنوعی توصیه‌ای است و ممکن است اشتباه باشد. هر گزاره باید با شواهدِ ارجاع‌شده تطبیق داده شود؛ تصمیم‌ها را انسان‌های مجاز می‌گیرند.",
    "Alert created from supervisor escalation": "هشدار از ارجاع سوپروایزر ایجاد شد", "Created from supervisor escalation": "از ارجاع سوپروایزر ایجاد شد", "Evidence viewed": "شواهد مشاهده شد",
    "AI question refused by input guardrail": "پرسش از دستیار هوش مصنوعی توسط محافظ ورودی رد شد",
}
MESSAGE_TEMPLATES = [
    (r"Cannot '(.+)' from state '(.+)'", lambda m: f"انجام «{TERMS.get(m.group(1), m.group(1))}» از وضعیت «{TERMS.get(m.group(2), m.group(2))}» ممکن نیست"),
    (r"A documented note of at least (\d+) characters is required for '(.+)'", lambda m: f"برای «{TERMS.get(m.group(2), m.group(2))}» یادداشتِ مستند حداقل {det.fa_digits(m.group(1))} نویسه لازم است"),
    (r"Action '(.+)' is not allowed for your role or the alert's current status", lambda m: f"اقدام «{TERMS.get(m.group(1), m.group(1))}» برای نقش شما یا وضعیت فعلی هشدار مجاز نیست"),
    (r"AI assistant limit reached \((\d+) requests per hour\)", lambda m: f"سقف دستیار هوش مصنوعی پر شد ({det.fa_digits(m.group(1))} درخواست در ساعت)"),
    (r"Request was throttled\. Expected available in (\d+) seconds?\.", lambda m: f"درخواست‌ها محدود شد. {det.fa_digits(m.group(1))} ثانیه‌ی دیگر دوباره تلاش کنید."),
    (r"Ensure this field has at least (\d+) characters\.", lambda m: f"این فیلد باید حداقل {det.fa_digits(m.group(1))} نویسه باشد."),
    (r"Ensure this field has no more than (\d+) characters\.", lambda m: f"این فیلد نباید بیش از {det.fa_digits(m.group(1))} نویسه باشد."),
    (r"Ensure this value is greater than or equal to (\d+)\.", lambda m: f"مقدار باید بزرگ‌تر یا برابر {det.fa_digits(m.group(1))} باشد."),
    (r"Ensure this value is less than or equal to (\d+)\.", lambda m: f"مقدار باید کوچک‌تر یا برابر {det.fa_digits(m.group(1))} باشد."),
    (r"\"(.+)\" is not a valid choice\.", lambda m: f"«{m.group(1)}» گزینه‌ی معتبری نیست."),
    (r"(?:Date|Datetime) has wrong format\..*", lambda m: "قالب تاریخ/زمان نادرست است."),
    (r"Assigned to (.+?)\.(?: (.*))?", lambda m: f"واگذار شد به {m.group(1)}." + (f" {m.group(2)}" if m.group(2) else "")),
    (r"Routed to supervisor #(\d+): (.*)", lambda m: f"به سوپروایزر #{det.fa_digits(m.group(1))} ارجاع شد: {m.group(2)}"),
    (r"Alert created by detection run #(\d+)(?: \(recurrence; earlier alert (\S+) was (\w+)\))?", lambda m: f"هشدار توسط اجرای تشخیص شماره‌ی {det.fa_digits(m.group(1))} ایجاد شد"
        + (f" (تکرار؛ هشدار قبلی {m.group(2)} در وضعیت «{TERMS.get(m.group(3), m.group(3))}» بود)" if m.group(2) else "")),
    (r"Risk score updated (\d+) → (\d+) by detection run #(\d+)", lambda m: f"امتیاز ریسک از {det.fa_digits(m.group(1))} به {det.fa_digits(m.group(2))} به‌روزرسانی شد (اجرای تشخیص {det.fa_digits(m.group(3))})"),
    (r"AI (briefing|answer) via (\S+); output guardrails (\d+)/(\d+) passed; attempts=(\d+); fallback=(True|False)",
     lambda m: f"{'خلاصه' if m.group(1) == 'briefing' else 'پاسخ'}ی هوش مصنوعی از طریق «{TERMS.get(m.group(2), m.group(2))}»؛ محافظ‌های خروجی {det.fa_digits(m.group(3))}/{det.fa_digits(m.group(4))} گذشت؛ تلاش‌ها={det.fa_digits(m.group(5))}؛ جایگزین قطعی={'بله' if m.group(6) == 'True' else 'خیر'}"),
]


def translate(msg: str) -> str:
    """Translate one API message to Persian (exact, then template); unknown text is returned unchanged."""
    if msg in MESSAGES:
        return MESSAGES[msg]
    for pattern, fn in MESSAGE_TEMPLATES:
        m = re.fullmatch(pattern, msg, flags=re.S)
        if m:
            return fn(m)
    return msg


def translate_payload(data):
    """Recursively translate strings in an error payload ({detail: ...} / {field: [msgs]})."""
    if isinstance(data, str):
        return translate(data)
    if isinstance(data, list):
        return [translate_payload(x) for x in data]
    if isinstance(data, dict):
        return {k: translate_payload(v) for k, v in data.items()}
    return data


def t(msg: str) -> str:
    """Localise a message for the CURRENT request language."""
    return translate(msg) if lang() == "fa" else msg


def labels() -> dict:
    """Everything the UI needs to render backend vocabularies in the current language."""
    return {"lang": lang(), "terms": TERMS if lang() == "fa" else {}, "categories": CATEGORY if lang() == "fa" else {},
            "levels": det.LEVEL if lang() == "fa" else {}}
