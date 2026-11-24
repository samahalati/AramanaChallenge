# قواعد مهندسی

[English](../ENGINEERING_RULES.md) · **فارسی**

قواعدی که کد را کوچک، امن و یکدست نگه می‌دارند؛ تا جای ممکن با تست اجرا می‌شوند. برای تصویر کلی اول [UNDERSTANDING.md](UNDERSTANDING.md) را بخوانید؛ دستورالعمل‌های گام‌به‌گام در [HOWTO.md](HOWTO.md) است.

## دستورها

| کار | دستور |
|---|---|
| نصب | `python3 -m venv .venv && . .venv/bin/activate && pip install -r backend/requirements.txt && (cd frontend && npm install)` |
| بک‌اند (از `backend/`) | `python manage.py migrate && python manage.py seed_demo --detect && python manage.py runserver 0.0.0.0:8000` |
| فرانت‌اند (از `frontend/`) | `npm run dev` (پروکسی به :8000) · `npm run build` (سپس Django آن را سرو می‌کند) |
| تست‌ها | `cd backend && python -m pytest -q` |
| بررسی ترجمه‌ها | `cd frontend && npm run check:i18n` |
| کیفیت تشخیص | `python manage.py evaluate` |
| نگهبان‌های LLM | `python manage.py evaluate_llm` (با کلید: `--live`) |
| آزمون دودِ رابط | `node frontend/e2e/smoke.cjs` |
| بازتولید مستندات تولیدشده | `python manage.py export_docs` |

## قواعد معماری (نشکنید)

1. **لایه‌ها:** `views` (HTTP + اعتبارسنجی سریالایزر) ← `services` (قواعد کسب‌وکار، تراکنش، حسابرسی) ← `models`. منطق کسب‌وکار در view نیست.
2. **مرزها اپ‌های Django هستند** (`accounts/hr`، `clinical/supervision`، `core`، `monitoring`). ارجاع بین مرزها به افراد فقط با شناسه‌ی عددی است، نه FK. مراجعان نام‌مستعارند؛ هرگز اطلاعات هویتیِ واقعی اضافه نکنید.
3. **مجوزدهی** فقط از `core/rbac.py` و `perms = {...}` اعلامی روی هر view (`core/permissions.py`؛ اعلام‌نشده ⇒ رد). دامنه‌ی رابطه‌ای در `hr/selectors.py` و `monitoring/visibility.py` است. تغییرش ⇒ `export_docs` را اجرا و `tests/test_security.py` را به‌روز کنید.
4. **انسان در حلقه:** هیچ مسیری نباید وضعیت/نقش/قرارداد کاربر را از روی هشدار یا امتیاز تغییر دهد. `detection/` پایتونِ خالص است و Django را import نمی‌کند؛ تست این را اجرا می‌کند.
5. **LLM هرگز امتیاز نمی‌دهد و تصمیم نمی‌گیرد.** فقط بسته‌ی شواهدِ نام‌مستعار و پاک‌سازی‌شده را می‌بیند (`detection/assistant/pack.py`). قواعد رفتاری (رد، لحن، زبان) در **پرامپت** است (`investigator.SYSTEM`)، نه لیست کلمه/regex. هر پاسخ باید از بررسی‌های قطعیِ بدون‌لیست در `guardrails.validate()` (ساختار، ارجاع، عدد، هویت) **و** قاضی LLM (`judge.py`: لحن، سازگاری، هویت پنهان) بگذرد وگرنه جایگزین قطعی می‌آید؛ بدون حکم قاضی ⇒ جایگزین. دستیار مسیر نوشتن ندارد. رفتار جدید LLM ⇒ یک سناریو در `detection/assistant/redteam.py` و اجرای `evaluate_llm` (با کلید: `--live`).
6. **تغییر وضعیت** از `StateMachine` (`core/statemachine.py`) می‌گذرد؛ **خواندن/نوشتن حساس** `core.audit.audit()` / `log_admin()` را صدا می‌زند؛ ردها را `RolePermission` ثبت می‌کند.
7. ردیف حسابرسیِ نوشته‌شده درست پیش از raise باید **بیرون** از `transaction.atomic()` باشد (وگرنه برگردانده می‌شود).
8. وزن‌ها و آستانه‌های تشخیص در `backend/detection/config.yaml` (نسخه‌دار) است؛ هرگز در کد ثابت نکنید. آشکارسازها شاخص را با `cfg.ind(...)` می‌سازند.
9. اول DRY: پیش از افزودن کمکی تازه از `bursts()`، `StateMachine`، `validated()`، `DataTable`/`FormModal`/`Query`/`useAct` استفاده کنید.
10. **i18n:** پایگاه داده انگلیسیِ متعارف نگه می‌دارد؛ بومی‌سازی فقط هنگام نمایش (`core/i18n.py`، `detection/i18n.py`، `monitoring/localize.py`، `t()` و `src/lib/fa.js` در فرانت). هر متن تازه ⇒ ترجمه‌ی فارسی‌اش (`npm run check:i18n`، و `tests/test_i18n.py` باید سبز بماند)؛ نگهبان‌های LLM باید در هر دو زبان برقرار باشند.
11. رازها فقط از env (`backend/.env` در گیت نیست؛ `.env.example` را به‌روز نگه دارید).
