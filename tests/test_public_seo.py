"""Rendered public SEO behavior and CDC BMI calculation boundaries."""

import re
import json
import unittest
from io import BytesIO
from html import unescape
from pathlib import Path
from tempfile import TemporaryDirectory
from xml.etree import ElementTree

from app import create_app
from extensions import db
from app.routes.main_routes import get_bmi_category
from app.services.bmi_reference import _reference_rows, child_bmi_result
from config import Config, normalize_database_url


PRODUCTION = "https://nutritiondietexpertsystem-production.up.railway.app"


class PublicTestConfig(Config):
    TESTING = True
    CHILD_BMI_ENABLED = True
    USDA_SCANNER_WARMUP = False
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_ENGINE_OPTIONS = {}


class DisabledChildTestConfig(PublicTestConfig):
    CHILD_BMI_ENABLED = False


class StagingTestConfig(PublicTestConfig):
    DEPLOYMENT_ENVIRONMENT = "staging"


class PublicSeoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app(PublicTestConfig)

    def setUp(self):
        self.client = self.app.test_client()

    def get(self, path, base_url=PRODUCTION):
        return self.client.get(path, base_url=base_url)

    def test_public_languages_and_metadata(self):
        expected = {
            "/": ("en", PRODUCTION + "/", "/km/"),
            "/km/": ("km", PRODUCTION + "/km/", "/"),
            "/bmi": ("en", PRODUCTION + "/bmi", "/km/bmi"),
            "/km/bmi": ("km", PRODUCTION + "/km/bmi", "/bmi"),
        }
        titles = []
        descriptions = []
        for path, (lang, canonical, alternate_path) in expected.items():
            with self.subTest(path=path):
                response = self.get(path)
                html = response.get_data(as_text=True)
                self.assertEqual(response.status_code, 200)
                self.assertNotIn("noindex", response.headers.get("X-Robots-Tag", ""))
                self.assertIn(f'<html lang="{lang}">', html)
                self.assertIn(f'<link rel="canonical" href="{canonical}"', html)
                self.assertIn(PRODUCTION + alternate_path, html)
                english = PRODUCTION + ("/bmi" if "bmi" in path else "/")
                khmer = PRODUCTION + ("/km/bmi" if "bmi" in path else "/km/")
                for code, href in (("en", english), ("km", khmer), ("x-default", english)):
                    self.assertIn(f'<link rel="alternate" hreflang="{code}" href="{href}"', html)
                    self.assertEqual(len(re.findall(fr'hreflang="{code}"', html)), 1)
                self.assertNotRegex(html, r'<meta[^>]+(?:name|http-equiv)="robots"[^>]+noindex')
                title = unescape(re.search(r'<title>(.*?)</title>', html, re.S).group(1).strip())
                description = unescape(re.search(r'<meta name="description"\s+content="([^"]+)"', html).group(1))
                self.assertTrue(len(title) >= 20)
                self.assertTrue(len(description) >= 50)
                self.assertEqual(len(re.findall(r'<h1(?:\s|>)', html)), 1)
                titles.append(title)
                descriptions.append(description)
                self.assertNotIn("????????", html)
        self.assertEqual(len(set(titles)), 4)
        self.assertEqual(len(set(descriptions)), 4)
        home_html = self.get("/").get_data(as_text=True)
        schema = re.search(r'<script type="application/ld\+json">(.*?)</script>', home_html).group(1)
        self.assertEqual(json.loads(schema)["@type"], "WebSite")
        self.assertIn('href="/km/"', home_html)
        adult_html = self.get("/bmi").get_data(as_text=True)
        self.assertIn('min="20"', adult_html)
        self.assertIn('id="btnClear"', adult_html)
        self.assertNotIn("<built-in method clear", adult_html)

    def test_adult_answers_are_visible_without_calculating(self):
        for path, lang in (("/bmi", "en"), ("/km/bmi", "km")):
            with self.subTest(path=path):
                html = self.get(path).get_data(as_text=True)
                self.assertIn("BMI =", html)
                self.assertIn("[", html)
                self.assertIn("]²", html)
                for boundary in ("18.5", "25", "30"):
                    self.assertIn(boundary, html)
                self.assertIn("20", html)
                self.assertIn("https://www.cdc.gov/bmi/adult-calculator/bmi-categories.html", html)
                self.assertIn('<h3 class="h6 mt-3">', html)
                self.assertNotIn('"@type":"FAQPage"', html)
                if lang == "en":
                    self.assertIn("not a diagnosis", html)
                else:
                    self.assertIn("មិនមែនជារោគវិនិច្ឆ័យ", html)

    def test_home_claims_and_schema_match_visible_content(self):
        for path, name, age in (("/", "Nutrition and Diet Expert System", "Adults 20+"),
                                ("/km/", "ប្រព័ន្ធជំនួយអាហារូបត្ថម្ភ", "អាយុ ២០ ឆ្នាំឡើង")):
            with self.subTest(path=path):
                html = self.get(path).get_data(as_text=True)
                schema = json.loads(re.search(
                    r'<script type="application/ld\+json">(.*?)</script>', html
                ).group(1))
                self.assertEqual(schema["name"], name)
                self.assertIn(name, html)
                self.assertIn(age, html)
                self.assertNotIn("Start Free", html)
                self.assertNotIn("All rights reserved", html)
                self.assertNotIn("See your health trend over time", html)

    def test_home_source_and_heading_structure(self):
        for path in ("/", "/km/"):
            with self.subTest(path=path):
                html = self.get(path).get_data(as_text=True)
                self.assertIn('href="https://www.cdc.gov/bmi/adult-calculator/bmi-categories.html"', html)
                self.assertEqual(len(re.findall(r"<h1(?:\s|>)", html)), 1)
                self.assertEqual(len(re.findall(r'<article class="step">\s*<span[^>]*>\d</span>\s*<h3>', html)), 4)
                self.assertNotIn('<h5>', html)

    def test_adult_page_navigation_uses_page_language(self):
        english = self.get("/bmi").get_data(as_text=True)
        khmer = self.get("/km/bmi").get_data(as_text=True)
        self.assertIn('<i class="fas fa-sign-in-alt me-1"></i>Sign In', english)
        self.assertIn('<i class="fas fa-user-plus me-1"></i>Register', english)
        self.assertIn('<i class="fas fa-sign-in-alt me-1"></i>ចូលប្រើ', khmer)
        self.assertIn('<i class="fas fa-user-plus me-1"></i>ចុះឈ្មោះ', khmer)

    def test_sitemap_robots_and_nonproduction(self):
        sitemap = self.get("/sitemap.xml")
        self.assertEqual(sitemap.status_code, 200)
        self.assertTrue(sitemap.content_type.startswith("application/xml"))
        body = sitemap.get_data(as_text=True)
        root = ElementTree.fromstring(body)
        locs = [loc.text for loc in root.iter("{http://www.sitemaps.org/schemas/sitemap/0.9}loc")]
        self.assertEqual(locs, [PRODUCTION + path for path in ("/", "/km/", "/bmi", "/km/bmi")])
        for path in ("/", "/km/", "/bmi", "/km/bmi"):
            self.assertIn(f"<loc>{PRODUCTION}{path}</loc>", body)
        for path in ("/match", "/rules", "/qa", "/bmi/child-teen"):
            self.assertNotIn(f"<loc>{PRODUCTION}{path}</loc>", body)
        self.assertIn("Sitemap: " + PRODUCTION + "/sitemap.xml",
                      self.get("/robots.txt").get_data(as_text=True))
        local = self.get("/", "http://localhost:5000")
        self.assertEqual(local.headers["X-Robots-Tag"], "noindex")
        self.assertIn(f'<link rel="canonical" href="{PRODUCTION}/"',
                      local.get_data(as_text=True))
        self.assertIn("Allow: /", self.get("/robots.txt", "http://localhost:5000").get_data(as_text=True))
        self.assertEqual(self.get("/sitemap.xml", "http://localhost:5000").status_code, 404)

    def test_url_language_is_independent_of_session_and_proxy(self):
        with self.client.session_transaction() as session:
            session["ui_lang"] = "km"
        english = self.get("/").get_data(as_text=True)
        self.assertIn('<html lang="en">', english)
        self.assertIn("Build smarter diet decisions", english)
        with self.client.session_transaction() as session:
            session["ui_lang"] = "en"
        khmer = self.get("/km/").get_data(as_text=True)
        self.assertIn('<html lang="km">', khmer)
        self.assertNotIn("Build smarter diet decisions", khmer)

        host = "nutritiondietexpertsystem-production.up.railway.app"
        proxied = self.client.get("/", base_url="http://internal:8000",
                                  headers={"X-Forwarded-Host": host,
                                           "X-Forwarded-Proto": "https"})
        self.assertEqual(proxied.status_code, 200)
        self.assertNotIn("noindex", proxied.headers.get("X-Robots-Tag", ""))
        staged = self.client.get("/", base_url="http://internal:8000",
                                 headers={"X-Forwarded-Host": "staging.example",
                                          "X-Forwarded-Proto": "https"})
        self.assertEqual(staged.headers["X-Robots-Tag"], "noindex")
        staging_app = create_app(StagingTestConfig)
        staging_response = staging_app.test_client().get("/", base_url=PRODUCTION)
        self.assertEqual(staging_response.headers["X-Robots-Tag"], "noindex")

    def test_child_private_error_and_redirect_responses(self):
        for path in ("/bmi/child-teen", "/km/bmi/child-teen", "/auth/login", "/qa"):
            with self.subTest(path=path):
                self.assertEqual(self.get(path).headers["X-Robots-Tag"], "noindex")
        for path in ("/auth/login", "/auth/register"):
            html = self.get(path).get_data(as_text=True)
            self.assertIn("woman-600.webp", html)
            self.assertNotIn("a_dish_of_food.png", html)
        child = self.get("/bmi/child-teen")
        self.assertIn("no-store", child.headers["Cache-Control"])
        self.assertNotIn("bmi_results", child.get_data(as_text=True))
        token = re.search(r'name="csrf_token" value="([^"]+)"', child.get_data(as_text=True)).group(1)
        response = self.client.post("/bmi/child-teen", base_url=PRODUCTION,
                                    headers={"Referer": PRODUCTION + "/bmi/child-teen"}, data={
            "csrf_token": token, "age_years": "9", "age_months": "6", "sex": "female",
            "height_cm": "100", "weight_kg": "21.2",
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn("92.2%", response.get_data(as_text=True))
        self.assertEqual(response.headers["X-Robots-Tag"], "noindex")
        self.assertIn("no-store", response.headers["Cache-Control"])
        invalid = self.client.post("/bmi/child-teen", base_url=PRODUCTION,
                                   headers={"Referer": PRODUCTION + "/bmi/child-teen"}, data={
            "csrf_token": token, "age_years": "1", "age_months": "11", "sex": "female",
            "height_cm": "100", "weight_kg": "21.2",
        })
        self.assertEqual(invalid.status_code, 400)
        age_20 = self.client.post("/bmi/child-teen", base_url=PRODUCTION,
                                  headers={"Referer": PRODUCTION + "/bmi/child-teen"}, data={
            "csrf_token": token, "age_years": "20", "age_months": "0", "sex": "female",
            "height_cm": "100", "weight_kg": "21.2",
        })
        self.assertEqual(age_20.status_code, 303)
        self.assertTrue(age_20.headers["Location"].endswith("/bmi"))
        self.assertEqual(self.get("/missing").status_code, 404)
        self.assertEqual(self.get("/km").status_code, 308)
        for old, new in (("/bmi/", "/bmi"), ("/km/bmi/", "/km/bmi")):
            response = self.get(old)
            self.assertEqual(response.status_code, 308)
            self.assertTrue(response.headers["Location"].endswith(new))
        typo = self.get("/auth/loginn")
        self.assertEqual(typo.status_code, 301)
        self.assertTrue(typo.headers["Location"].endswith("/auth/login"))
        for private_path in ("/admin", "/dashboard/admin", "/dashboard/user", "/dashboard/doctor"):
            private = self.get(private_path)
            self.assertEqual(private.status_code, 302, private_path)
            self.assertIn("/auth/login", private.headers["Location"])
            self.assertEqual(private.headers["X-Robots-Tag"], "noindex")


class BmiReferenceTests(unittest.TestCase):
    def test_published_cdc_examples(self):
        girl = child_bmi_result(9, 6, "female", 100, 21.2)
        boy = child_bmi_result(4, 2, "male", 100, 22.6)
        self.assertAlmostEqual(girl["percentile"], 92.2, delta=0.1)
        self.assertAlmostEqual(boy["percentile"], 99.7683, delta=0.01)

    def test_reference_boundaries_and_age_limits(self):
        rows = _reference_rows()
        for sex, age in (("male", 24), ("female", 239)):
            row = rows[(1 if sex == "male" else 2, age)]
            years, months = divmod(age, 12)
            for threshold, below, at in (("P5", "underweight", "healthy_weight"),
                                         ("P85", "healthy_weight", "overweight"),
                                         ("P95", "overweight", "obesity")):
                with self.subTest(sex=sex, age=age, threshold=threshold):
                    self.assertEqual(child_bmi_result(years, months, sex, 100,
                                     row[threshold] - 0.001)["category"], below)
                    self.assertEqual(child_bmi_result(years, months, sex, 100,
                                     row[threshold])["category"], at)
        for age in ((1, 11), (20, 0)):
            with self.assertRaises(ValueError):
                child_bmi_result(*age, "male", 100, 20)
        with self.assertRaises(ValueError):
            child_bmi_result(9, 6, "male", 0, 20)
        self.assertEqual(get_bmi_category(18.5), "Healthy weight")
        self.assertEqual(get_bmi_category(25), "Overweight")
        self.assertEqual(get_bmi_category(30), "Obesity")


class DatabaseBackedRouteTests(unittest.TestCase):
    def test_public_database_routes_with_available_schema(self):
        app = create_app(PublicTestConfig)
        with app.app_context():
            db.create_all()
        client = app.test_client()
        for path, expected in (("/match", 200), ("/rules", 200), ("/foods/999999", 404)):
            response = client.get(path, base_url=PRODUCTION)
            self.assertEqual(response.status_code, expected, path)
            self.assertEqual(response.headers["X-Robots-Tag"], "noindex")
        with app.app_context():
            db.session.remove()
            db.engine.dispose()

    def test_anonymous_and_authenticated_rule_views(self):
        from app.models.diet_rule import DietRulesTable
        from app.models.permission import PermissionTable
        from app.models.role import RoleTable
        from app.models.user import UserTable

        app = create_app(PublicTestConfig)
        with app.app_context():
            db.create_all()
            role = RoleTable(name="doctor", permissions=[
                PermissionTable(code="rule.create", name="Create diet rules")
            ])
            user = UserTable(username="seo_probe", email="seo@example.invalid",
                             full_name="SEO Probe", roles=[role])
            rule = DietRulesTable(rule_name="Test rule", is_active=False)
            db.session.add_all([user, rule])
            db.session.commit()
            user_id, rule_id = user.id, rule.id
        client = app.test_client()
        for path in ("/match", "/rules", f"/foods/{rule_id}"):
            self.assertEqual(client.get(path).status_code, 200, path)
        self.assertIn('data-status="inactive"', client.get("/rules").get_data(as_text=True))
        with client.session_transaction() as session:
            session["_user_id"] = str(user_id)
            session["_fresh"] = True
        for path in ("/match", "/rules", f"/foods/{rule_id}"):
            self.assertEqual(client.get(path).status_code, 200, path)
        self.assertIn("Create Rule", client.get("/rules").get_data(as_text=True))
        with app.app_context():
            db.session.remove()
            db.engine.dispose()

    def test_rule_creation_requires_permission_and_honors_inactive_choice(self):
        from app.models.diet_rule import DietRulesTable
        from app.models.permission import PermissionTable
        from app.models.role import RoleTable
        from app.models.user import UserTable

        app = create_app(PublicTestConfig)
        with app.app_context():
            db.create_all()
            allowed_role = RoleTable(name="doctor", permissions=[
                PermissionTable(code="rule.create", name="Create diet rules")
            ])
            basic_role = RoleTable(name="user")
            allowed = UserTable(username="rule_editor", email="rule_editor@example.invalid",
                                full_name="Rule Editor", roles=[allowed_role])
            basic = UserTable(username="basic_user", email="basic_user@example.invalid",
                              full_name="Basic User", roles=[basic_role])
            db.session.add_all([allowed, basic])
            db.session.commit()
            allowed_id, basic_id = allowed.id, basic.id
        client = app.test_client()
        self.assertEqual(client.get("/rules/create").status_code, 302)
        self.assertNotIn("Create Rule", client.get("/rules").get_data(as_text=True))
        with client.session_transaction() as session:
            session["_user_id"] = str(basic_id)
            session["_fresh"] = True
        denied = client.get("/rules/create")
        self.assertEqual(denied.status_code, 302)
        self.assertNotIn("Create Rule", client.get("/rules").get_data(as_text=True))
        with client.session_transaction() as session:
            session["_user_id"] = str(allowed_id)
        form = client.get("/rules/create")
        self.assertEqual(form.status_code, 200)
        token = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', form.get_data(as_text=True)).group(1)
        created = client.post("/rules/create",
                              headers={"Referer": "http://localhost/rules/create"},
                              data={"csrf_token": token, "rule_name": "Inactive test rule",
                                    "description": "Test-only rule", "conditions": "", "goals": []})
        self.assertEqual(created.status_code, 302)
        with app.app_context():
            rule = DietRulesTable.query.filter_by(rule_name="Inactive test rule").one()
            self.assertFalse(rule.is_active)
            db.session.remove()
            db.engine.dispose()

    def test_profile_uploads_are_not_public_assets(self):
        from app.models.permission import PermissionTable
        from app.models.role import RoleTable
        from app.models.user import UserTable
        from app.services.profile_images import profile_upload_directory, save_profile_image
        from werkzeug.datastructures import FileStorage

        app = create_app(PublicTestConfig)
        with TemporaryDirectory() as temp:
            app.config["PROFILE_UPLOAD_DIR"] = temp
            with app.app_context():
                db.create_all()
                role = RoleTable(name="user", permissions=[
                    PermissionTable(code="user.dashboard.update", name="Update user dashboard"),
                    PermissionTable(code="user.dashboard.read", name="Read user dashboard"),
                ])
                first = UserTable(username="image_first", email="first@example.invalid",
                                  full_name="First User", roles=[role])
                second = UserTable(username="image_second", email="second@example.invalid",
                                   full_name="Second User", roles=[role])
                db.session.add_all([first, second])
                db.session.commit()
                first_id, second_id = first.id, second.id
                sample = b"private-image-test-bytes"
                second.photo = save_profile_image(
                    FileStorage(stream=BytesIO(sample), filename="test.jpg"), second_id)
                db.session.commit()
                second_name = Path(second.photo).name
                self.assertEqual((profile_upload_directory() / second_name).read_bytes(), sample)
                self.assertFalse((Path(app.static_folder) / "images" / "profiles" / second_name).exists())

            client = app.test_client()
            private_path = f"/images/profiles/{second_name}"
            public_path = f"/static/images/profiles/{second_name}"
            for path in (private_path, public_path):
                anonymous = client.get(path)
                self.assertEqual(anonymous.status_code, 404)
                self.assertEqual(anonymous.headers["X-Robots-Tag"], "noindex")
                self.assertIn("no-store", anonymous.headers["Cache-Control"])
            with client.session_transaction() as session:
                session["_user_id"] = str(first_id)
                session["_fresh"] = True
            for path in (private_path, public_path):
                self.assertEqual(client.get(path).status_code, 404, path)
            self.assertEqual(client.get(f"/images/profiles/nested/{second_name}").status_code, 404)
            with client.session_transaction() as session:
                session["_user_id"] = str(second_id)
            own = client.get(private_path)
            self.assertEqual(own.status_code, 200)
            self.assertEqual(own.data, sample)
            self.assertEqual(own.headers["X-Robots-Tag"], "noindex")
            self.assertIn("no-store", own.headers["Cache-Control"])
            own.close()
            self.assertEqual(client.get(public_path).status_code, 404)

            # The actual profile edit form must write to private storage and
            # keep the legacy database path readable by its owner.
            with client.session_transaction() as session:
                session["_user_id"] = str(first_id)
            edit = client.get("/dashboard/user/profile/edit")
            self.assertEqual(edit.status_code, 200)
            token = re.search(r'name="csrf_token"[^>]*value="([^"]+)"',
                              edit.get_data(as_text=True)).group(1)
            uploaded = client.post("/dashboard/user/profile/edit", data={
                "csrf_token": token, "username": "image_first",
                "full_name": "First User", "photo": (BytesIO(sample), "new.jpg"),
            }, content_type="multipart/form-data")
            self.assertEqual(uploaded.status_code, 302)
            with app.app_context():
                first_photo = db.session.get(UserTable, first_id).photo
                self.assertTrue(first_photo.startswith("images/profiles/"))
                first_name = Path(first_photo).name
                self.assertEqual((profile_upload_directory() / first_name).read_bytes(), sample)
            own_upload = client.get(f"/images/profiles/{first_name}")
            self.assertEqual(own_upload.status_code, 200)
            own_upload.close()
            profile_page = client.get("/dashboard/user/profile")
            self.assertEqual(profile_page.status_code, 200)
            self.assertIn(f"/images/profiles/{first_name}", profile_page.get_data(as_text=True))
            self.assertEqual(client.get(f"/static/images/profiles/{first_name}").status_code, 404)
            with client.session_transaction() as session:
                session["_user_id"] = str(second_id)
            self.assertEqual(client.get(f"/images/profiles/{first_name}").status_code, 404)
            static_probe = Path(app.static_folder) / "images" / "profiles" / first_name
            static_probe.parent.mkdir(parents=True, exist_ok=True)
            static_probe.write_bytes(sample)
            try:
                self.assertEqual(client.get(f"/static/images/profiles/{first_name}").status_code, 404)
            finally:
                static_probe.unlink()
            with app.app_context():
                configured = app.config["PROFILE_UPLOAD_DIR"]
                app.config["PROFILE_UPLOAD_DIR"] = str(Path(app.static_folder) / "unsafe")
                try:
                    with self.assertRaises(RuntimeError):
                        profile_upload_directory()
                finally:
                    app.config["PROFILE_UPLOAD_DIR"] = configured
            logo = client.get("/static/images/logo.png")
            self.assertEqual(logo.status_code, 200)
            logo.close()
            with app.app_context():
                db.session.remove()
                db.engine.dispose()

    def test_match_and_qa_forms_are_submittable_and_honest(self):
        from app.models.goal import GoalsTable
        from app.models.diet_rule import DietRulesTable

        app = create_app(PublicTestConfig)
        with app.app_context():
            db.create_all()
            goal = GoalsTable(name="Example goal")
            rule = DietRulesTable(rule_name="Example rule", description="Test-only rule", goals=[goal])
            inactive = DietRulesTable(rule_name="Inactive example", is_active=False,
                                      description="Test-only inactive rule", goals=[goal])
            db.session.add_all([rule, inactive])
            db.session.commit()
            goal_id = goal.id
        client = app.test_client()

        match_page = client.get("/match")
        match_html = match_page.get_data(as_text=True)
        self.assertIn("<title>Diet Rule Matcher", match_html)
        self.assertIn("Rules are matched by the selected goal, not BMI", match_html)
        self.assertNotIn("Save Plan", match_html)
        self.assertNotIn("High Match", match_html)
        match_token = re.search(r'name="csrf_token" value="([^"]+)"', match_html).group(1)
        matched = client.post("/match", data={"goal": goal_id, "bmi": "24.5",
                                               "csrf_token": match_token})
        self.assertEqual(matched.status_code, 200)
        self.assertIn("Example rule", matched.get_data(as_text=True))
        self.assertNotIn("Inactive example", matched.get_data(as_text=True))
        self.assertIn("does not change the matching rules", matched.get_data(as_text=True))
        self.assertEqual(matched.headers["X-Robots-Tag"], "noindex")
        self.assertIn("no-store", matched.headers["Cache-Control"])
        for invalid in ("nan", "infinity", "9.9", "50.1", "not-a-number"):
            rejected = client.post("/match", data={"goal": goal_id, "bmi": invalid,
                                                    "csrf_token": match_token})
            self.assertEqual(rejected.status_code, 400, invalid)

        qa_page = client.get("/qa")
        qa_html = qa_page.get_data(as_text=True)
        self.assertIn("<title>Health Question Demo", qa_html)
        self.assertNotIn("Frequently Asked Questions", qa_html)
        self.assertIn("does not provide a health answer", qa_html)
        qa_token = re.search(r'name="csrf_token" value="([^"]+)"', qa_html).group(1)
        submitted = client.post("/qa", data={"question": "Private test question",
                                              "csrf_token": qa_token})
        self.assertEqual(submitted.status_code, 200)
        self.assertIn("This demo received your question", submitted.get_data(as_text=True))
        self.assertEqual(submitted.headers["X-Robots-Tag"], "noindex")
        self.assertIn("no-store", submitted.headers["Cache-Control"])
        blank = client.post("/qa", data={"question": " ", "csrf_token": qa_token})
        self.assertEqual(blank.status_code, 400)
        with app.app_context():
            db.session.remove()
            db.engine.dispose()

    def test_login_redirects_to_private_dashboard_and_errors_are_noindex(self):
        from app.models.user import UserTable
        from app.models.role import RoleTable
        from app.models.permission import PermissionTable

        app = create_app(PublicTestConfig)
        with app.app_context():
            db.create_all()
            user = UserTable(username="login_probe", email="login_probe@example.invalid",
                             full_name="Login Probe", is_email_verified=True,
                             roles=[RoleTable(name="user", permissions=[
                                 PermissionTable(code="user.dashboard.read", name="Read user dashboard")
                             ])])
            user.set_password("local-test-password")
            db.session.add(user)
            db.session.commit()
        client = app.test_client()
        private = client.get("/dashboard/user")
        self.assertEqual(private.status_code, 302)
        self.assertIn("/auth/login", private.headers["Location"])
        self.assertEqual(private.headers["X-Robots-Tag"], "noindex")
        login_html = client.get("/auth/login").get_data(as_text=True)
        token = re.search(r'name="csrf_token" value="([^"]+)"', login_html).group(1)
        logged_in = client.post("/auth/login", data={"username": "login_probe",
                                                    "password": "local-test-password",
                                                    "csrf_token": token})
        self.assertEqual(logged_in.status_code, 302)
        self.assertIn("/dashboard/user", logged_in.headers["Location"])
        dashboard = client.get("/dashboard/user")
        self.assertEqual(dashboard.status_code, 200)
        self.assertEqual(dashboard.headers["X-Robots-Tag"], "noindex")
        missing = client.get("/missing-aeo-audit-page")
        self.assertEqual(missing.status_code, 404)
        self.assertEqual(missing.headers["X-Robots-Tag"], "noindex")
        with app.app_context():
            db.session.remove()
            db.engine.dispose()

        error_app = create_app(PublicTestConfig)
        error_app.config["PROPAGATE_EXCEPTIONS"] = False

        @error_app.route("/test-only-500")
        def test_only_500():
            raise RuntimeError("test-only failure")

        error_app.logger.disabled = True
        failed = error_app.test_client().get("/test-only-500")
        self.assertEqual(failed.status_code, 500)
        self.assertEqual(failed.headers["X-Robots-Tag"], "noindex")


class DisabledChildTests(unittest.TestCase):
    def test_child_routes_and_links_are_hidden_without_review(self):
        app = create_app(DisabledChildTestConfig)
        client = app.test_client()
        for path in ("/bmi/child-teen", "/km/bmi/child-teen"):
            for method in ("get", "post"):
                response = getattr(client, method)(path, base_url=PRODUCTION)
                self.assertEqual(response.status_code, 404, (method, path))
                self.assertEqual(response.headers["X-Robots-Tag"], "noindex")
                self.assertNotIn('rel="canonical"', response.get_data(as_text=True))
        for path in ("/", "/km/", "/bmi", "/km/bmi"):
            html = client.get(path, base_url=PRODUCTION).get_data(as_text=True)
            self.assertNotIn("/bmi/child-teen", html)
        self.assertNotIn("child-teen", client.get("/sitemap.xml", base_url=PRODUCTION).get_data(as_text=True))

    def test_visible_public_links_resolve_with_child_disabled(self):
        app = create_app(DisabledChildTestConfig)
        with app.app_context():
            db.create_all()
        client = app.test_client()
        links = set()
        for page in ("/", "/km/", "/bmi", "/km/bmi"):
            html = client.get(page, base_url=PRODUCTION).get_data(as_text=True)
            links.update(re.findall(r'<a[^>]+href="(/[^"#?]*)"', html))
        self.assertEqual(links, {"/", "/km/", "/bmi", "/km/bmi", "/auth/login", "/auth/register"})
        for path in links:
            self.assertEqual(client.get(path, base_url=PRODUCTION).status_code, 200, path)
        with app.app_context():
            db.session.remove()
            db.engine.dispose()


class DatabaseConfigTests(unittest.TestCase):
    def test_provider_postgres_url_selects_installed_driver(self):
        for scheme in ("postgres", "postgresql"):
            self.assertEqual(
                normalize_database_url(f"{scheme}://user:password@example.test:6543/db"),
                "postgresql+psycopg://user:password@example.test:6543/db",
            )


if __name__ == "__main__":
    unittest.main()
