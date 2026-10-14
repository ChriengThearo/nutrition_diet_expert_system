"""Small, explicit index policy for the public Flask pages."""

import posixpath
from urllib.parse import urlsplit

from flask import current_app, request


PUBLIC_PAGES = {
    "main.home": ("/", "home"),
    "main.home_km": ("/km/", "home"),
    "main.bmi": ("/bmi", "bmi"),
    "main.bmi_km": ("/km/bmi", "bmi"),
}
CHILD_PAGES = {
    "main.child_bmi": ("/bmi/child-teen", "child_bmi"),
    "main.child_bmi_km": ("/km/bmi/child-teen", "child_bmi"),
}


def is_profile_upload():
    if request.endpoint not in {"static", "main.images"}:
        return False
    filename = (request.view_args or {}).get("filename", "").replace("\\", "/")
    filename = posixpath.normpath("/" + filename).lstrip("/")
    prefix = "images/profiles/" if request.endpoint == "static" else "profiles/"
    return filename.startswith(prefix)


def production_url(path):
    return current_app.config["PUBLIC_SITE_URL"].rstrip("/") + path


def production_host():
    return urlsplit(current_app.config["PUBLIC_SITE_URL"]).netloc.lower()


def is_production_request():
    environment = current_app.config.get("DEPLOYMENT_ENVIRONMENT")
    return (environment in (None, "production")
            and request.host.lower() == production_host()
            and request.scheme == "https")


def page_seo():
    if request.endpoint in CHILD_PAGES and not current_app.config.get("CHILD_BMI_ENABLED", False):
        return {"canonical_url": None, "alternate_urls": None}
    entry = PUBLIC_PAGES.get(request.endpoint) or CHILD_PAGES.get(request.endpoint)
    if not entry:
        return {"canonical_url": None, "alternate_urls": None}
    path, family = entry
    pairs = {name: production_url(candidate_path) for name, (candidate_path, kind) in
             {**PUBLIC_PAGES, **CHILD_PAGES}.items() if kind == family}
    english = next(url for name, url in pairs.items() if not name.endswith("_km"))
    khmer = next(url for name, url in pairs.items() if name.endswith("_km"))
    return {
        "canonical_url": production_url(path),
        "alternate_urls": {"en": english, "km": khmer, "x-default": english},
    }


def apply_index_policy(response):
    if request.endpoint in {"static", "main.images"}:
        if is_profile_upload():
            response.headers["X-Robots-Tag"] = "noindex"
            response.headers["Cache-Control"] = "private, no-store"
            response.headers["X-Content-Type-Options"] = "nosniff"
        elif request.endpoint == "main.images":
            response.headers["X-Robots-Tag"] = "noindex"
        return response
    if request.endpoint in {"main.robots_txt", "main.sitemap_xml"}:
        return response
    public = request.endpoint in PUBLIC_PAGES
    if not (public and request.method == "GET" and response.status_code == 200
            and is_production_request()):
        response.headers["X-Robots-Tag"] = "noindex"
    if request.endpoint in CHILD_PAGES:
        response.headers["Cache-Control"] = "no-store"
    if request.endpoint in {"main.qa", "main.match"} and request.method == "POST":
        response.headers["Cache-Control"] = "no-store"
    return response
