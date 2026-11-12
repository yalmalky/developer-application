from __future__ import annotations

import json
import os
import re
import secrets
import time
from collections import defaultdict, deque
from datetime import datetime, timezone, timedelta
from io import BytesIO
from pathlib import Path
from typing import Any
from zipfile import ZipFile

from flask import (
    Flask,
    abort,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from store import StorageError, save_submission

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
app.config["MAX_CONTENT_LENGTH"] = 12 * 1024 * 1024
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("FLASK_ENV") != "development"

RIYADH = timezone(timedelta(hours=3))
MAX_CV_BYTES = 10 * 1024 * 1024
ALLOWED_CV = {
    ".pdf": "pdf",
    ".doc": "doc",
    ".docx": "docx",
}
MIN_TECH = 40
MIN_EVIDENCE = 20

# In-memory rate limit (per process). Enough to blunt casual spam.
_RATE: dict[str, deque] = defaultdict(deque)
RATE_MAX = 5
RATE_WINDOW = 3600

SKILL_SECTIONS = [
    {
        "id": "apps",
        "num": "ثانيًا",
        "title": "تطوير تطبيقات الجوال والويب وصيانتها",
        "note": "",
        "evidence": "اذكر مثالًا أو رابط عمل/تطبيق منشور يوضح خبرتك في هذا القسم",
        "questions": [
            ("apps_build", "بناء تطبيق جوال (iPhone / Android) من الصفر حتى النشر"),
            ("apps_publish", "نشر تطبيق بنفسي على App Store و Google Play (TestFlight، ومراجعة المتجر، والرد على الرفض)"),
            ("apps_iap", "الاشتراكات والشراء داخل التطبيق (Subscriptions / In-App Purchases)"),
            ("apps_maintain", "صيانة وتحديث تطبيقات موجودة، وإصلاح الأعطال (Bugs) وتقارير التعطّل"),
            ("apps_web", "تطبيقات الويب (مثل React / Next.js)"),
            ("apps_hybrid", "أدوات تطبيقات الجوال: Capacitor أو React Native أو Flutter"),
            ("apps_swift", "Swift / تطوير iOS الأصلي (ميزة إضافية)"),
            ("apps_backend", "بناء الخلفية (Backend) وواجهات الربط (APIs)"),
            ("apps_db", "قواعد البيانات (مثل PostgreSQL / MySQL / Firebase / MongoDB)"),
            ("apps_deploy", "الاستضافة والنشر على السيرفرات أو السحابة (مثل Render / AWS / غيرها)"),
            ("apps_git", "استخدام Git و GitHub لإدارة الكود"),
        ],
    },
    {
        "id": "ai",
        "num": "ثالثًا",
        "title": "استخدام أدوات الذكاء الاصطناعي في البرمجة",
        "note": "استخدام أدوات الذكاء الاصطناعي في البرمجة مرحّب به ومتوقّع في هذه الوظيفة.",
        "evidence": "مثال لمرة استخدمت فيها الذكاء الاصطناعي، وكيف تأكدت أن الناتج صحيح",
        "questions": [
            ("ai_daily", "أستخدم أدوات مثل Cursor أو ChatGPT أو Claude أو Copilot في شغلي اليومي"),
            ("ai_review", "أراجع وأختبر الكود الذي تقترحه الأداة قبل اعتماده، وأفهم ماذا يفعل"),
            ("ai_detect", "أعرف أكتشف متى تعطي الأداة حلًا خاطئًا أو غير آمن"),
            ("ai_secrets", "لا أضع كلمات المرور أو بيانات العملاء الحساسة داخل هذه الأدوات"),
        ],
    },
    {
        "id": "cameras",
        "num": "رابعًا",
        "title": "أنظمة مراقبة الكاميرات والرؤية الحاسوبية",
        "note": "",
        "evidence": "اذكر مشروعًا مشابهًا اشتغلت عليه، أو رابط كود/فيديو يوضح عملك",
        "questions": [
            ("cam_python", "البرمجة بلغة Python"),
            ("cam_opencv", "مكتبة OpenCV لمعالجة الصور والفيديو"),
            ("cam_yolo", "نماذج كشف الأجسام وتدريبها أو تحسينها (مثل YOLO أو ما يشابهها)"),
            ("cam_rtsp", "التعامل مع كاميرات IP وبث RTSP وأجهزة التسجيل NVR"),
            ("cam_minipc", "تشغيل برامج تحليل الفيديو على أجهزة صغيرة (Mini PC) بشكل مستقر"),
            ("cam_count", "قياس وتحسين دقة العدّ (عدّ الأشخاص أو الأشياء من الفيديو)"),
            ("cam_coord", "التنسيق مع العميل والمندوب وفني التركيب، والحضور للموقع عند الحاجة لتسليم المشروع"),
        ],
    },
    {
        "id": "lms",
        "num": "خامسًا",
        "title": "منصة التدريب والدورات الإلكترونية",
        "note": "",
        "evidence": "اذكر مثالًا أو رابط عمل يوضح خبرتك في هذا القسم",
        "questions": [
            ("lms_accounts", "حسابات المستخدمين (تسجيل، دخول، استعادة كلمة المرور، صلاحيات)"),
            ("lms_content", "رفع محتوى الدورات والفيديو وحمايته من النسخ"),
            ("lms_pay", "الدفع الإلكتروني عبر بوابات سعودية (مثل ميسّر Moyasar / HyperPay / Tap) مع مدى و Apple Pay"),
            ("lms_cert", "إصدار شهادات تلقائيًا عند إكمال الدورة، مع رابط أو رمز QR للتحقق منها"),
            ("lms_admin", "لوحة تحكم للإدارة (المتدربون، المبيعات، التقارير)"),
            ("lms_pdpl", "معرفة بنظام حماية البيانات الشخصية السعودي (PDPL) (ميزة إضافية)"),
        ],
    },
    {
        "id": "comms",
        "num": "ثامنًا",
        "title": "التواصل وطريقة العمل",
        "note": "",
        "evidence": "مثال لمرة شرحت فيها مشكلة تقنية لعميل أو مدير غير تقني",
        "questions": [
            ("com_lang", "التواصل بوضوح باللغة العربية، واستخدام الإنجليزية في المصطلحات والتوثيق التقني"),
            ("com_explain", "شرح الأمور التقنية لأشخاص غير تقنيين بكلام بسيط"),
            ("com_estimate", "تقدير المدة المطلوبة للمهام بواقعية، وتقسيم العمل إلى مراحل"),
            ("com_docs", "توثيق العمل (طريقة التشغيل، الإعدادات، الخطوات) بحيث يقدر غيري يكمل عليه"),
            ("com_secrets", "أساسيات الأمان: حفظ المفاتيح وكلمات المرور بشكل آمن، وأن تكون الحسابات باسم الشركة"),
        ],
    },
]

SUPPORT_YESNO = [
    ("support_available", "هل أنت مستعد تكون متاحًا ومتجاوبًا مع الدعم الفني والمشاكل طوال ساعات العمل يوميًا (وليس حسب الحاجة فقط)؟"),
    ("support_tickets", "هل أنت مستعد لاستقبال بلاغات واستفسارات المستخدمين والرد عليها ومتابعتها حتى تُحل؟"),
    ("support_daily", "هل توافق على متابعة يومية مع الإدارة (تحديث قصير يومي بما تم إنجازه)؟"),
    ("support_afterhours", "هل أنت مستعد للتعامل مع الأعطال الطارئة الكبيرة بعد الدوام، وفق ترتيب يُتفق عليه؟"),
    ("support_test", "هل توافق على إجراء اختبار عملي قصير (2–3 ساعات) أو جلسة حل مشكلة مع مشاركة الشاشة؟"),
]

TECH_QUESTIONS = [
    ("tech_ios_release", "اذكر خطوات رفع تحديث لتطبيق iOS من البناء حتى TestFlight ثم إرساله لمراجعة App Store، وماذا تفعل إذا رفضت آبل المراجعة؟"),
    ("tech_subscriptions", "كيف تطبّق الاشتراكات التلقائية التجديد (Auto-Renewable Subscriptions) داخل التطبيق، وكيف تتم عملية التحقق من جهة الخادم (server-side verification)؟"),
    ("tech_capacitor", "تطبيق يعمل بشكل صحيح في المتصفح، لكنه يفشل داخل بناء iOS يعتمد على Capacitor أو WebView. كيف تبدأ في تشخيص المشكلة وحلّها؟"),
    ("tech_rtsp_count", "كيف تعدّ أجسامًا تعبر منطقة محددة (zone / line) في بث كاميرا RTSP على جهاز Mini PC، وكيف تتجنّب العدّ المكرر لنفس الجسم؟"),
    ("tech_payments", "كيف تربط بوابة دفع سعودية (مثل Moyasar أو HyperPay أو Tap) مع إشعارات Webhook، بحيث لا تُمنح صلاحية الدخول للدورة إذا فشل الدفع أو تكرر نفس الإشعار؟"),
    ("tech_certificates", "كيف تُصدر شهادات إكمال قابلة للتحقق (مثل رمز QR أو رابط تحقق)، بحيث يمكن التأكد أن الشهادة غير مزوّرة؟"),
    ("tech_outage", "إذا وقع عطل في نظام الإنتاج الساعة 10 صباحًا أثناء ساعات العمل، ماذا تفعل في أول 15 دقيقة، وكيف تتواصل معنا؟"),
    ("tech_ai_use", "كيف تستخدم أدوات الذكاء الاصطناعي في البرمجة (مثل Cursor أو ChatGPT أو Copilot)، وكيف تتحقق أن الناتج صحيح وآمن قبل اعتماده؟ اذكر مثالًا."),
    ("tech_git", "صف طريقة عملك مع Git: الفروع، وطلبات الدمج (Pull Requests)، والالتزامات (Commits)، وما الذي لا يجب رفعه إلى المستودع."),
]

ROLE_LABELS = {
    "alone": "بنيته وحدي",
    "team": "ضمن فريق",
    "maintenance": "صيانة/تحديث فقط",
}
SALARY_RANGES = [
    ("under_5000", "أقل من 5,000"),
    ("5000_7000", "5,000–7,000"),
    ("7000_9000", "7,000–9,000"),
    ("9000_12000", "9,000–12,000"),
    ("over_12000", "أكثر من 12,000"),
]
RESPONSE_TIMES = [
    ("15min", "15 دقيقة"),
    ("30min", "30 دقيقة"),
    ("1hour", "ساعة"),
    ("more", "أكثر من ساعة"),
]
WORK_MODES = [
    ("onsite", "حضوري في المقر"),
    ("hybrid", "هجين (المقر + عن بُعد)"),
    ("remote", "عن بُعد بالكامل (من البيت أو موقعك)"),
]
HOUSING = [
    ("needs", "أحتاج سكنًا توفّره الشركة"),
    ("has", "لديّ سكن ولا أحتاج"),
]


def _now() -> datetime:
    return datetime.now(RIYADH)


def client_ip() -> str:
    # Render sits behind a proxy; use the first forwarded IP if present.
    fwd = request.headers.get("X-Forwarded-For", "")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.remote_addr or "0.0.0.0"


def rate_limited(ip: str) -> bool:
    now = time.time()
    q = _RATE[ip]
    while q and now - q[0] > RATE_WINDOW:
        q.popleft()
    return len(q) >= RATE_MAX


def rate_hit(ip: str) -> None:
    _RATE[ip].append(time.time())


def issue_csrf() -> str:
    token = secrets.token_urlsafe(32)
    session["csrf"] = token
    return token


def valid_csrf(token: str | None) -> bool:
    expected = session.get("csrf")
    if not token or not expected:
        return False
    return secrets.compare_digest(str(token), str(expected))


def clean(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\x00", "")
    return text.strip()


def is_email(v: str) -> bool:
    return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", v)) and len(v) <= 200


def is_http_url(v: str) -> bool:
    return bool(re.match(r"^https?://[^\s]+$", v, re.I)) and len(v) <= 500


def slugify_name(name: str) -> str:
    arabic = re.sub(r"[^\w\s\u0600-\u06FF-]", "", name, flags=re.UNICODE)
    arabic = re.sub(r"\s+", "-", arabic).strip("-")
    if not arabic:
        arabic = "candidate"
    return arabic[:40]


def detect_cv(filename: str, data: bytes) -> str | None:
    ext = Path(filename or "").suffix.lower()
    if ext not in ALLOWED_CV or not data:
        return None
    if ext == ".pdf":
        if data[:5] == b"%PDF-":
            return "pdf"
        return None
    if ext == ".doc":
        # OLE Compound File (legacy .doc) or sometimes a raw Word stream
        if data[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
            return "doc"
        return None
    if ext == ".docx":
        if data[:2] != b"PK":
            return None
        try:
            with ZipFile(BytesIO(data)) as zf:
                names = zf.namelist()
            if any(n.startswith("word/") for n in names) or "[Content_Types].xml" in names:
                return "docx"
        except Exception:
            return None
        return None
    return None


def parse_projects(form) -> tuple[list[dict], str | None]:
    try:
        count = int(form.get("project_count") or "1")
    except ValueError:
        count = 1
    if count < 1 or count > 5:
        return [], "عدد المشاريع يجب أن يكون بين 1 و 5."
    projects = []
    for i in range(1, count + 1):
        name = clean(form.get(f"project_{i}_name"))
        link = clean(form.get(f"project_{i}_link"))
        role = clean(form.get(f"project_{i}_role"))
        tech = clean(form.get(f"project_{i}_tech"))
        year = clean(form.get(f"project_{i}_year"))
        live = clean(form.get(f"project_{i}_live"))
        # Skip completely empty trailing slots (in case JS count drifts)
        if not any([name, link, role, tech, year, live]):
            continue
        if not name or not link or not role or not tech or not year or not live:
            return [], f"أكمل جميع حقول المشروع رقم {i}."
        if not is_http_url(link):
            return [], f"رابط المشروع رقم {i} غير صحيح. استخدم رابطًا يبدأ بـ https:// أو http://."
        if role not in ROLE_LABELS:
            return [], f"اختر دورك في المشروع رقم {i}."
        if live not in ("yes", "no"):
            return [], f"حدد هل المشروع رقم {i} لا يزال يعمل."
        if not re.fullmatch(r"(19|20)\d{2}", year):
            return [], f"سنة المشروع رقم {i} غير صحيحة."
        year_n = int(year)
        if year_n < 2000 or year_n > _now().year + 1:
            return [], f"سنة المشروع رقم {i} خارج النطاق المقبول."
        projects.append(
            {
                "name": name[:200],
                "link": link,
                "role": role,
                "role_label": ROLE_LABELS[role],
                "tech": tech[:400],
                "year": year,
                "still_live": live == "yes",
            }
        )
    if not projects:
        return [], "أضف مشروعًا واحدًا على الأقل."
    if len(projects) > 5:
        return [], "الحد الأقصى خمسة مشاريع."
    return projects, None


def collect_errors(form, files) -> tuple[list[str], dict[str, Any] | None]:
    errors: list[str] = []
    # Honeypot: pretender handled by caller
    name = clean(form.get("full_name"))
    mobile = clean(form.get("mobile"))
    email = clean(form.get("email"))
    city = clean(form.get("city"))
    start = clean(form.get("start_date"))
    linkedin = clean(form.get("linkedin"))
    github = clean(form.get("github"))
    dev_account = clean(form.get("developer_account"))

    if len(name) < 3:
        errors.append("اكتب الاسم الكامل كما في السيرة الذاتية.")
    if len(re.sub(r"\D", "", mobile)) < 8:
        errors.append("رقم الجوال غير مكتمل.")
    if not is_email(email):
        errors.append("البريد الإلكتروني غير صحيح.")
    if len(city) < 2:
        errors.append("اكتب المدينة.")
    if not start:
        errors.append("حدد أقرب تاريخ تقدر تبدأ فيه.")
    else:
        try:
            datetime.strptime(start, "%Y-%m-%d")
        except ValueError:
            errors.append("تاريخ البدء غير صحيح.")
    if linkedin and not is_http_url(linkedin):
        errors.append("رابط LinkedIn غير صحيح. اتركه فارغًا أو ضع رابطًا كاملًا.")
    if github and not is_http_url(github):
        errors.append("رابط GitHub غير صحيح. اتركه فارغًا أو ضع رابطًا كاملًا.")
    if len(dev_account) < 1:
        errors.append("اكتب اسم حساب المطوّر في المتاجر، أو «لا يوجد».")

    projects, perr = parse_projects(form)
    if perr:
        errors.append(perr)

    skills: dict[str, str] = {}
    evidence: dict[str, str] = {}
    for sec in SKILL_SECTIONS:
        ev = clean(form.get(f"evidence_{sec['id']}"))
        if len(ev) < MIN_EVIDENCE:
            errors.append(f"اكتب مثالًا أوضح في قسم «{sec['title']}» (سطران يكفيان).")
        evidence[sec["id"]] = ev
        for key, _label in sec["questions"]:
            val = clean(form.get(key))
            if val not in ("yes", "partial", "no"):
                errors.append(f"اختر نعم / جزئيًا / لا لكل بند في قسم «{sec['title']}».")
                break
            skills[key] = val

    support: dict[str, str] = {}
    for key, _label in SUPPORT_YESNO:
        val = clean(form.get(key))
        if val not in ("yes", "no"):
            errors.append("أجب بنعم أو لا على جميع أسئلة الدعم الفني والتواجد.")
            break
        support[key] = val
    response_time = clean(form.get("response_time"))
    if response_time not in {k for k, _ in RESPONSE_TIMES}:
        errors.append("حدد زمن الرد خلال ساعات العمل.")
    unavailable = clean(form.get("unavailable"))
    if len(unavailable) < 1:
        errors.append("اكتب الأوقات التي لا تكون متاحًا فيها، أو «لا يوجد».")

    work_mode = clean(form.get("work_mode"))
    if work_mode not in {k for k, _ in WORK_MODES}:
        errors.append("اختر طريقة العمل المفضّلة.")
    salary_range = clean(form.get("salary_range"))
    if salary_range not in {k for k, _ in SALARY_RANGES}:
        errors.append("اختر نطاق الراتب المتوقع.")
    salary_exact = clean(form.get("salary_exact")).replace(",", "").replace("،", "").replace(" ", "")
    if not re.fullmatch(r"\d{3,6}", salary_exact):
        errors.append("اكتب الرقم المتوقع للراتب الشهري بالأرقام (بالريال).")
    housing = clean(form.get("housing"))
    if housing not in {k for k, _ in HOUSING}:
        errors.append("حدد وضع السكن.")

    tech: dict[str, str] = {}
    for key, label in TECH_QUESTIONS:
        val = clean(form.get(key))
        if len(val) < MIN_TECH:
            errors.append("أجب على الأسئلة التقنية بخطوات أوضح (بضعة أسطر لكل سؤال).")
            break
        tech[key] = val

    if clean(form.get("declaration")) != "yes":
        errors.append("يلزم الإقرار بأن المعلومات صحيحة قبل الإرسال.")

    cv = files.get("cv")
    cv_bytes = b""
    cv_name = ""
    cv_kind = None
    if cv is None or not getattr(cv, "filename", None):
        errors.append("إرفاق السيرة الذاتية إلزامي (PDF أو Word).")
    else:
        cv_name = Path(cv.filename).name
        try:
            cv_bytes = cv.read()
        except Exception:
            cv_bytes = b""
        if len(cv_bytes) == 0:
            errors.append("ملف السيرة الذاتية فارغ.")
        elif len(cv_bytes) > MAX_CV_BYTES:
            errors.append("حجم السيرة الذاتية يتجاوز 10 ميغابايت.")
        else:
            cv_kind = detect_cv(cv_name, cv_bytes)
            if not cv_kind:
                errors.append("صيغة السيرة الذاتية غير مدعومة. ارفع ملف PDF أو DOC أو DOCX.")

    # De-duplicate while preserving order
    seen = set()
    uniq = []
    for e in errors:
        if e not in seen:
            seen.add(e)
            uniq.append(e)

    if uniq:
        return uniq, None

    payload = {
        "submitted_at": _now().isoformat(timespec="seconds"),
        "full_name": name,
        "mobile": mobile,
        "email": email,
        "city": city,
        "start_date": start,
        "linkedin": linkedin or None,
        "github": github or None,
        "developer_account": dev_account,
        "projects": projects,
        "skills": skills,
        "evidence": evidence,
        "support": {
            **support,
            "response_time": response_time,
            "unavailable": unavailable,
        },
        "work": {
            "mode": work_mode,
            "salary_range": salary_range,
            "salary_exact_sar": int(salary_exact),
            "housing": housing,
        },
        "technical": tech,
        "declaration": True,
        "cv": {"filename": cv_name, "type": cv_kind, "size_bytes": len(cv_bytes)},
    }
    return [], {"payload": payload, "cv_bytes": cv_bytes, "cv_name": cv_name}


@app.context_processor
def inject_globals():
    return {
        "skill_sections": SKILL_SECTIONS,
        "support_yesno": SUPPORT_YESNO,
        "tech_questions": TECH_QUESTIONS,
        "salary_ranges": SALARY_RANGES,
        "response_times": RESPONSE_TIMES,
        "work_modes": WORK_MODES,
        "housing_options": HOUSING,
        "role_labels": ROLE_LABELS,
        "min_tech": MIN_TECH,
        "min_evidence": MIN_EVIDENCE,
    }


@app.after_request
def security_headers(resp):
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Referrer-Policy"] = "no-referrer"
    resp.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com data:; "
        "script-src 'self'; "
        "img-src 'self' data:; "
        "form-action 'self'; "
        "base-uri 'self'; "
        "frame-ancestors 'none'"
    )
    resp.headers["Cache-Control"] = "no-store"
    return resp


@app.get("/health")
def health():
    return {"ok": True}, 200


@app.get("/robots.txt")
def robots():
    return "User-agent: *\nDisallow: /\n", 200, {"Content-Type": "text/plain; charset=utf-8"}


@app.get("/")
def form_get():
    token = issue_csrf()
    return render_template("form.html", csrf_token=token, errors=[], form={}, project_count=1)


@app.get("/shukran")
def thanks():
    if not session.get("submitted"):
        return redirect(url_for("form_get"))
    return render_template("success.html")


@app.post("/")
def form_post():
    # Honeypot: look like success, store nothing.
    if clean(request.form.get("website")) or clean(request.form.get("fax_number")):
        session["submitted"] = True
        return redirect(url_for("thanks"))

    if not valid_csrf(request.form.get("csrf_token")):
        token = issue_csrf()
        return render_template(
            "form.html",
            csrf_token=token,
            errors=["انتهت صلاحية الصفحة. حدّث الصفحة وأعد الإرسال."],
            form=request.form,
            project_count=_safe_count(request.form),
        ), 400

    ip = client_ip()
    if rate_limited(ip):
        token = issue_csrf()
        return render_template(
            "form.html",
            csrf_token=token,
            errors=["حاولت الإرسال مرات كثيرة. انتظر قليلًا ثم أعد المحاولة."],
            form=request.form,
            project_count=_safe_count(request.form),
        ), 429

    errors, parsed = collect_errors(request.form, request.files)
    if errors:
        token = issue_csrf()
        return render_template(
            "form.html",
            csrf_token=token,
            errors=errors,
            form=request.form,
            project_count=_safe_count(request.form),
        ), 400

    assert parsed is not None
    payload = parsed["payload"]
    stamp = _now().strftime("%Y%m%d-%H%M%S")
    folder = f"{stamp}-{slugify_name(payload['full_name'])}"
    # Keep test submissions easy to spot and clean up.
    if payload["full_name"].upper().startswith("TEST") or "اختبار" in payload["full_name"]:
        folder = f"TEST-{folder}"
        payload["is_test"] = True

    json_text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    ext = Path(parsed["cv_name"]).suffix.lower() or ".bin"
    stored_cv_name = f"cv{ext}"
    try:
        save_submission(folder, json_text, parsed["cv_bytes"], stored_cv_name)
    except StorageError:
        app.logger.exception("storage failed")
        token = issue_csrf()
        return render_template(
            "form.html",
            csrf_token=token,
            errors=["تعذّر حفظ الطلب الآن. حاول مرة أخرى بعد دقيقة، وإن تكرر الأمر راسلنا."],
            form=request.form,
            project_count=_safe_count(request.form),
        ), 503

    rate_hit(ip)
    session["submitted"] = True
    session.pop("csrf", None)
    return redirect(url_for("thanks"))


def _safe_count(form) -> int:
    try:
        n = int(form.get("project_count") or 1)
    except ValueError:
        n = 1
    return min(max(n, 1), 5)


@app.errorhandler(413)
def too_large(_e):
    token = issue_csrf()
    return render_template(
        "form.html",
        csrf_token=token,
        errors=["حجم المرفق أكبر من 10 ميغابايت. ارفع ملفًا أصغر."],
        form=request.form if request.form else {},
        project_count=1,
    ), 413


if __name__ == "__main__":
    app.config["SESSION_COOKIE_SECURE"] = False
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", 5055)), debug=True)
