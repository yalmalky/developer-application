"""Headless browser check: adding/removing project blocks must keep typed values.

Run:  python tests/test_projects_ui.py            (starts a local server on :5098)
      BASE_URL=https://... python tests/test_projects_ui.py --no-submit
The submit step is intercepted in the browser and aborted, so nothing is ever stored.
Requires: playwright + a Chromium/Chrome (CHROME env var to override the path).
"""
import os, subprocess, sys, time, urllib.request
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = os.environ.get("BASE_URL")
NO_SUBMIT = "--no-submit" in sys.argv
CHROME = os.environ.get("CHROME", "/usr/bin/google-chrome")


def fill_project(pg, i, role="team", live="yes"):
    pg.fill(f"input[name=project_{i}_name]", f"TEST project {i}")
    pg.fill(f"input[name=project_{i}_link]", f"https://example.com/p{i}")
    pg.check(f"input[name=project_{i}_role][value={role}]")
    pg.fill(f"input[name=project_{i}_tech]", f"Flutter {i}")
    pg.fill(f"input[name=project_{i}_year]", str(2020 + i))
    pg.check(f"input[name=project_{i}_live][value={live}]")


def assert_project(pg, i, role="team", live="yes"):
    got = (
        pg.input_value(f"input[name=project_{i}_name]"),
        pg.input_value(f"input[name=project_{i}_link]"),
        pg.is_checked(f"input[name=project_{i}_role][value={role}]"),
        pg.input_value(f"input[name=project_{i}_tech]"),
        pg.input_value(f"input[name=project_{i}_year]"),
        pg.is_checked(f"input[name=project_{i}_live][value={live}]"),
    )
    want = (f"TEST project {i}", f"https://example.com/p{i}", True, f"Flutter {i}", str(2020 + i), True)
    assert got == want, f"project {i} lost values: {got}"


def run(base):
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=CHROME, headless=True)
        pg = b.new_context().new_page()
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto(base)
        pg.evaluate("localStorage.clear()")
        pg.reload()
        pg.fill("input[name=full_name]", "TEST - headless check")
        fill_project(pg, 1)
        pg.click("#add-project")
        assert pg.locator("#projects .project").count() == 2
        assert_project(pg, 1)
        assert pg.input_value("input[name=project_2_name]") == ""
        assert pg.input_value("input[name=full_name]") == "TEST - headless check"
        print("OK: project 1 kept after adding project 2")
        if NO_SUBMIT:
            b.close(); return
        fill_project(pg, 2, role="alone", live="no")
        pg.click("#add-project")
        assert pg.locator("#projects .project").count() == 3
        assert_project(pg, 1); assert_project(pg, 2, role="alone", live="no")
        fill_project(pg, 3, role="maintenance")
        pg.click("#add-project")  # 4th, then remove it
        pg.click("#remove-project")
        assert pg.locator("#projects .project").count() == 3
        assert_project(pg, 1); assert_project(pg, 2, role="alone", live="no"); assert_project(pg, 3, role="maintenance")
        assert pg.input_value("#project_count") == "3"
        print("OK: projects 1-3 kept after adding 2 more and removing the last")
        # Capture what the browser would POST, then abort it (nothing stored).
        captured = {}
        def handle(route):
            if route.request.method == "POST":
                captured["body"] = route.request.post_data_buffer or b""
                route.abort()
            else:
                route.continue_()
        pg.route("**/*", handle)
        pg.evaluate("document.getElementById('apply-form').noValidate = true;"
                    "HTMLFormElement.prototype.submit.call(document.getElementById('apply-form'))")
        pg.wait_for_timeout(1500)
        body = captured.get("body", b"").decode("utf-8", "replace")
        assert body, "no POST captured"
        for i, role, live in [(1, "team", "yes"), (2, "alone", "no"), (3, "maintenance", "yes")]:
            for k, v in [("name", f"TEST project {i}"), ("link", f"https://example.com/p{i}"), ("role", role),
                         ("tech", f"Flutter {i}"), ("year", str(2020 + i)), ("live", live)]:
                assert f'name="project_{i}_{k}"\r\n\r\n{v}\r\n' in body, f"payload missing project_{i}_{k}"
        assert 'name="project_count"\r\n\r\n3\r\n' in body
        assert "project_4_" not in body
        print("OK: submit payload has all 3 projects (request aborted, nothing stored)")
        assert not errs, errs
        b.close()


if __name__ == "__main__":
    if BASE:
        run(BASE)
    else:
        env = dict(os.environ, PORT="5098", FLASK_ENV="development", DISABLE_BACKGROUND="1",
                   APP_DATA_DIR="/tmp/devapp-uitest")
        srv = subprocess.Popen([os.environ.get("SERVER_PY", sys.executable), "app.py"], cwd=ROOT, env=env,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            for _ in range(50):
                try: urllib.request.urlopen("http://127.0.0.1:5098/"); break
                except Exception: time.sleep(0.2)
            run("http://127.0.0.1:5098/")
        finally:
            srv.terminate()
    print("ALL PASSED")
