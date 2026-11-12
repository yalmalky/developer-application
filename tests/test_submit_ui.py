"""Headless checks: warmup ping, Arabic loading state, single POST on double click.

Submit is intercepted and aborted. Nothing is stored.
Run:  /workspace/.venv-pw/bin/python tests/test_submit_ui.py
      BASE_URL=https://... /workspace/.venv-pw/bin/python tests/test_submit_ui.py
"""
import os, subprocess, sys, time, urllib.request
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = os.environ.get("BASE_URL")
CHROME = os.environ.get("CHROME", "/usr/bin/google-chrome")
MINI_PDF = (
    b"%PDF-1.1\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
    b"3 0 obj<</Type/Page/MediaBox[0 0 3 3]>>endobj\n"
    b"xref\n0 4\n0000000000 65535 f \ntrailer<</Size 4/Root 1 0 R>>\nstartxref\n0\n%%EOF\n"
)
EVIDENCE = "هذا مثال حقيقي واضح يكفي للحد الأدنى."
TECH = "أشرح الخطوات بتفصيل كافٍ هنا حتى يتجاوز الحد الأدنى المطلوب تمامًا."
MSG = "جاري إرسال طلبك… لا تغلق الصفحة"


def fill_required(pg, tmp_cv):
    pg.fill("input[name=full_name]", "TEST - submit ui")
    pg.fill("input[name=mobile]", "0500000000")
    pg.fill("input[name=email]", "test@example.com")
    pg.fill("input[name=city]", "Riyadh")
    pg.fill("input[name=start_date]", "2026-12-01")
    pg.set_input_files("input#cv", tmp_cv)
    pg.fill("input[name=project_1_name]", "TEST project 1")
    pg.fill("input[name=project_1_link]", "https://example.com/p1")
    pg.check("input[name=project_1_role][value=team]")
    pg.fill("input[name=project_1_tech]", "Flutter 1")
    pg.fill("input[name=project_1_year]", "2021")
    pg.check("input[name=project_1_live][value=yes]")
    pg.fill("input[name=developer_account]", "لا يوجد")
    for name in ("apps", "ai", "cameras", "lms", "comms"):
        pg.fill(f"textarea[name=evidence_{name}]", EVIDENCE)
    for name in (
        "apps_build", "apps_publish", "apps_iap", "apps_maintain", "apps_web",
        "apps_hybrid", "apps_swift", "apps_backend", "apps_db", "apps_deploy", "apps_git",
        "ai_daily", "ai_review", "ai_detect", "ai_secrets",
        "cam_python", "cam_opencv", "cam_yolo", "cam_rtsp", "cam_minipc", "cam_count", "cam_coord",
        "lms_accounts", "lms_content", "lms_pay", "lms_cert", "lms_admin", "lms_pdpl",
        "com_lang", "com_explain", "com_estimate", "com_docs", "com_secrets",
    ):
        pg.check(f'input[name="{name}"][value="partial"]')
    for name in (
        "support_available", "support_tickets", "support_daily",
        "support_afterhours", "support_test",
    ):
        pg.check(f'input[name="{name}"][value="yes"]')
    pg.check('input[name="response_time"][value="30min"]')
    pg.fill("input[name=unavailable]", "لا يوجد")
    pg.check('input[name="work_mode"][value="remote"]')
    pg.check('input[name="salary_range"][value="7000_9000"]')
    pg.fill("input[name=salary_exact]", "8000")
    pg.check('input[name="housing"][value="has"]')
    for name in ("lang_ar_reading", "lang_ar_writing", "lang_en_reading", "lang_en_writing"):
        pg.check(f'input[name="{name}"][value="good"]')
    for name in (
        "tech_ios_release", "tech_subscriptions", "tech_capacitor", "tech_rtsp_count",
        "tech_payments", "tech_certificates", "tech_outage", "tech_ai_use", "tech_git",
    ):
        pg.fill(f'textarea[name="{name}"]', TECH)
    pg.check("input[name=declaration]")


def run(base, tmp_cv):
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=CHROME, headless=True)
        pg = b.new_page()
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))

        healthz = {"count": 0}
        def on_req(req):
            if "/healthz" in req.url and req.method == "GET":
                healthz["count"] += 1
        pg.on("request", on_req)
        pg.goto(base)
        pg.evaluate("localStorage.clear()")
        pg.reload()
        pg.wait_for_timeout(800)
        assert healthz["count"] >= 1, f"page open should quietly ping /healthz, got {healthz['count']}"
        print("OK: page open pinged /healthz")

        js = pg.evaluate("() => document.querySelector('script[src*=\"form.js\"]') && document.querySelector('script[src*=\"form.js\"]').src")
        src = pg.evaluate("""() => fetch(document.querySelector('script[src*=\"form.js\"]').src, {cache:'no-store'}).then(r => r.text())""")
        assert "submit-v2" in src, "form.js is not the new version"
        assert MSG in src
        print("OK: form.js is submit-v2")

        fill_required(pg, tmp_cv)

        posts = []
        release_health = {"go": False}

        def handle(route):
            from urllib.parse import urlparse
            url = route.request.url
            method = route.request.method
            path = urlparse(url).path or "/"
            if path.rstrip("/") == "/healthz" and method == "GET":
                # Hold briefly so the overlay is visible before the native POST.
                if not release_health["go"]:
                    pg.wait_for_timeout(800)
                route.fulfill(status=200, content_type="application/json", body='{"ok":true}')
                return
            if method == "POST" and path in ("/", ""):
                posts.append(url)
                route.abort()
                return
            route.continue_()

        pg.route("**/*", handle)
        # Double click / Enter must produce a single POST.
        btn = pg.locator("#submit-btn")
        btn.click()
        # Overlay should appear immediately (healthz may still be held).
        pg.wait_for_selector("#submit-overlay:not([hidden])", timeout=3000)
        assert MSG in pg.inner_text("#submit-overlay")
        assert pg.locator("#submit-btn").is_disabled()
        print("OK: loading overlay visible with Arabic message; button disabled")
        # Second click + Enter must not queue another submit.
        try:
            btn.click(timeout=500, force=True)
        except Exception:
            pass
        pg.keyboard.press("Enter")
        pg.wait_for_timeout(300)
        release_health["go"] = True
        # Wait for the single (aborted) POST.
        for _ in range(40):
            if posts:
                break
            pg.wait_for_timeout(100)
        pg.wait_for_timeout(800)
        assert len(posts) == 1, f"expected exactly one POST, got {len(posts)}"
        print("OK: double click / Enter sent one intercepted POST (nothing stored)")
        assert not errs, errs
        b.close()


if __name__ == "__main__":
    cv_path = "/tmp/devapp-test-cv.pdf"
    with open(cv_path, "wb") as f:
        f.write(MINI_PDF)
    if BASE:
        run(BASE, cv_path)
    else:
        env = dict(os.environ, PORT="5099", FLASK_ENV="development", DISABLE_BACKGROUND="1",
                   APP_DATA_DIR="/tmp/devapp-submittest", SERVER_PY=os.environ.get("SERVER_PY", ""))
        py = os.environ.get("SERVER_PY") or os.environ.get("DEVAPP_PY") or sys.executable
        # Prefer the app venv if this interpreter is Playwright-only.
        srv = subprocess.Popen([py, "app.py"], cwd=ROOT, env={k: v for k, v in env.items() if k != "SERVER_PY"},
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            for _ in range(50):
                try:
                    urllib.request.urlopen("http://127.0.0.1:5099/healthz"); break
                except Exception:
                    time.sleep(0.2)
            else:
                raise SystemExit("local server did not start")
            run("http://127.0.0.1:5099/", cv_path)
        finally:
            srv.terminate()
    print("ALL PASSED")
