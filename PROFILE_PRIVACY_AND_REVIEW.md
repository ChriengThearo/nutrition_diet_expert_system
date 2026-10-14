# Profile privacy and content review preparation — 2026-10-14

## Release decision

**Safe to push to a confirmed non-deploying branch for code review only, with the owner aware that this does not remove the existing public copies. Not ready for a bilingual, indexable production release.** Do not push this branch if Railway deploys it. The code and tests below are local; the existing Railway deployment and public Git history still expose sampled profile images. The owner must decide how to respond to those existing copies and must arrange qualified Khmer and medical content review. No push, deployment, Git history rewrite, Railway setting change, or Search Console submission was made.

The earlier untracked `PRE_PUSH_AEO_SEO_AUDIT.md` was found empty during this continuation, so it now points to this report. Its prior conclusions were checked against the live code and tests rather than copied from a missing file.

## Privacy inventory and use

| Location or component | Finding and treatment |
| --- | --- |
| `app/static/images/profiles/` | Ten tracked `user_*` image files match the application upload naming pattern. They were moved locally to `instance/profile_uploads/`, preserved byte for byte, and staged for removal from Git tracking with `git rm --cached`. The public legacy folder is now empty locally and ignored. No image or personal record is reproduced here. |
| `instance/profile_uploads/` | Private, ignored on-disk storage outside Flask static. The ten migrated files remain local; new user, doctor, and admin profile edits write here. An optional `PROFILE_UPLOAD_DIR` can point to a persistent private mount, but is rejected if it resolves inside Flask static. No production mount was configured. |
| `app/static/images/brand/` and `app/static/img/default-avatar.png` | Application avatar/brand assets, retained as public tracked files. `app/services/user_service.py` uses `images/brand/avatar.png` as the default photo path. |
| `app/static/images/foods/`, `app/static/images/cooked_foods/` | 70 and 67 tracked files respectively; 62 food filenames and at least 34 cooked-food filenames match generated upload patterns. Eight food files are named stock illustrations. Doctor food and cooked-food editors save files in these folders, and seed data references many of them. They are **not** profile images. Their ownership, privacy classification, persistence, and any separate Git cleanup need an owner decision before changing them; this task did not remove those seeded assets. |
| `seeds/tbl_users.json` | Contains legacy `images/profiles/...` photo references. The new private serving route still understands those database values. The seed file and Git history need an owner privacy review; no personal records are printed in this report. |
| Image serving | Flask's implicit `/static/<path:filename>` and `main.images` at `/images/<path:filename>` were both investigated. There is no other Flask `send_from_directory` profile path. All `/static/images/profiles/*` requests now get 404, even for a signed-in owner. `/images/profiles/<name>` reads only private storage, and only when the authenticated user's exact database photo path matches that name; other users and anonymous visitors get 404. Profile responses have `X-Robots-Tag: noindex`, `Cache-Control: private, no-store`, and `X-Content-Type-Options: nosniff`. Public brand images still work. |
| Displays and writes | `dashboard_routes.py` has three profile edit flows (admin, doctor, user), now calling `save_profile_image`. Own profile, account navigation, and dashboard templates still build the existing `/images/profiles/...` URL and can display an owner's migrated or newly uploaded private file. Admin and doctor views that reference **another** user's profile URL will now receive 404; a future explicit privileged-access policy needs owner approval if those thumbnails must be visible. No broad cross-user exception was silently added. |

The local migration retained filenames so existing `UserTable.photo` values can resolve if the corresponding files are present in private storage. **Production has not been migrated.** A new deployment that removes tracked images without copying the deployed files into a persistent private store will leave existing profile photos unavailable. Railway's filesystem persistence and deployment mechanism must be checked before a production release. A filesystem mount or controlled migration must not be replaced with a public static directory.

## Existing exposure and Git history

- Read-only checks on 2026-10-14 requested only response status and headers, never image bodies. A sampled profile URL returned **200 `image/jpeg` through both** `/static/images/profiles/` and `/images/profiles/` on the current Railway host, with no `X-Robots-Tag`. The older deployed build remains exposed at the sampled paths. Other files and any caches were not exhaustively checked.
- The public GitHub repository returned `visibility: public` from its read-only repository API. `origin/main` and other remote branches contain commit `8d7e66a` (2026-09-07), which placed profile images under `app/static/images/profiles/`. Earlier history touching the predecessor `images/profiles/` path includes `78a5fb3`, `ef1face`, `055b4ee`, and `09c27f7`. Those commits are already in reachable history; staged deletion does not erase their blobs. The affected path families are `images/profiles/*` and `app/static/images/profiles/*`. Exact filenames are withheld here because they encode account IDs; the local command `git log --all -- images/profiles app/static/images/profiles` shows the commits.
- The owner must decide whether the affected images had consent for public distribution, whether the live assets must be removed urgently, whether GitHub/history/cache remediation is needed, and whether affected people must be contacted. This audit did **not** rewrite history or change live systems. Consult an appropriate privacy adviser if required for those decisions.

## Tests and browser results

- `uv run --no-sync python -m unittest discover -s tests -v`: **22 tests passed**. The profile test uses two ordinary accounts and temporary private storage. Anonymous and user A requests for user B's file returned 404 at both paths; B's private route returned 200 with the exact test bytes, while B's static path returned 404. B also could not fetch A's newly uploaded file. A real profile edit POST stored a new file outside static; A's profile page referenced its private URL and that URL returned 200. A deliberately placed file in the legacy static folder still returned 404. A configured upload folder inside static raised an error. Public logo still returned 200. No real user image bytes were used in this test.
- Chrome 155 headless on local Flask: `/`, `/km/`, `/bmi`, `/km/bmi` at 390 × 844 and 1280 × 900 had correct page language, no broken images, and no horizontal overflow. Both BMI forms gave 22.9 for the test measurements, saved locally, cleared, rejected age 19, and classified 24.98/25.0 on opposite sides of the 25 boundary. Language switch and mobile menu passed. The first run hit a timing assertion before the Bootstrap mobile menu became visible; the ignored browser check script was changed to wait for visibility, and the rerun passed. This was a test timing issue, not an application change.
- `git diff --check`, `git diff --cached --check`, and `python -m compileall -q app`: passed. The local `.venv` remains Python 3.14.4, while the project targets Python 3.11.15; this is not a Linux/Gunicorn or Railway test.
- Final diff inspection found ten staged binary removals from the profile folder and no added profile image files or credential values. Private local files are ignored. The existing `PRE_PUSH_AEO_SEO_AUDIT.md` and `CONTENT_REVIEW_FACT_SHEET.md` contain no image bodies or personal records.

## Owner and qualified-review decisions

The [owner fact sheet and exact bilingual review strings](CONTENT_REVIEW_FACT_SHEET.md) ask for the official English and Khmer project names, publisher/maintainer, content and image rights, any real author or reviewer credentials, and genuine review dates. It extracts exact home health passages and adult BMI formula, category labels, result wording, storage text, and error messages in both languages. It also identifies disabled child-tool strings for a later qualified review. **None are marked approved.**

The current policy still treats `/km/` and `/km/bmi` as indexable on the production HTTPS host. If the owner plans to deploy before qualified Khmer health-language review, the proposed temporary change is:

1. Keep both Khmer URLs available as normal 200 pages with `X-Robots-Tag: noindex`.
2. Remove `/km/` and `/km/bmi` from the sitemap, leaving `/` and `/bmi`.
3. Remove reciprocal `hreflang="km"` pairs from English and Khmer metadata while translations are unapproved. Keep English self-canonicals; omit Khmer canonicals while those pages are noindex. Keep ordinary visible language-switch links so people can still reach the Khmer pages.
4. Restore the four-URL sitemap, reciprocal hreflang, and indexable policy only after the owner records the qualified review and approves the exact wording.

**This indexing change was proposed only, not implemented.** The owner must choose whether to hold deployment for review or temporarily noindex the Khmer pages. Child BMI pages remain disabled/noindex/out of the sitemap either way.

## Changed files and remaining gates

Privacy changes: `.gitignore`, `config.py`, `app/services/profile_images.py`, `app/__init__.py`, `app/routes/main_routes.py`, `app/routes/dashboard_routes.py`, `app/seo.py`, `tests/test_public_seo.py`; ten profile binaries are staged for removal from tracking and preserved under ignored `instance/profile_uploads/`. This report and `CONTENT_REVIEW_FACT_SHEET.md` were added. Earlier SEO/AEO edits already in this worktree remain pending the user's review; they were not pushed.

Before any production release: resolve the live and history exposure with the owner, provision private persistent storage and migrate needed production files, verify role-specific photo display expectations, obtain qualified Khmer/medical review, choose the Khmer indexing policy, then perform a separately authorized deployment and live verification. A non-deploying review branch does not satisfy these gates.
