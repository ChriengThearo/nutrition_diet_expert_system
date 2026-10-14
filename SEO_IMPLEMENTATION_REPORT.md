# Flask SEO and public content verification report

**Date:** 2026-10-13  
**Project:** Nutrition and Diet Expert System  
**Release state:** Changes are in the local worktree. No deployment, Railway setting change, Search Console submission, or production migration was made in this task.

## Decision

The local implementation is ready for release review, but **technical SEO acceptance is not complete**. The deployed Railway site still serves the older build: `/km/`, `/km/bmi`, `/robots.txt`, and `/sitemap.xml` return 404; `/rules` returns 500. The exact Search Console property is unverified. Linux installation, Gunicorn startup, and Railway build/runtime logs could not be checked from this Windows workspace. No claim of indexing, traffic improvement, or a “10/10” technical score is supported.

## Changes and confirmed causes

- The intended Supabase project reference supplied by the owner matches the local Supabase API URL and the project-qualified database username. A previous transaction-pooler `tenant/user not found` response did not recur. Read-only `SELECT 1` succeeded on the configured host using both port 6543 and port 5432. The local private `.env` was switched to **session pooling on port 5432**; `config.py` uses the installed `psycopg` driver and leaves prepared statements at the driver default in session mode. This follows [Supabase's guidance for a persistent backend on an IPv4-only network](https://supabase.com/docs/guides/database/connecting-to-postgres). [Railway documents outbound IPv6 as disabled by default](https://docs.railway.com/networking/outbound-networking). The exact Railway `DATABASE_URL` and the project's Connect dialog were inaccessible, so their match remains unverified. Credentials were not printed or added to tracked files.
- The connected database has 26 public tables, including users, foods, diet rules, and Alembic metadata. It contains 46 users, 85 foods, 720 diet rules, and 35,716 food-group rows. Its `alembic_version` is `f1a3b6c8d9e2`, the repository migration head (`flask db heads`). No schema write or migration was performed.
- The deployed `/rules` 500 has a repository-side cause: the committed template calls `current_user.has_role(...)` for an anonymous visitor, although Flask-Login's anonymous user has no such method. Rendering that committed template in an anonymous request reproduces `UndefinedError` mentioning `has_role`. The local template guards this call with `current_user.is_authenticated`; its `/rules` response is 200 against the intended database. This fix is **not yet deployed**. The rule status label also used nonexistent `rule.active`; it now uses `rule.is_active` for the filter data and visible badge.
- The Khmer BMI mobile shift came from three overlapping Google Fonts requests, one still using `display=swap` through `style.css`. The public base, `dashboard_theme.css`, and `style.css` now use `display=optional`. Under matched local cold mobile conditions, three `/km/bmi` runs changed from layout-shift score **0.074** to **0.000**; median LCP changed from 1.644 s to 1.684 s. This is browser lab evidence, not field Core Web Vitals.
- The earlier worktree changes remain: fixed English/Khmer URLs, canonical and language alternatives, crawl directives, four-URL sitemap, actual 404 page, adult BMI age guard, disabled-by-default child tools, and responsive WebP assets. `PUBLIC_SEO.md` now reflects the confirmed session connection and release gates.

## Database and route verification

| Check | Local result | Deployed result (2026-10-13) |
| --- | --- | --- |
| Supabase connection | `SELECT 1` passed via `postgresql+psycopg` session pooler, port 5432 | Railway URL/logs not accessible |
| Schema and migration | Expected tables and records present; DB revision equals repository head | Not independently visible in Railway |
| `/match` | 200 | 200 |
| `/rules` | 200, 3,349,479 response bytes | 500 |
| `/foods/21` (existing rule) | 200 | 200 |
| `/foods/999999` (missing rule) | 404 | 404 |
| Authenticated views | Synthetic doctor account in local SQLite: `/match`, `/rules`, and existing food page return 200; doctor sees Create Rule | Not tested with a production account |

The local `/rules` response is large because it renders all 720 rules. That is a performance concern for this **noindex** page, but it did not cause the observed local error. A later pagination change should preserve search/filter behavior; it is separate from the current release gate.

## Installation and startup

- `.python-version` requests Python 3.11.15; `pyproject.toml` and `uv.lock` pin Flask 2.3.3, Gunicorn 26.2.0, and the rest of the dependency set. `railway.json` selects Railpack and starts `gunicorn --workers 1 --threads 4 --timeout 600 --bind 0.0.0.0:$PORT run:app`.
- `uv sync --frozen --dry-run --python-platform x86_64-unknown-linux-gnu --python 3.11.15` resolved the Linux lockfile and proposed 99 packages, including large CUDA packages. It did **not** install or run them. A prior clean Windows Python 3.11.15 `uv sync --frozen` succeeded; current Windows tests used the existing environment and are not Linux proof.
- Docker, Podman, and an installed WSL distribution were unavailable. There was no Railway CLI/session or accessible browser dashboard. Therefore the production installer choice, build logs, runtime logs, Gunicorn boot, actual Python version, and resource limits are **not verified**. Review these before release acceptance. The scanner warmup may add startup load; inspect actual logs rather than inferring success from the health page.

## SEO response checks

| URL or behavior | Local current build | Live older build |
| --- | --- | --- |
| `/` | 200; English, unique title/description, self-canonical, reciprocal `hreflang`, `WebSite` JSON-LD | 200; Khmer language marker, no canonical |
| `/km/` | 200; Khmer, corresponding metadata and language links | 404 |
| `/bmi` | 200; English adult BMI, age 20+, canonical and language links | 200; Khmer language marker, no canonical |
| `/km/bmi` | 200; Khmer adult BMI, canonical and language links | 404 |
| `/robots.txt`, `/sitemap.xml` | 200; sitemap has exactly the four public canonical URLs | Both 404 |
| Redirects, 404s, private access | 308 for `/km`, `/bmi/`, `/km/bmi/`; real 404; private dashboards redirect to login; nonproduction responses noindex | New behavior not deployed |
| Child BMI | Disabled and unlinked by default; GET and POST return noindex 404; excluded from sitemap | New behavior not deployed |

Local rendered HTML, language stability across sessions, proxy headers, production-only index policy, sitemap membership, redirects, and private access passed automated checks. Reciprocal language URLs follow [Google's multilingual URL guidance](https://developers.google.com/search/docs/specialty/international/managing-multi-regional-sites). Child percentile calculations passed CDC examples and boundary tests, but qualified calculation and Khmer-language review are still required before enabling them.

## Performance evidence

The local browser probe used headless Chrome, cache disabled, 390 × 844 mobile viewport with 150 ms latency and 200,000 bytes/s throughput, or 1365 × 768 desktop with 40 ms latency and 1,250,000 bytes/s throughput. Each final local page has two runs and four seconds of settle time. The local results are not a Lighthouse score and do not represent the 75th percentile of real users. Google defines field Core Web Vitals using [LCP, INP, and CLS at the 75th percentile](https://web.dev/articles/vitals).

| Current local page | Mobile LCP | Mobile layout shift | Desktop LCP | Desktop layout shift |
| --- | ---: | ---: | ---: | ---: |
| `/` | 2.188 s | 0.0001 | 0.842 s | 0.0014 |
| `/km/` | 2.418 s | 0.0355 | 0.852 s | 0.0365 |
| `/bmi` | 1.688 s | 0 | 0.564 s | 0.0001 |
| `/km/bmi` | 1.684 s | 0 | 0.488 s | 0.0001 |

The **old deployed** `/` and `/bmi` were also measured once each with the same browser profile but a longer settle period (45 s mobile, 25 s desktop). Mobile `/` had LCP 3.084 s, layout-shift score 0.385, and TTFB 181 ms; `/bmi` had LCP 1.388 s, shift 0.018, and TTFB 31 ms. Desktop `/` had LCP 2.576 s, shift 0.016, and TTFB 154 ms; `/bmi` had LCP 0.464 s, shift 0.005, and TTFB 42 ms. The mobile homepage LCP element was its heading; desktop LCP was `woman.png`. On the old mobile homepage, `woman.png` took 13.7 s, Bootstrap CSS 1.38 s, and Bootstrap JS 1.14 s; desktop also fetched the 7.8 MB `a_dish_of_food.png` in 8.5 s. These conditions differ from the earlier Ubersuggest 49.2 s mobile LCP report, so the figures are **not** an improvement comparison.

The local current homepage uses a 20 KB `woman-600.webp` and a 17 KB `a_dish_of_food-600.webp` in place of the 1.06 MB and 7.83 MB originals, with explicit dimensions and loading priority. Its mobile LCP is now text; Bootstrap, `dashboard_theme.css`, and Font Awesome remain prominent blocking/slow resources in the local trace. The updated four-page build needs the same mobile and desktop audit **after deployment**. The live Khmer pages cannot be measured as public pages while they return 404. Raw observations and conditions are in `reports/performance/`.

## Audience and search measurement

The bilingual URLs suggest Cambodia-focused Khmer and English users, but the owner has not yet confirmed the primary country and languages. Ubersuggest's daily report quota is **3/3 used**, so no additional country-specific volume or paid crawl was run. The earlier US-English competitor sample and global volumes cannot stand in for Cambodia/Khmer demand. This intent-based map uses only pages the site currently supports:

| Page | Search intent to target | Constraint |
| --- | --- | --- |
| `/` | English overview of nutrition tools and adult BMI calculation | Describe the real tools; no medical-validation claim |
| `/km/` | Khmer overview of nutrition tools and adult BMI calculation | Khmer copy review before expanding medical guidance |
| `/bmi` | “adult BMI calculator”, “BMI categories for adults” | Ages 20+; screening information |
| `/km/bmi` | “គណនា BMI សម្រាប់មនុស្សពេញវ័យ” and related Khmer adult-BMI intent | No unsupported search-volume claim |

Child tools, matcher, rules, account pages, and the poster remain outside the indexable keyword map. GSC Wizard lists the **exact production HTTPS URL-prefix property** as **not verified in GSC** and unreadable. The owner should open that property in Search Console, choose **HTML tag verification**, provide its exact token for the production homepage `<head>`, then verify after an authorized deployment. Google supports the [HTML tag method for URL-prefix properties](https://support.google.com/webmasters/answer/9008080?hl=en); it requires the public homepage to expose the tag. Do not use a DNS method for a `railway.app` hostname the owner does not control. No GSC inspection, crawl date, indexing, clicks, impressions, CTR, average position, or field Core Web Vitals can be reported yet. After verification and deployment, inspect all four URLs and capture a complete 28-day baseline, then compare with an equivalent later period. No sitemap was submitted.

## Acceptance table

| Requirement | Status | Evidence | Remaining action |
| --- | --- | --- | --- |
| Correct intended DB project and working local connection | PASS | Project reference match; session pooler `SELECT 1` | Confirm exact Railway Connect URI privately |
| Expected schema, migration head, actual records | PASS | 26 tables; Alembic `f1a3b6c8d9e2`; nonzero records | None; no migration indicated |
| Database routes, including existing/missing IDs | PASS locally; FAIL live | Local 200/200/200/404; live 200/500/200/404 | Release guarded `/rules` template |
| Relevant authenticated route behavior | PASS locally | Synthetic doctor test in SQLite | Production account smoke test after release |
| Linux dependency installation | NOT VERIFIED | Linux `uv sync --dry-run` resolves 99 packages | Run actual clean Linux `uv sync --frozen` |
| Gunicorn boot and Railway build/runtime logs | NOT VERIFIED | Start command in `railway.json`; no logs accessible | Inspect logs and smoke test running worker |
| Four public pages and metadata | PASS locally; FAIL live | 14 tests pass; live Khmer URLs 404 and old canonicals absent | Deploy, then fetch all four live pages |
| Robots, sitemap, redirects, 404, privacy and staging | PASS locally; FAIL live | Local route tests; live robots/sitemap 404 | Verify on deployed production/staging |
| Child tools disabled pending clinical/Khmer review | PASS locally | Default-off 404/noindex/unlinked tests | Keep disabled until qualified review |
| Khmer BMI layout stability | PASS locally | Matched cold mobile runs: 0.074 to 0.000 | Measure deployed build |
| Four-page deployed mobile/desktop performance | NOT VERIFIED | Old live has only two working pages | Rerun same audit after release |
| GSC property and current indexing evidence | FAIL / NOT VERIFIED | GSC Wizard: exact property not verified | Owner supplies verification token and verifies |
| Cambodia/Khmer keyword metrics and audience | NOT VERIFIED | Ubersuggest quota 3/3; owner audience pending | Confirm market; research when quota resets |
| Search traffic improvement | NOT VERIFIED | No readable GSC property or 28-day periods | Measure after verification and release |

## Exact release gates

1. Obtain the intended project's **session pooler** URI from Supabase Connect and confirm host, port 5432, database, and project-qualified user. Apply it to Railway's private `DATABASE_URL` only with deployment authorization. Keep the password private. The local `.env` is already in session mode.
2. Review and release this worktree. Check Railpack logs for Python 3.11.15 and installation from `uv.lock`, then Gunicorn logs for successful worker boot. Do not run `flask db upgrade` merely to clear an error; the observed database revision already matches the head.
3. Fetch the four production pages, robots, sitemap, redirects, 404, account/privacy routes, and `/match`, `/rules`, and food routes. Confirm canonical/alternate URLs, `X-Robots-Tag`, and proxy/environment detection from actual response headers and HTML.
4. Rerun mobile and desktop lab checks with recorded conditions on all four deployed pages; separately obtain field Core Web Vitals when available.
5. Add the owner-provided Search Console HTML verification tag to the public homepage in a reviewed release, have the owner verify the exact URL-prefix property, then inspect URLs. Sitemap submission and search settings are outside this task.

## Independent critical review

- Reproduced the committed anonymous `/rules` template failure directly, then verified the guarded worktree route against the intended database and a synthetic authenticated doctor. This supports the specific fix but cannot substitute for the deployed smoke test.
- Checked `git diff --check` and all 14 regression tests. The diff check found no whitespace errors; Git reported only an existing line-ending normalization warning for `pyproject.toml`.
- Inspected a 390 px Khmer BMI screenshot and checked all four pages at 320 and 390 px: Khmer text remained readable and no document exceeded its viewport width. `font-display: optional` can use the fallback font on a slow first visit; the deployed design should be reviewed on a representative device.
- The 3.35 MB all-rules HTML response and Linux dependency set with CUDA packages remain size/resource risks. Neither explains a confirmed current local failure. Do not label production startup or performance as passed until Railway logs and deployed audits are available.

## Files changed in this continuation

- `app/templates/layouts/base_enhanced.html`, `app/static/css/dashboard_theme.css`, `app/static/css/style.css`: avoid late font swapping.
- `app/templates/main/rules.html`: render the actual `is_active` state; the earlier anonymous role guard remains in this worktree.
- `tests/test_public_seo.py`: cover anonymous and synthetic authenticated rule/food views.
- `PUBLIC_SEO.md`: correct the database and Linux verification notes.
- `reports/performance/khmer-bmi-mobile-after-font.json`, `final-mobile.json`, `final-desktop.json`, `live-old-mobile.json`, `live-old-desktop.json`: reproducible browser observations.
- Private ignored `.env`: local database URL port changed from 6543 to 5432; no credential value changed.

**Review result:** `uv run --no-sync python -m unittest discover -s tests -v` passed all 14 tests. The fresh local Chrome checks found no horizontal overflow at 320 or 390 px on the four public pages. The production release and its logs remain the decisive acceptance gate.
