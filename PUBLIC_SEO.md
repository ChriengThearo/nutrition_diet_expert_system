# Public search pages

`app/seo.py` is the index policy. On the configured production HTTPS host and
Railway `production` environment, only
`/`, `/km/`, `/bmi`, and `/km/bmi` are indexable. These four URLs appear in
`/sitemap.xml`. Every other content route returns an `X-Robots-Tag: noindex` header;
the child BMI pages also include a robots meta tag and disable response caching.
Nonproduction responses are noindex. Keep `robots.txt` crawlable so crawlers can
read those directives. Authentication remains the access control for private
routes.

The child and teen calculator is **disabled by default** (`CHILD_BMI_ENABLED=0`).
Disabled GET and POST routes return 404, and the public pages do not link to
them. Enable it only after qualified calculation and Khmer-language review.
Its implementation uses the CDC 2022 extended BMI-for-age data in
`app/data/cdc_bmi_age_2022.csv` for ages 24 through 239 completed months. The
source is <https://www.cdc.gov/growthcharts/extended-bmi-data-files.htm> and the
downloaded CSV SHA-256 is
`7f416a213157a5209bb6cbfd1b19292510248f3f31fe43c9ff63f6d8e39f7890`.
When enabled, keep `/bmi/child-teen` and `/km/bmi/child-teen` noindex and out of
the sitemap until a qualified reviewer checks the calculation and Khmer medical
wording. The tests verify example values and boundaries; they do not constitute
clinical review.

The intended Supabase project reference matches the local API URL and the
project-qualified database user. A later read-only probe successfully ran
`SELECT 1` against the configured pooler on both port 6543 (transaction) and
port 5432 (session); the earlier `tenant/user not found` error is no longer
reproducible. The local private `.env` now uses port 5432, appropriate for this
persistent Flask worker on Railway's default IPv4 outbound network. Do not
derive a production hostname from the project region: copy the exact session
pooler host, port, database name, and project-qualified user from the intended
project's Supabase **Connect** dialog. Update the private Railway `DATABASE_URL`
only as part of an authorized release. Do not place credentials in a report.
The local session connection has the expected public tables, actual records,
and Alembic revision `f1a3b6c8d9e2`, matching the repository head. No
production migration is indicated by this read-only check. Confirm the Railway
configuration and logs before attributing any remaining live error to the
database.

Dependency installation: Python 3.11.15 from `.python-version`, with
`pyproject.toml` and `uv.lock` as the single source of truth. Use
`uv sync --frozen` locally. Railway Railpack should select uv from these files;
confirm this in the build log when deployed. `requirements.txt` was removed to
avoid competing installers. The existing Railway start command remains
`gunicorn --workers 1 --threads 4 --timeout 600 --bind 0.0.0.0:$PORT run:app`.
Application startup no longer creates tables or migrates permission codes.
`uv sync --frozen --dry-run --python-platform x86_64-unknown-linux-gnu --python
3.11.15` resolves the Linux lockfile, but is not an installed Linux runtime or
a Gunicorn smoke test. Those remain deployment gates.

After deployment, rerun mobile and desktop PageSpeed against the deployed URL.
Those lab results should be reported separately from field Core Web Vitals.
After the owner verifies the exact Search Console property, record the first
complete 28-day period for clicks, impressions, CTR, average position, landing
pages, indexing, and sitemap status. Compare it with an equivalent later period.
Sitemap submission and Search Console setting changes require separate
authorization.
