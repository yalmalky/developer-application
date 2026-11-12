"""Server checks: /healthz and one-time submit token (no real storage).

Run:  APP_DATA_DIR=/tmp/devapp-idtest DISABLE_BACKGROUND=1 \\
      /workspace/.venv-devapp/bin/python tests/test_health_idempotency.py
"""
from __future__ import annotations

import io
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DISABLE_BACKGROUND", "1")
os.environ.setdefault("FLASK_ENV", "development")
os.environ.setdefault("SECRET_KEY", "test-secret-key-devapp-idempotency")
if "APP_DATA_DIR" not in os.environ:
    os.environ["APP_DATA_DIR"] = tempfile.mkdtemp(prefix="devapp-idtest-")
sys.path.insert(0, ROOT)

import app as devapp  # noqa: E402

MINI_PDF = (
    b"%PDF-1.1\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
    b"3 0 obj<</Type/Page/MediaBox[0 0 3 3]>>endobj\n"
    b"xref\n0 4\n0000000000 65535 f \ntrailer<</Size 4/Root 1 0 R>>\nstartxref\n0\n%%EOF\n"
)
EVIDENCE = "هذا مثال حقيقي واضح يكفي للحد الأدنى."
TECH = "أشرح الخطوات بتفصيل كافٍ هنا حتى يتجاوز الحد الأدنى المطلوب تمامًا."


def valid_form():
    data = {
        "full_name": "TEST idempotency",
        "mobile": "0500000000",
        "email": "test@example.com",
        "city": "Riyadh",
        "start_date": "2026-12-01",
        "developer_account": "لا يوجد",
        "project_count": "1",
        "project_1_name": "App",
        "project_1_link": "https://example.com/app",
        "project_1_role": "alone",
        "project_1_tech": "Flutter",
        "project_1_year": "2024",
        "project_1_live": "yes",
        "unavailable": "لا يوجد",
        "response_time": "30min",
        "work_mode": "remote",
        "salary_range": "7000_9000",
        "salary_exact": "8000",
        "housing": "has",
        "declaration": "yes",
        "csrf_token": devapp.issue_csrf(),
        "submit_token": devapp.issue_submit_token(),
    }
    for sec in devapp.SKILL_SECTIONS:
        data[f"evidence_{sec['id']}"] = EVIDENCE
        for key, _ in sec["questions"]:
            data[key] = "partial"
    for key, _ in devapp.SUPPORT_YESNO:
        data[key] = "yes"
    for key, _ in devapp.LANG_SKILLS:
        data[key] = "good"
    for key, _ in devapp.TECH_QUESTIONS:
        data[key] = TECH
    return data


class HealthAndIdempotency(unittest.TestCase):
    def setUp(self):
        devapp.app.config["TESTING"] = True
        self.client = devapp.app.test_client()

    def test_healthz_and_health(self):
        for path in ("/healthz", "/health"):
            res = self.client.get(path)
            self.assertEqual(res.status_code, 200, path)
            self.assertEqual(res.get_json(), {"ok": True})

    def test_form_includes_submit_token(self):
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        self.assertIn('name="submit_token"', html)
        self.assertIn("جاري إرسال طلبك… لا تغلق الصفحة", html)
        self.assertIn("form.js", html)

    def test_duplicate_token_stores_once(self):
        form = valid_form()
        token = form["submit_token"]
        calls = []

        def fake_save(folder, json_text, cv_bytes, cv_name):
            calls.append(folder)
            return folder

        cv = {"cv": (io.BytesIO(MINI_PDF), "cv.pdf")}
        with patch.object(devapp, "save_submission", side_effect=fake_save):
            first = self.client.post("/", data={**form, **cv}, content_type="multipart/form-data")
            self.assertEqual(first.status_code, 302)
            self.assertTrue(first.headers["Location"].endswith("/shukran"))
            cv2 = {"cv": (io.BytesIO(MINI_PDF), "cv.pdf")}
            # Reuse the same csrf + submit tokens (double POST).
            form2 = dict(form)
            form2["submit_token"] = token
            form2["csrf_token"] = form["csrf_token"]
            second = self.client.post("/", data={**form2, **cv2}, content_type="multipart/form-data")
            self.assertEqual(second.status_code, 302)
            self.assertTrue(second.headers["Location"].endswith("/shukran"))
        self.assertEqual(len(calls), 1, f"expected one stored folder, got {calls}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
