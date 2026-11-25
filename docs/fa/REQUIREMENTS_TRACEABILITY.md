# ردیابی الزام‌ها

[English](../REQUIREMENTS_TRACEABILITY.md) · **فارسی**

هر بند از سند اصلی چالش («AI Engineer – Technical Challenge»، ۱۰ صفحه) به محل پیاده‌سازی، محل نمایش و آزمونِ خودکارِ اثبات‌کننده‌اش نگاشت شده است. شماره‌ی بندها مال سند است. مجموعه‌ی انطباق در `backend/tests/test_requirements.py` است؛ آزمون‌های عمیق‌تر در سایر فایل‌های `backend/tests/` هستند.

راهنما: **کد** = پیاده‌سازی · **رابط** = جایی که کاربر می‌بیند · **اثبات** = آزمون خودکار یا سند.

## ۲. مأموریت اصلی – سه ماژول روی یک بنیان
| بند | کد | اثبات |
|---|---|---|
| ماژول‌های الف، ب، ج روی بنیان مشترک و یکدست | `backend/core` (RBAC، حسابرسی، ماشین حالت، خطاها)، یک پایگاه‌داده، یک احراز هویت | [ARCHITECTURE.md §۱–۲](ARCHITECTURE.md) |
| موتور تشخیص لایه‌ی هوشِ مرکزی است و هشدارهای توضیح‌پذیر را از رابط‌های منابع انسانی/نظارت قابل‌بررسی می‌کند | `backend/detection` ← `monitoring` ← صفحه‌های هشدار؛ سیگنال ارجاع سوپروایزر | `test_e2e.py` جریان‌های ۱ تا ۵ |

## ۳. ماژول الف – منابع انسانی و مدیریت پلتفرم
| بند | کد | رابط | اثبات |
|---|---|---|---|
| ۳٫۱ پروفایل حرفه‌ای، دسته‌های کاربر، تخصص | `hr/models.py` (`PractitionerProfile`)، `accounts/models.py` (نقش‌ها) | منابع انسانی ← متخصصان؛ پنجره‌ی **ویرایش پروفایل** (تخصص، واحد، نوع همکاری، ظرفیت، توضیح) | `test_workflows.py`، `test_3_1_profile_can_be_managed_and_supervision_schedule_defined` |
| مدارک، پیگیری پروانه و گواهی، انقضا | `Credential`، `hr/services.dashboard` | داشبورد منابع انسانی (انقضا ≤ ۶۰ روز) | `test_credentials_contracts_and_dashboard` |
| وضعیت اشتغال/همکاری، قراردادها | `PractitionerProfile.employment_type`، `Contract` | صفحه‌ی متخصص | همان |
| جذب/خروج؛ تعلیق، بازگشت، خاتمه | `hr/services.change_lifecycle` + `StateMachine`؛ دلیل الزامی | دکمه‌های صفحه‌ی متخصص | `test_practitioner_lifecycle_state_machine`، `test_terminate_closes_assignments_and_contracts` |
| تاریخچه‌ی کامل فعالیت و وضعیت | `LifecycleEvent` | کارت «تاریخچه‌ی کامل فعالیت و وضعیت» | `test_workflows.py` |
| ۳٫۲ تعریف نقش‌ها، سوپروایزر–زیردست، تیم‌ها، سلسله‌مراتب | `core/rbac.py`، `SupervisionAssignment`، `OrgUnit` | صفحه‌ی نقش‌ها، منابع انسانی ← سازمان | `test_permission_matrix_invariants` |
| تخصیص/تخصیص مجدد، تاریخ اعتبار، ردیابی تاریخی | `hr/services.assign_supervisor` (رابطه‌ی قبلی را پایان‌تاریخ می‌دهد) | منابع انسانی ← تخصیص‌های نظارت | `test_assignment_history_preserved_and_validated` |
| **۳٫۳ مدیریت عملکرد و فعالیت**: فعالیت متخصص، جلسه‌های انجام‌شده/زمان‌بندی‌شده، ارجاع‌ها، شاخص‌های کیفیت، مشارکت در نظارت، **توسعه‌ی حرفه‌ای**، روندها، الگوهای غیرعادی | `hr/activity.py` (فقط تجمیع، بدون محتوای بالینی)، `ProfessionalDevelopment`، `GET /hr/practitioners/{id}/activity`، `POST …/development` | صفحه‌ی متخصص ← «فعالیت و عملکرد»، «توسعه‌ی حرفه‌ای»، «فعالیت غیرعادی» | `test_3_3_*` |
| ۳٫۴ RBAC: شش نقش + نقش‌های مجاز دیگر؛ محدودسازی بر پایه‌ی نقش، رابطه، مسئولیت، حساسیت | `core/rbac.py`، `core/permissions.py` (اعلام‌نشده = رد)، `hr/selectors.py`، `monitoring/visibility.py` | ناوبریِ ویژه‌ی هر نقش | `test_security.py`، `test_3_4_six_roles_and_separation_of_clinical_data`؛ ماتریس: [RBAC_MATRIX.md](../RBAC_MATRIX.md) |
| جداسازی داده‌ی بالینی از منابع انسانی؛ جلوگیری از دسترسی غیرمجاز و قابل‌نمایش | نقش‌های مدیریتی `clinical:*` ندارند؛ شناسه‌ی مراجع پوشانده می‌شود (`C-****`) | – | `test_admin_roles_cannot_read_clinical_data_and_denials_are_recorded`، `test_client_refs_redacted_for_hr` |

## ۴. ماژول ب – نظارت بالینی و کیفیت
| بند | کد | رابط | اثبات |
|---|---|---|---|
| ۴٫۱ داشبورد: زیردستان تخصیص‌یافته/فعال/غیرفعال، بازبینی‌های در انتظار و معوق، مسائل کیفیتِ باز، موارد نیازمند ارجاع، فعالیت اخیر، روندها | `supervision/services.dashboard` | نظارت ← داشبورد | `test_4_1_supervisor_dashboard_has_every_required_indicator` |
| ۴٫۲ تخصیص متخصصان، رابطه‌ها، برنامه‌ها، مشارکت، تاریخچه، مسائل حل‌نشده، تغییر تخصیص | `SupervisionAssignment.schedule_every_days` (در فرم تخصیص منابع انسانی: «نظارت هر چند روز»)، `SupervisionMeeting`، فهرست زیردستان (حضور)، endpointهای تخصیص | نظارت ← زیردستان؛ منابع انسانی ← تخصیص‌ها | `test_supervisor_dashboard_and_supervisees`، `test_3_1_profile_can_be_managed_and_supervision_schedule_defined` |
| ۴٫۳ گردش‌کار بازبینی: اطلاعات مجازِ پرونده، یادداشت، ارزیابی، بازخورد، اقدام اصلاحی، برنامه‌ی پایش، بستن | `supervision/services` (`start/decide/add_corrective_action/close_review`)؛ `case_info` جلسه‌ی بازبینی‌شده را برمی‌گرداند (مراجع نام‌مستعار، زمان‌ها، شیوه، مدت‌ها، ثبت ورود/خروج) | نظارت ← بازبینی‌ها ← «اطلاعات پرونده» | `test_review_workflow_end_to_end`، `test_4_3_review_shows_the_authorised_case_information` |
| ۴٫۴ ارجاع ریسک؛ تمایز عملیاتی/بالینی/تخلف بالقوه؛ تصمیم بالینی انسانی می‌ماند | `QualityIssue.category`، `escalate_issue` ← هشدار، دامنه‌ها در `core/constants.py` | نظارت ← مسائل کیفیت | `test_flow5_quality_concern_routed_to_supervisor_and_escalation_back` |
| ۴٫۵ ردپذیری: چه کسی، کِی، چه چیزی دید، تصمیم، اقدام‌های اصلاحی، تکمیل | `core/audit.py` (زنجیره‌ی درهم‌سازی)، رویدادهای `viewed`/تصمیمِ بازبینی | صفحه‌ی حسابرسی، صفحه‌ی بازبینی | `test_4_5_*`، `test_audit_chain_verifies_and_detects_tampering` |

## ۵. ماژول ج – تشخیص تقلب و ناهنجاری مبتنی بر هوش مصنوعی
| بند | کد | اثبات |
|---|---|---|
| ۵٫۱ دسته‌های الف تا ه (درمانگر، مشاور، سوپروایزر، مدیر/پلتفرم، بین‌کاربری/شبکه)، از جمله «تغییرات مشکوک در رفتار ارجاع» (`referral_behavior_shift`) | `detection/detectors/{session,referral,approvals,security,graph,peer}.py` | `test_5_1_all_five_categories_are_detected_and_5_2_all_methods_are_used`، `test_detection.py`، `test_referral_behaviour_shift_detected_for_the_counselor_whose_targets_changed` |
| ۵٫۲ قاعده‌محور / آماری / ML / گراف / توضیح با کمک هوش مصنوعی، هرکدام توجیه‌شده؛ LLM تنها سازوکار نیست | قواعد، `peer.py` (آمار مقاوم)، Isolation Forest، `graph.py` (networkx)، `detection/assistant/` (فقط مشورتی) | [ARCHITECTURE.md §۵](ARCHITECTURE.md)، [TECHNICAL_REPORT.md](TECHNICAL_REPORT.md)، `test_detection_never_modifies_users` |
| ۵٫۳ امتیازدهی پیکربندی‌پذیر؛ محتوای هشدار (شناسه، کاربران، دسته، زمان، امتیاز، سطح، روش، شواهد، توضیح، اقدام، وضعیت)؛ چهار سطح؛ توضیح‌پذیر و قابل‌ردیابی | `detection/config.yaml`، `scoring.py` (noisy-OR)، `explain.py`، `monitoring/models.Alert` | `test_5_3_every_alert_carries_the_required_content_and_is_explainable`، `test_noisy_or_points_sum_to_score`، `test_every_alert_is_explainable_and_traceable` |
| ۵٫۴ گردش‌کار تحقیق: بازبینی، شواهد، **تاریخچه‌ی فعالیت**، ثبت یافته، درخواست اطلاعات، مثبت کاذب، ارجاع، بستن با تصمیم مستند؛ تاریخچه‌ی کامل | `monitoring/services/alerts.WORKFLOW` + `StateMachine`، خط زمان؛ `user_history` | رابط: صفحه‌ی هشدار («تاریخچه‌ی فعالیتِ این فرد») | `test_flow1…`، `test_5_4_*` |
| **مهم:** هیچ مجازات/تعلیق/اتهامِ خودکار از روی امتیاز؛ بازبینی انسانی لازم است | موتور فقط هشدار می‌نویسد؛ یادداشت الزامی؛ «تأیید تخلف» یافته‌ی انسانیِ ثبت‌شده است | `test_detection_never_modifies_users`، `test_assistant_never_changes_state` |

## ۶. الزام‌های یکپارچگی
| نمونه در سند | پیاده‌سازی | اثبات |
|---|---|---|
| الگوی غیرعادی ← هشدار | `monitoring/services/runs.run_detection` | `test_flow1…` |
| بازبین منابع انسانی یا انطباق هشدار را بررسی می‌کند | `ALERT_DOMAIN_VISIBILITY` در `core/rbac.py` | `test_alert_visibility_by_role` |
| نگرانی کیفیت به سوپروایزر مناسب ارجاع می‌شود | `route_to_supervisor`؛ ارجاع برگشتی با سیگنال Observer | `test_flow5…` |
| نتیجه‌ی بازبینی سوپروایزر در پرونده‌های عملیاتی بازتاب می‌یابد | `decide_review` ← `hr_lifecycleevent(supervision_review)` | `test_4_5_review_decision_is_traceable_and_reflected_in_operational_records` |
| ناهنجاری‌های تکراری ← پایش طولی بدون پیش‌داوریِ تخلف | `longitudinal_context`، `user_history` («هشدارها یافته نیستند») | `test_flow2…` |
| ≥ ۳ سناریوی سرتاسری | چهار سناریو (بند ۸) | `test_e2e.py` |
| یکپارچگی با پلتفرم موجود (Go) | [ARCHITECTURE.md §۹](ARCHITECTURE.md) | – |

## ۷. الزام‌های فنی و معماری
| بند | محل |
|---|---|
| ۷٫۱ API ساخت‌یافته، سرویس‌های ماژولار، احراز هویت/مجوز، اعتبارسنجی، جداسازی منطق، مدیریت خطا، **لاگ**، حسابرسی، مستندات API، تراکنش | `views → services → models`؛ سریالایزرهای DRF؛ `core/errors.py`؛ `LOGGING` و لاگر `aramana.security` (`config/settings.py`، `core/permissions.py`، `accounts/services.py`)؛ `core/audit.py`؛ Swagger در `/api/docs/` و [openapi.yaml](../openapi.yaml)؛ `transaction.atomic` در serviceها. آزمون‌ها: `test_7_4_denials_and_failed_logins_are_logged`، `test_api_docs_and_schema_are_served` |
| سرویس‌های هوش مصنوعیِ پایتون سازگار با هسته‌ی Go؛ توجیه فناوری | [ARCHITECTURE.md §۹](ARCHITECTURE.md)، [TECHNICAL_REPORT.md](TECHNICAL_REPORT.md) |
| ۷٫۲ ERD، schema، رابطه‌ها، مرزهای مالکیت داده، تاریخچه‌ی حسابرسی، ایندکس، نگهداشت، جداسازی بالینی/مدیریتی | [ARCHITECTURE.md §۳](ARCHITECTURE.md) (ERD مرمید، فهرست جدول‌ها، یادداشت نگهداشت)؛ مرز اپ‌ها = مالکیت داده |
| ۷٫۳ مهندسی ویژگی، انتخاب مدل، امتیاز توضیح‌پذیر، ارزیابی، مدیریت مثبت کاذب، نسخه‌بندی، بازتولیدپذیری؛ روش بدون داده‌ی برچسب‌دار | `detection/features.py`، `config.yaml`، `evaluate`، `evaluate_llm`، بازخورد مثبت کاذب در خلاصه‌ی پایش، `ruleset_version`/`model_version` روی هر هشدار؛ [DATASET.md](DATASET.md). آزمون‌ها: `test_7_3_*`، `test_evaluation_meets_targets_and_no_hard_negative_false_positives`، `test_engine_is_deterministic_and_idempotent` |
| ۷٫۴ احراز هویت، مجوز، کمترین دسترسی، حفاظت داده‌ی حساس، ارتباط امن API، لاگ حسابرسی، حداقل‌سازی داده، رازها، آسیب‌پذیری‌های رایج؛ بدون داده‌ی واقعی مراجع | JWT + قفل حساب؛ مجوزِ پیش‌فرض‌رد؛ مراجعِ نام‌مستعار و پوشاندن؛ حسابرسی زنجیره‌ای؛ **هدرهای امنیتی (CSP، قاب‌بندی، sniffing، referrer، سیاست مجوزها، HSTS در تولید)** و پاسخ‌های بدون کش؛ رازها فقط از محیط؛ ORM پارامتری؛ سریالایزرهای سخت‌گیر؛ بدون `dangerouslySetInnerHTML`. آزمون‌ها: `test_security.py`، `test_7_4_security_headers_on_api_and_app` |
| ۷٫۵ رابط وب: داشبورد منابع انسانی، داشبورد سوپروایزر، داشبورد پایش، جزئیات هشدار و گردش‌کار، ناوبری ویژه‌ی نقش | `frontend/src/features/{hr,supervision,monitoring,…}`؛ ناوبری از سرور (`/auth/me`) | `e2e/smoke.cjs` (همه‌ی نقش‌ها، فارسی و انگلیسی) |

## ۸. سناریوهای الزامی
| سناریو | هشدار از پیش ساخته | اثبات |
|---|---|---|
| ۱ فعالیت مشکوک جلسه‌ها | رکوردهای هم‌پوشانِ جلسه (۱۵ جفت) | `test_scenario1_overlapping_sessions`، `test_flow1…` |
| ۲ شبکه‌ی ارجاعِ غیرعادی (و تخصص مشروع هشدار نگیرد) | تمرکز ارجاع + «سرکوب‌شده: با سیاست توضیح‌پذیر» | `test_scenario2_referral_network_and_policy_suppression`، `test_flow2…` |
| ۳ تأییدهای غیرعادی سوپروایزر | انفجار تأیید / نبود مستندات | `test_scenario3…`، `test_flow3…` |
| ۴ فعالیت مدیریتی غیرمجاز | انفجار دسترسی ردشده، هشدار امنیتی | `test_scenario4_admin_out_of_scope`، `test_flow4…` |

## ۹. الزام‌های داده
مجموعه‌داده‌ی مصنوعی (کاربران/نقش‌ها، پروفایل‌ها، سوپروایزرها و زیردستان، جلسه‌ها، ارجاع‌ها، تأییدها، فعالیت‌های مدیریتی، رویدادهای دسترسی، رکوردهای تحقیق، توسعه‌ی حرفه‌ای) با موردهای عادی **و** ناهنجار، به‌علاوه‌ی توضیح ساختار، فرض‌ها، ویژگی‌ها، روش تولید ناهنجاری، محدودیت‌ها و مسیر گذار به داده‌ی واقعی: `backend/seed/generate.py`، [DATASET.md](DATASET.md)؛ آزمون `test_9_dataset_has_every_required_record_type`. هیچ داده‌ی شخصی، بالینی یا محرمانه‌ی واقعی استفاده نشده است.

## ۱۰. تحویل‌دادنی‌ها
| تحویل‌دادنی | محل |
|---|---|
| **الف. معماری و طراحی** (نمودار سیستم، معماری ماژول/سرویس، ERD، ماتریس نقش و مجوز، مستندات API، نمودار جریان داده، معماری تشخیص تقلب، طراحی امنیت و حریم خصوصی) | [ARCHITECTURE.md](ARCHITECTURE.md)، [RBAC_MATRIX.md](../RBAC_MATRIX.md)، [openapi.yaml](../openapi.yaml)، `/api/docs/` |
| **ب. نمونه‌ی اجرایی** (پنل‌های منابع انسانی، سوپروایزر و پایش، موتور یکپارچه، ≥ ۴ سناریو، گردش‌کار تحقیق، داده‌ی مصنوعی) | `backend/` و `frontend/`؛ [GUIDE.md](GUIDE.md) |
| **ج. کد و مستندات مهندسی** (کد، ساختار، README/نصب، نمونه‌ی محیط، تست‌ها، مستندات API، راه‌اندازی پایگاه‌داده/مهاجرت، فرض‌ها و محدودیت‌ها) | مخزن؛ [README.fa.md](../../README.fa.md)؛ `backend/.env.example`؛ `backend/tests/`؛ مهاجرت‌ها در `backend/*/migrations/`؛ [GUIDE.md](GUIDE.md)؛ [TECHNICAL_REPORT.md](TECHNICAL_REPORT.md) |
| **د. گزارش فنی** (تصمیم‌ها، فناوری، روش‌شناسی، عملکرد تشخیص، محدودیت‌ها/مثبت کاذب، امنیت، مقیاس‌پذیری، هزینه‌ها، نقشه‌ی راه) | [TECHNICAL_REPORT.md](TECHNICAL_REPORT.md) |
| **ه. ارائه‌ی فنی** | [PRESENTATION.md](PRESENTATION.md) (سازگار با Marp) |

آزمون `test_10_deliverables_exist` اگر فایلی از تحویل‌دادنی‌ها ناپدید شود شکست می‌خورد.
