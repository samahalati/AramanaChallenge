"""Persian (fa) catalog for everything the detection engine SAYS: scenario names, titles, explanations, indicator labels / values /
thresholds / notes, recommended actions. Pure Python, no Django.

Design: the database keeps ONE canonical English text (audit source of truth, stable keys); localisation happens at presentation time,
per request, from this catalog. Static strings are exact-match; strings with numbers inside are matched by a template (`TEMPLATES`).
Unknown strings fall back to English (a test fails if a real alert still contains English).
"""
from __future__ import annotations

import re

DIGITS_FA = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
DIGITS_EN = {**{ord(c): str(i) for i, c in enumerate("۰۱۲۳۴۵۶۷۸۹")}, **{ord(c): str(i) for i, c in enumerate("٠١٢٣٤٥٦٧٨٩")}, ord("٫"): ".", ord("٬"): "", ord("٪"): "%"}


DECIMAL = re.compile(r"(?<![\d.])(\d+)\.(\d+)(?![\d.])")   # 0.75 -> ۰٫۷۵ (but never 203.0.113.50 or 1.0.0)


def fa_digits(s) -> str:
    return DECIMAL.sub(r"\1٫\2", str(s)).translate(DIGITS_FA).replace("%", "٪")


def en_digits(s) -> str:
    return str(s).translate(DIGITS_EN)


LEVEL = {"low": "کم", "medium": "متوسط", "high": "بالا", "critical": "بحرانی"}
METHOD = {"rule": "قاعده", "statistical": "آماری", "ml": "یادگیری ماشین", "graph": "گراف", "manual": "دستی"}
AREA = {"clinical": "بالینی", "hr": "منابع انسانی", "supervision": "نظارت", "alerts": "هشدارها", "audit": "حسابرسی"}
FEATURE = {"n_decided": "تعداد بازبینی", "rapid_rate": "نرخ بازبینی سریع", "mean_minutes": "میانگین دقیقه‌ی بازبینی", "cancel_rate": "نرخ لغو",
           "heavy_mod_rate": "نرخ ویرایش سنگین", "mismatch_rate": "نرخ ناهمخوانی", "noshow_rate": "نرخ غیبت", "load": "بار کاری",
           "overlap_pairs": "جفت‌های هم‌پوشان", "doc_missing_rate": "نرخ فقدان مستندات", "approve_rate": "نرخ تأیید"}

SCENARIOS = {
    "session_overlap": {
        "name": "جلسه‌های هم‌پوشان", "title": "رکوردهای جلسه‌ی هم‌پوشان ({n} جفت) برای {subject}",
        "summary": "ناسازگاری زمان‌بندی: متخصص رکوردهایی دارد که بازه‌ی زمانی‌شان هم‌پوشانی دارد (یک متخصص نمی‌تواند هم‌زمان دو جلسه‌ی یک‌به‌یک برگزار کند).",
        "benign": ["دوباره‌رزرو شدن یا خطای همگام‌سازی تقویم", "ثبت جلسه در بازه‌ی نادرست", "جلسه‌ی گروهیِ ثبت‌نشده (باید شناسه‌ی گروه مشترک داشته باشد)"]},
    "excessive_hours": {
        "name": "ساعات کاری بیش‌ازحد", "title": "ساعات جلسه‌ی بیش‌ازحد در روز برای {subject}",
        "summary": "تعداد ساعت‌های جلسه‌ی زمان‌بندی‌شده در یک روز غیرعادی زیاد است.", "benign": ["یک روز کاریِ طولانیِ تأییدشده", "خطای ورود داده"]},
    "duration_discrepancy": {
        "name": "ناهمخوانی مدت جلسه", "title": "مدت گزارش‌شده‌ی جلسه‌ها با داده‌ی ورود/خروج همخوان نیست: {subject}",
        "summary": "ناهمخوانی میان مدت گزارش‌شده و مدتِ قابل‌راستی‌آزمایی: مدت‌های گزارش‌شده از بازه‌ی ورود/خروج بیشترند، یا جلسه‌های انجام‌شده اصلاً ورودی ثبت نکرده‌اند.",
        "benign": ["فراموش‌شدن ثبت خروج", "مشکل ابزار ثبت ورود", "جلسه‌هایی که از کانالِ فاقد ابزار ثبت برگزار شده‌اند"]},
    "cancellation_pattern": {
        "name": "الگوی لغو/ویرایش جلسه‌ها", "title": "الگوی لغو/ویرایش جلسه‌ها: {subject}",
        "summary": "الگوی غیرعادیِ لغو و ویرایش جلسه‌ها در مقایسه با همتایان و تاریخچه‌ی خودِ متخصص.",
        "benign": ["بیماری، مرخصی یا تغییر پرونده‌ها", "اختلال پلتفرم", "جابه‌جایی‌های درخواستیِ مراجعان"]},
    "referral_behavior_shift": {
        "name": "تغییر مشکوک در رفتار ارجاع", "title": "تغییر در رفتار ارجاعِ {subject}",
        "summary": "مقصدهای ارجاعِ مشاور بین دوره‌ی قبلی و دوره‌ی اخیر بیش از آنچه تصادف توضیح می‌دهد تغییر کرده است.",
        "benign": ["تغییر در ترکیب یا نیازهای مراجعان", "سیاست تخصیص تازه یا تغییر ظرفیت متخصصان", "درخواست مراجعان برای متخصصان مشخص"]},
    "referral_concentration": {
        "name": "تمرکز غیرعادی ارجاع", "title": "تمرکز غیرعادی ارجاع برای {subject}",
        "summary": "توزیع ارجاع‌ها به‌طور معنادار با آنچه سیاست انتساب (تخصص + ظرفیت) پیش‌بینی می‌کند فرق دارد: ارجاع‌ها روی تعداد بسیار کمی متخصص متمرکز شده‌اند.",
        "benign": ["تخصصِ کم‌یاب با متخصصانِ واجد شرایطِ اندک (توضیح‌داده‌شده با سیاست)", "درخواست مراجع برای یک متخصص مشخص", "محدودیت ظرفیت/دسترس‌پذیری که در داده نیست"]},
    "approval_burst": {
        "name": "الگوی غیرعادی تأیید", "title": "الگوی غیرعادی تأیید برای سوپروایزر {subject}",
        "summary": "الگوی تأییدهای سوپروایزر غیرعادی است: تأییدها بدون مستندات پشتیبانِ الزامی و/یا با زمان بازبینیِ غیرقابل‌باور کوتاه صادر شده‌اند.",
        "benign": ["پاک‌سازی انباشتِ پایان دوره", "مستندات خارج از پلتفرم نگهداری می‌شوند", "بازبینی‌های تفویض‌شده که با حساب سوپروایزر ثبت شده‌اند"]},
    "admin_out_of_scope": {
        "name": "فعالیت مدیریتی خارج از دامنه‌ی مجوز", "title": "فعالیت حساب مدیریتی خارج از دامنه‌ی مجوز: {subject}",
        "summary": "حساب مدیریتی اقداماتی خارج از دامنه‌ی مجوز خود انجام داده و/یا حساب‌ها را به الگوی غیرعادی ساخته یا ارتقا داده است. این تلاش‌ها مسدود و کاملاً حسابرسی شده‌اند.",
        "benign": ["اتوماسیون یا یکپارچه‌سازیِ پیکربندی‌نادرست", "مدیری که بدون درک دامنه‌ی مجوز در رابط کاربری گشت می‌زند", "سناریوی واقعیِ تهدید داخلی یا اعتبارنامه‌ی لو رفته"]},
    "admin_modification_burst": {
        "name": "انفجار ویرایش سوابق حساس", "title": "انفجارِ {n} ویرایش مدرک/قرارداد توسط {subject}",
        "summary": "تعداد غیرعادی زیادی ویرایش روی سوابق حساس (مدارک/قراردادها) در بازه‌ی کوتاه.",
        "benign": ["کارزار تمدید گروهیِ مشروع (باید در یک درخواست تغییر مستند باشد)", "مهاجرت داده یا پاک‌سازی"]},
    "failed_login_burst": {
        "name": "ورودهای ناموفق مکرر", "title": "ورودهای ناموفق مکرر علیه {subject}",
        "summary": "انفجار تلاش‌های ورودِ ناموفق روی یک حساب، احتمالاً از چند نشانی (حمله‌ی حدس رمز).", "benign": ["فراموشی رمز توسط کاربر", "دستگاه مشترک با رمز ذخیره‌شده‌ی کهنه"]},
    "multi_account_ip": {
        "name": "یک نشانی، چند حساب", "title": "نشانی {ip} روی {n} حساب مختلف احراز هویت ناموفق داشت",
        "summary": "یک نشانی شبکه روی چند حساب متفاوت احراز هویت ناموفق داشته است (الگوی استفاده‌ی انبوه از اعتبارنامه‌های لو رفته یا آزمودنِ یک رمز روی حساب‌های بسیار).",
        "benign": ["نشانی NAT مشترک سازمانی", "حساب سرویسِ پیکربندی‌نادرست"]},
    "referral_approval_ring": {
        "name": "خوشه‌ی انحصاری ارجاع/تأیید", "title": "خوشه‌ی انحصاری ارجاع/تأیید پیرامون {subject}",
        "summary": "الگوی شبکه‌ای: یک مشاور، یک متخصص و سوپروایزرِ همان متخصص خوشه‌ای انحصاری می‌سازند — مشاور سهم غیرعادی بزرگی از ارجاع‌ها را (بیش از پیش‌بینی سیاست) به آن متخصص می‌فرستد، متخصص تقریباً همه‌ی ارجاع‌هایش را از همان مشاور می‌گیرد، و سوپروایزر کار او را بی‌قیدوشرط تأیید می‌کند.",
        "benign": ["تیم کوچک و خوب‌کار با عادت‌های ارجاعِ طبیعی", "تخصصی که در داده ثبت نشده است"]},
    "behavioral_anomaly": {
        "name": "ناهنجاری رفتاری", "title": "ناهنجاری رفتاری نسبت به همتایان: {subject}",
        "summary": "پرتِ رفتاری نسبت به همتایان / تاریخچه‌ی خود، که با روش آماری و مدل بدون‌ناظر تشخیص داده شده است. اطمینان مستقل پایین است؛ فقط انگیزه‌ای برای بررسی است، نه مدرک.",
        "benign": ["بار فصلی کار", "تغییر نقش", "ترکیب تازه‌ی پرونده‌ها"]},
    "supervisor_escalation": {
        "name": "ارجاع سوپروایزر", "title": "ارجاع سوپروایزر: {title}", "summary": "یک سوپروایزر بالینی این مورد را برای بازبینی بیشتر ارجاع داده است.", "benign": []},
}

LABELS = {
    "Accounts created in a short window": "حساب‌های ساخته‌شده در بازه‌ی کوتاه",
    "Approvals without required supporting documentation": "تأیید بدون مستندات پشتیبانِ الزامی",
    "Cancellation rate vs peers (robust z)": "نرخ لغو در مقایسه با همتایان (z مقاوم)",
    "Completed sessions with no check-in record": "جلسه‌های انجام‌شده بدون ثبت ورود",
    "Counselor ↔ practitioner exclusive referral dependency": "وابستگی انحصاریِ ارجاع میان مشاور و متخصص",
    "Denied access attempts in one window": "تلاش‌های دسترسیِ ردشده در یک بازه",
    "Distinct accounts targeted from one address": "حساب‌های متمایزِ هدف‌گرفته‌شده از یک نشانی",
    "Distinct resource areas probed": "حوزه‌های منبعِ متمایزِ کاوش‌شده",
    "Failed logins in one window": "ورودهای ناموفق در یک بازه",
    "Isolation-Forest anomaly score (recent weeks)": "امتیاز ناهنجاری Isolation Forest (هفته‌های اخیر)",
    "Change of referral targets between the previous and the recent period (permutation p-value)": "تغییر مقصدهای ارجاع بین دوره‌ی قبلی و اخیر (مقدار p آزمون جایگشت)",
    "Jensen-Shannon distance between the two periods": "فاصله‌ی ینسن–شانون میان دو دوره",
    "Jensen-Shannon distance observed vs expected": "فاصله‌ی ینسن–شانون مشاهده‌شده در برابر مورد انتظار",
    "Overlap between sessions both recorded as completed": "هم‌پوشانی میان جلسه‌هایی که هر دو انجام‌شده ثبت شده‌اند",
    "Overlapping session pairs": "جفت‌جلسه‌های هم‌پوشان",
    "Physically impossible: in-person at two locations": "ناممکن از نظر فیزیکی: حضوری در دو مکان",
    "Privileged roles granted in the same period": "نقش‌های ویژه‌ی اعطاشده در همان بازه",
    "Referral distribution vs policy-expected (Monte-Carlo GOF p-value)": "توزیع ارجاع در برابر مورد انتظار از سیاست (مقدار p آزمون نیکویی برازش مونت‌کارلو)",
    "Referrals to practitioners whose specialisation does not match the need": "ارجاع به متخصصانی که تخصصشان با نیاز نمی‌خواند",
    "Sensitive-record edits in one hour": "ویرایش سوابق حساس در یک ساعت",
    "Share of completed sessions with unsupported reported duration": "سهم جلسه‌های انجام‌شده با مدت گزارش‌شده‌ی بی‌پشتوانه",
    "Share of sessions modified 2+ times vs peers (robust z)": "سهم جلسه‌های ویرایش‌شده ۲ بار یا بیشتر در مقایسه با همتایان (z مقاوم)",
    "Share sent to the two most-used practitioners (observed vs expected)": "سهم ارسال‌شده به دو متخصصِ پرارجاع‌تر (مشاهده‌شده در برابر مورد انتظار)",
    "Supervisor approves this practitioner's work unconditionally": "سوپروایزر کار این متخصص را بی‌قیدوشرط تأیید می‌کند",
    "Unsupported duration/check-in rate vs peers (robust z)": "نرخ مدت/ورودِ بی‌پشتوانه در مقایسه با همتایان (z مقاوم)",
    "Weekly reviews decided vs peers (robust z)": "بازبینی‌های تصمیم‌گرفته‌شده‌ی هفتگی در مقایسه با همتایان (z مقاوم)",
    "Days with excessive session hours": "روزهای دارای ساعت جلسه‌ی بیش‌ازحد",
    "No-show rate vs peers (robust z)": "نرخ غیبت در مقایسه با همتایان (z مقاوم)",
    "Weekly load vs capacity vs peers (robust z)": "بار هفتگی نسبت به ظرفیت در مقایسه با همتایان (z مقاوم)",
    "Approvals without documentation vs peers (robust z)": "تأیید بدون مستندات در مقایسه با همتایان (z مقاوم)",
    "Supervisor severity judgement": "قضاوت شدتِ سوپروایزر",
}
LABEL_TEMPLATES = [
    (r"Approvals with < (\d+) min review time", "تأییدها با زمان بازبینی کمتر از {0} دقیقه"),
    (r"Decisions within (\d+)h vs cohort median", "تصمیم‌ها در {0} ساعت در برابر میانه‌ی گروه"),
    (r"Share of reviews under (\d+) minutes vs peers \(robust z\)", "سهم بازبینی‌های زیر {0} دقیقه در مقایسه با همتایان (z مقاوم)"),
]
NOTES = {
    "Each attempt was blocked and audited": "هر تلاش مسدود و حسابرسی شد",
    "Volume only – documentation and review time are normal": "فقط حجم – مستندات و زمان بازبینی عادی‌اند",
    "Intervals overlap by more than the tolerance": "بازه‌ها بیش از حد تلورانس هم‌پوشانی دارند",
    "Both sessions in person at different locations at the same time": "هر دو جلسه حضوری و هم‌زمان در مکان‌های متفاوت‌اند",
    "Completed (with check-in) – not merely a scheduling conflict": "انجام‌شده (با ثبت ورود) – صرفاً تعارض زمان‌بندی نیست",
    "Human input": "ورودیِ انسانی",
}
# (regex, template) – matched with fullmatch, groups are formatted with {0}, {1}…; nested translation via callables below
TEMPLATES = [
    (r"Top drivers: (.+)", lambda m: "محرک‌های اصلی: " + re.sub(r"([a-z_]+) \(z=([\d.]+)\)", lambda d: f"{FEATURE.get(d.group(1), d.group(1))} (z={d.group(2)})", m.group(1)).replace(", ", "، ")),
    (r"value ([\d.]+), cohort median ([\d.]+)", lambda m: f"مقدار {m.group(1)}، میانه‌ی گروه {m.group(2)}"),
    (r"naive-uniform test p=([\d.]+)", lambda m: f"آزمون یکنواختِ ساده p={m.group(1)}"),
    (r"median review time ([\d.]+) min", lambda m: f"میانه‌ی زمان بازبینی {m.group(1)} دقیقه"),
    (r"(\d+) distinct source addresses", lambda m: f"{m.group(1)} نشانی مبدأ متمایز"),
    (r"(\d+) inflated vs check-in/out span, (\d+) without check-in", lambda m: f"{m.group(1)} مورد بیش از بازه‌ی ورود/خروج، {m.group(2)} مورد بدون ورود"),
    (r"([a-z]+(?:, [a-z]+)*)", lambda m: "، ".join(AREA.get(x, x) for x in m.group(1).split(", "))),
    # thresholds (specific before generic)
    (r">= (\d+) and >= (\d+)%", lambda m: f"≥ {m.group(1)} و ≥ {m.group(2)}٪"),
    (r"> ([\d.]+) \(p(\d+) of cohort history\)", lambda m: f"> {m.group(1)} (صدک {m.group(2)} تاریخچه‌ی گروه)"),
    (r"([\d.]+)× median \((\d+)\)", lambda m: f"{m.group(1)}× میانه ({m.group(2)})"),
    (r"null mean ([\d.]+)", lambda m: f"میانگین توزیع صفر {m.group(1)}"),
    (r"excess >= (\d+)", lambda m: f"مازاد ≥ {m.group(1)}"),
    (r"peer median (\d+)%", lambda m: f"میانه‌ی همتایان {m.group(1)}٪"),
    (r"out>=(\d+)%, in>=(\d+)%, lift>=([\d.]+)×", lambda m: f"خروجی ≥ {m.group(1)}٪، ورودی ≥ {m.group(2)}٪، افزایش نسبت به انتظار ≥ {m.group(3)}×"),
    (r">= ([\d.]+)% over >= (\d+) reviews", lambda m: f"≥ {m.group(1)}٪ در ≥ {m.group(2)} بازبینی"),
    (r">= (\d+) in (\d+) min", lambda m: f"≥ {m.group(1)} در {m.group(2)} دقیقه"),
    (r">= 1 alongside other admin anomalies", lambda m: "≥ 1 در کنار دیگر ناهنجاری‌های مدیریتی"),
    (r">= (\d+) per (\d+) min \(typical <= (\d+)\)", lambda m: f"≥ {m.group(1)} در هر {m.group(2)} دقیقه (معمول ≤ {m.group(3)})"),
    (r">= ([\d.]+) \(full (?:strength )?at (\d+)\)", lambda m: f"≥ {m.group(1)} (قدرت کامل در {m.group(2)})"),
    (r"> (\d+) h/day", lambda m: f"> {m.group(1)} ساعت در روز"),
    (r">= ([\d.]+)", lambda m: f"≥ {m.group(1)}"),
    (r"<= ([\d.]+)", lambda m: f"≤ {m.group(1)}"),
    # values
    (r"(\d+) of (\d+)", lambda m: f"{m.group(1)} از {m.group(2)}"),
    (r"(\d+)% vs (\d+)%", lambda m: f"{m.group(1)}٪ در برابر {m.group(2)}٪"),
    (r"(\d+)% of counselor's referrals; (\d+)% of practitioner's intake; lift ([\d.]+)×", lambda m: f"{m.group(1)}٪ از ارجاع‌های مشاور؛ {m.group(2)}٪ از ورودی متخصص؛ افزایش نسبت به انتظار {m.group(3)}×"),
    (r"(\d+)/(\d+) approved \(supervisor's other supervisees: (\d+%|n/a)\)", lambda m: f"{m.group(1)}/{m.group(2)} تأییدشده (سایر زیردستان سوپروایزر: {'نامشخص' if m.group(3) == 'n/a' else m.group(3).replace('%', '٪')})"),
]
ACTIONS = {
    "Ask the counselor and their supervisor what changed between the two periods (new client mix, assignment policy, requests); compare with the concentration alert for the same person. A shift alone is not evidence of wrongdoing.": "از مشاور و سوپروایزرش بپرسید بین دو دوره چه چیزی تغییر کرده است (ترکیب مراجعان، سیاست تخصیص، درخواست‌ها)؛ با هشدار تمرکزِ همان فرد مقایسه کنید. تغییر به‌تنهایی مدرک تخلف نیست.",
    "Block/rate-limit the address; reset targeted accounts; check whether any attempt succeeded.": "نشانی را مسدود/محدود کنید؛ حساب‌های هدف را بازنشانی کنید؛ بررسی کنید آیا تلاشی موفق بوده است.",
    "Check for an approved change request; compare modified values with source documents; verify the credentials/contracts changed are valid.": "وجود درخواست تغییرِ تأییدشده را بررسی کنید؛ مقادیر ویرایش‌شده را با اسناد مبدأ مقایسه کنید؛ از معتبربودن مدارک/قراردادهای تغییرکرده مطمئن شوید.",
    "Compare the distribution with assignment policy and client requests; check declared relationships/conflicts of interest between the counselor and the top practitioners. Rule out specialisation or capacity constraints before drawing any conclusion.": "توزیع را با سیاست انتساب و درخواست‌های مراجعان مقایسه کنید؛ روابط/تعارض منافع اعلام‌شده میان مشاور و متخصصانِ پرارجاع را بررسی کنید. پیش از هر نتیجه‌گیری، محدودیت‌های تخصص یا ظرفیت را کنار بگذارید.",
    "Compare the overlapping records with check-in/out logs; ask the practitioner to confirm which session took place; correct the schedule data if it is a recording error.": "رکوردهای هم‌پوشان را با لاگ ورود/خروج مقایسه کنید؛ از متخصص بخواهید تأیید کند کدام جلسه برگزار شده؛ اگر خطای ثبت است داده‌ی زمان‌بندی را اصلاح کنید.",
    "Confirm with the account owner what the intent was; review the audit trail; consider temporary credential reset. Do not sanction on the score alone.": "با صاحب حساب روشن کنید قصد چه بوده؛ ردپای حسابرسی را بازبینی کنید؛ بازنشانی موقت اعتبارنامه را در نظر بگیرید. فقط بر پایه‌ی امتیاز مجازات نکنید.",
    "Discuss in the next supervision session; check for legitimate causes (leave, caseload change).": "در جلسه‌ی نظارت بعدی مطرح کنید؛ علت‌های مشروع (مرخصی، تغییر پرونده‌ها) را بررسی کنید.",
    "Lock/reset the account, notify the owner, review source addresses.": "حساب را قفل/بازنشانی کنید، به صاحب آن اطلاع دهید، نشانی‌های مبدأ را بررسی کنید.",
    "Open the supervisor's recent approval history; request the missing documentation; ask whether reviews were delegated or backlog-cleared; consider second-review of flagged cases.": "تاریخچه‌ی تأییدهای اخیر سوپروایزر را باز کنید؛ مستندات ناقص را بخواهید؛ بپرسید بازبینی‌ها تفویض یا انباشت‌زدایی شده‌اند یا نه؛ بازبینی دومِ موارد علامت‌خورده را در نظر بگیرید.",
    "Request the practitioner's explanation; compare against platform check-in logs; review a sample of session notes. Possible manipulation of service records is a hypothesis only.": "توضیح متخصص را بخواهید؛ با لاگ‌های ورودِ پلتفرم مقایسه کنید؛ نمونه‌ای از یادداشت‌های جلسه را بررسی کنید. دست‌کاری سوابق خدمت فقط یک فرضیه است.",
    "Review whether a relationship or conflict of interest exists among the three users; audit a sample of the practitioner's reviewed cases independently of the supervisor.": "بررسی کنید آیا میان این سه کاربر رابطه یا تعارض منافع وجود دارد؛ نمونه‌ای از پرونده‌های بازبینی‌شده‌ی متخصص را مستقل از سوپروایزر ممیزی کنید.",
    "Verify the schedule for the listed days.": "زمان‌بندی روزهای فهرست‌شده را راستی‌آزمایی کنید.",
    "Use as a prompt for review only; corroborate with rule/statistical evidence.": "فقط به‌عنوان انگیزه‌ی بررسی استفاده کنید؛ با شواهد قاعده‌محور/آماری تأیید کنید.",
    "Compliance review of the supervisor's concern; consider clinical or HR follow-up through the documented process.": "نگرانی سوپروایزر را در انطباق بازبینی کنید؛ پیگیری بالینی یا منابع انسانی را از مسیر فرایند مستند در نظر بگیرید.",
}
DISCLAIMER = ("این هشدار صرفاً توصیه‌ای است. سیگنالی آماری/قاعده‌محور است و تقلب یا تخلف را اثبات نمی‌کند. "
              "تصمیم‌گیری مستلزم بازبینی انسانیِ مجاز، شواهد و فرایند مستند است.")
CAPPED_NOTE = "یادداشت: فقط شواهد ضعیف (حجم / امتیاز مدلِ غیرقابل‌توضیح) از این هشدار پشتیبانی می‌کند، پس امتیازش در سطح «کم» سقف خورده است."


def tr_text(text, kind: str = "any") -> str:
    """Translate one system-generated string (exact match, then template). Unknown -> unchanged (English)."""
    s = "" if text is None else str(text)
    if not s:
        return s
    for table in (LABELS, NOTES, ACTIONS):
        if s in table:
            return table[s]
    for pattern, fn in LABEL_TEMPLATES:
        m = re.fullmatch(pattern, s)
        if m:
            return fn.format(*m.groups()) if isinstance(fn, str) else fn(m)
    for pattern, fn in TEMPLATES:
        m = re.fullmatch(pattern, s)
        if m:
            return fn(m)
    return s


def localize_breakdown(rows: list[dict]) -> list[dict]:
    return [{**b, "label": tr_text(b["label"]), "note": tr_text(b.get("note")), "value": fa_digits(tr_text(b["value"])), "threshold": fa_digits(tr_text(b["threshold"])),
             "method_label": METHOD.get(b["method"], b["method"])} for b in rows]


def localize_title(scenario: str, subject: str, breakdown: list[dict], dedup_key: str = "", original: str = "") -> str:
    spec = SCENARIOS.get(scenario)
    if not spec:
        return original
    first = lambda *names: next((b["value"] for b in breakdown if b["name"] in names), "")   # noqa: E731
    n = first("overlap_pairs", "admin_modification_burst", "multi_account_ip")
    ip = dedup_key.split(":")[-1] if scenario == "multi_account_ip" else ""
    inner = original.split(": ", 1)[1] if scenario == "supervisor_escalation" and ": " in original else original
    return fa_digits(spec["title"].format(subject=subject, n=n, ip=ip, title=inner))


def build_explanation(scenario: str, subject: str, score: float, level: str, breakdown: list[dict], capped: bool = False) -> str:
    """Persian twin of detection.explain.build_explanation (breakdown must already be localised)."""
    spec = SCENARIOS.get(scenario, {"summary": scenario, "benign": []})
    shown = fa_digits(f"{score:.0f}")
    lines = [spec["summary"], "", f"موضوع: {subject}. امتیاز ریسک {shown} از ۱۰۰ (سطح {LEVEL[level]}).", "", "چرا این امتیاز (شاخص ← امتیاز):"]
    for b in breakdown:
        pts, note = fa_digits(f"{b['points']:.1f}"), (f" — {b['note']}" if b.get("note") else "")
        lines.append(f"  • [{b['method_label']}] {b['label']}: مقدار={b['value']} (مرجع {b['threshold']})، وزن {fa_digits(b['weight'])} × قدرت {fa_digits(b['strength'])} ← {pts} امتیاز{note}")
    if spec["benign"]:
        lines += ["", "توضیحات بی‌خطرِ قابل‌بررسی: " + "؛ ".join(spec["benign"]) + "."]
    if capped:
        lines += ["", CAPPED_NOTE]
    return "\n".join(lines + ["", DISCLAIMER])
