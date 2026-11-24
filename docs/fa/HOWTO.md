# راهنمای گام‌به‌گام

[English](../HOWTO.md) · **فارسی**

فهرست‌های کوتاه برای تغییرهایی که بیشتر انجام می‌دهید. مفاهیم و نقشه‌ی فایل‌ها: [UNDERSTANDING.md](UNDERSTANDING.md). قواعد: [ENGINEERING_RULES.md](ENGINEERING_RULES.md).

## اجرا و راستی‌آزمایی دمو از ابتدا تا انتها
1. `cd backend && python manage.py migrate && python manage.py seed_demo --detect` (برای پاک‌کردن اول `--reset`).
2. `python manage.py runserver 0.0.0.0:8000` (API و Swagger در `/api/docs/`)؛ در `frontend/`: `npm install && npm run dev` ← http://localhost:5173 (یا `npm run build` و استفاده از :8000).
3. ورودهای دمو (رمز `Demo!2345`): `compliance@`، `hr@`، `supervisor1@`، `admin@`، `admin2@`، `therapist1@`، `counselor1@aramana.test`.
4. چهار سناریوی الزامی در README است. سناریوی ۴ زنده: با `admin@` پنج بار `GET /api/clinical/practitioners/15/sessions` بزنید (۴۰۳) و سپس با انطباق تشخیص را اجرا کنید.
5. راستی‌آزمایی: `cd backend && python -m pytest -q`، `python manage.py evaluate` و `BASE=http://localhost:5173 node frontend/e2e/smoke.cjs` (برای حالت تمیز اول reseed).

## افزودن آشکارساز
1. کلاس تازه در `backend/detection/detectors/<file>.py` که از `Detector` ارث می‌برد: `category/domain/scenario` را بگذارید (و `kind="behavioral"` فقط برای سیگنال‌های تأییدکننده)، `detect()` را با `self.finding(...)` و `self.cfg.ind(...)` بنویسید، با `@register` ثبت کنید؛ اگر فایل تازه است در `detectors/__init__.py` import کنید.
2. وزن‌ها و آستانه‌ها در `backend/detection/config.yaml`؛ `ruleset_version` را بالا ببرید. برای قواعد پنجره‌ای از `bursts()` استفاده کنید.
3. نام سناریوی تازه متن توضیحش را در `detection/explain.py` (و متن فارسی در `detection/i18n.py`) می‌خواهد.
4. یک ناهنجاریِ تزریقی **و یک نمونه‌ی منفیِ دشوار** به `backend/seed/generate.py` اضافه کنید (+ ورودی ground-truth).
5. تست در `backend/tests/test_detection.py`؛ `python manage.py evaluate` و `python scripts/multi_seed_eval.py 1 2 3 4 5` را اجرا و عددها را در `docs/TECHNICAL_REPORT.md` به‌روز کنید.
6. توضیح باید به شاخص‌ها ردیابی شود – بدون امتیاز مبهم. `detection/` نباید Django را import کند.

## تغییر نقش، مجوز یا دید
1. `backend/core/rbac.py` را ویرایش کنید (ماتریس، `ALERT_DOMAIN_VISIBILITY`، `INVESTIGATE_DOMAINS`، `ROLE_NAV`). viewها نیازشان را با `perms = {...}` اعلام می‌کنند؛ قواعد رابطه‌ای در `hr/selectors.py` و `monitoring/visibility.py` است.
2. داده‌ی بالینی را از منابع انسانی جدا نگه دارید: `hr_admin` و `platform_admin` هرگز `clinical:*` ندارند.
3. `python manage.py export_docs` را اجرا کنید (`docs/RBAC_MATRIX.md` بازتولید می‌شود) و موارد `backend/tests/test_security.py` را اضافه/اصلاح کنید.
4. `cd backend && python -m pytest tests/test_security.py -q`.

## ارزیابی موتور تشخیص و به‌روزکردن عددهای گزارش
1. `cd backend && python manage.py seed_demo --reset --seed-value 42 --detect`
2. `python manage.py evaluate` (برای ذخیره‌ی JSON: `--write ../docs/eval_results.json`)
3. `python scripts/multi_seed_eval.py 1 2 3 4 5 6 7 8 | tee ../docs/eval_multi_seed.txt`
4. جدول‌ها را در `docs/TECHNICAL_REPORT.md` بگذارید. اگر معیاری بدتر شد، آشکارساز یا پیکربندی‌اش را درست کنید – هرگز ground truth را ویرایش نکنید.

## افزودن گردش‌کار، endpoint یا صفحه
* **گردش‌کار:** یک `StateMachine({...})` تعریف کنید و `.apply(action, current)` را در service صدا بزنید.
* **Endpoint:** سریالایزر ← تابع service ← view نازک با `perms = {...}` ← URL. احراز هویت، ثبت ردها و قراردادهای حسابرسی رایگان می‌آیند.
* **صفحه:** یک صفحه زیر `frontend/src/features/<module>/` با `Query`، `DataTable`، `useForm` و `useAct`؛ هر متن نمایشی از `t("…")` می‌گذرد و ترجمه‌اش در `src/lib/fa.js` می‌آید (`npm run check:i18n`).

## تغییر دستیار LLM
قواعد در پرامپت (`detection/assistant/investigator.py::SYSTEM`) و rubric قاضی (`judge.py::RUBRIC`) است. یک حمله به `redteam.py` اضافه کنید، `python manage.py evaluate_llm` و (با کلید در `backend/.env`) `evaluate_llm --live` را اجرا کنید. ر.ک. [LLM_ASSISTANT.md](LLM_ASSISTANT.md).
