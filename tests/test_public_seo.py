"""Rendered public SEO behavior and CDC BMI calculation boundaries."""

import re
import json
import unittest
from html import unescape
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
        from app.models.role import RoleTable
        from app.models.user import UserTable

        app = create_app(PublicTestConfig)
        with app.app_context():
            db.create_all()
            role = RoleTable(name="doctor")
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
