"""
sync_photos.py
==============
Scans images/foods/ and images/cooked_foods/ folders, then:
1. Ensures every file already referenced in the DB is still valid.
2. Matches UUID-named files (food_<uuid>.*) uploaded via UI to DB rows
   that currently have NULL photo — by checking created_at proximity or
   letting the operator manually confirm.
3. Matches readable-named files (e.g. apple.png → Apples) to NULL rows.
4. Updates the DB and re-dumps the seed.

Usage:
    python seeds/sync_photos.py          # dry-run (preview only)
    python seeds/sync_photos.py --apply  # apply changes to DB + re-dump seed
"""

import os
import sys
import re
import unicodedata
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import create_app
from extensions import db
from sqlalchemy import text

FOODS_DIR  = ROOT / "images" / "foods"
COOKED_DIR = ROOT / "images" / "cooked_foods"
APPLY      = "--apply" in sys.argv


# ─── helpers ────────────────────────────────────────────────────────────────

def normalize(s):
    """Lowercase, strip accents, replace non-alphanumeric with space."""
    s = unicodedata.normalize("NFKD", str(s or ""))
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()
    return s


def filename_to_words(filename):
    """Extract words from a filename (remove extension, split on _ - space)."""
    stem = Path(filename).stem
    stem = re.sub(r"^(food|cooked_food)_[0-9a-f]{32}$", "", stem, flags=re.I)
    words = set(re.split(r"[_\-\s]+", stem.lower()))
    words.discard("")
    return words


def name_score(food_name, filename):
    """Return a similarity score between a food name and a filename."""
    fn = normalize(food_name)
    fwords = set(fn.split())
    iwords = filename_to_words(filename)
    if not fwords or not iwords:
        return 0
    overlap = fwords & iwords
    return len(overlap) / max(len(fwords), len(iwords))


def find_best_match(filename, candidates):
    """Find the best matching (id, name) from candidates for a given filename."""
    scored = [(food_id, food_name, name_score(food_name, filename))
              for food_id, food_name in candidates]
    scored.sort(key=lambda x: x[2], reverse=True)
    best = scored[0] if scored else None
    if best and best[2] >= 0.5:
        return best
    return None


# ─── main ───────────────────────────────────────────────────────────────────

app = create_app()
with app.app_context():
    with db.engine.connect() as conn:
        food_rows  = conn.execute(text("SELECT id, name, photo FROM tbl_foods ORDER BY id")).fetchall()
        cooked_rows = conn.execute(text("SELECT id, name, photo FROM tbl_cooked_foods ORDER BY id")).fetchall()

    food_by_id   = {r[0]: {"name": r[1], "photo": r[2]} for r in food_rows}
    cooked_by_id = {r[0]: {"name": r[1], "photo": r[2]} for r in cooked_rows}

    # Rows already have a photo → don't touch
    food_null   = [(r[0], r[1]) for r in food_rows  if not r[2]]
    cooked_null = [(r[0], r[1]) for r in cooked_rows if not r[2]]

    print(f"Foods with NULL photo:        {len(food_null)}")
    print(f"Cooked foods with NULL photo: {len(cooked_null)}")

    # Collect files in each folder
    food_files  = sorted(FOODS_DIR.iterdir())  if FOODS_DIR.exists()  else []
    cooked_files = sorted(COOKED_DIR.iterdir()) if COOKED_DIR.exists() else []

    # Already-used paths (skip these files)
    used_food_paths   = {r[2] for r in food_rows  if r[2]}
    used_cooked_paths = {r[2] for r in cooked_rows if r[2]}

    # Only consider files NOT already assigned to any row
    free_food_files  = [f for f in food_files
                        if f.is_file() and f"images/foods/{f.name}" not in used_food_paths]
    free_cooked_files = [f for f in cooked_files
                         if f.is_file() and f"images/cooked_foods/{f.name}" not in used_cooked_paths]

    print(f"\nFree food image files:        {len(free_food_files)}")
    print(f"Free cooked image files:      {len(free_cooked_files)}")

    # ── Match free files to NULL rows ─────────────────────────────────────
    food_updates   = {}  # id → new_photo_path
    cooked_updates = {}

    print("\n── Food matches ──────────────────────────────────────────────────")
    assigned_food_files = set()
    for f in free_food_files:
        match = find_best_match(f.name, food_null)
        if match and match[0] not in food_updates:
            food_id, food_name, score = match
            path = f"images/foods/{f.name}"
            food_updates[food_id] = path
            assigned_food_files.add(f.name)
            print(f"  MATCH  id={food_id:3}  score={score:.2f}  '{food_name}'  <-  {f.name}")
        else:
            print(f"  SKIP   {f.name}  (no match or duplicate)")

    print(f"\n── Cooked food matches ───────────────────────────────────────────")
    for f in free_cooked_files:
        match = find_best_match(f.name, cooked_null)
        if match and match[0] not in cooked_updates:
            cf_id, cf_name, score = match
            path = f"images/cooked_foods/{f.name}"
            cooked_updates[cf_id] = path
            print(f"  MATCH  id={cf_id:3}  score={score:.2f}  '{cf_name}'  <-  {f.name}")
        else:
            print(f"  SKIP   {f.name}  (no match or duplicate)")

    print(f"\nFood rows to update:        {len(food_updates)}")
    print(f"Cooked food rows to update: {len(cooked_updates)}")

    if not APPLY:
        print("\n[DRY RUN] No changes made. Run with --apply to apply.")
        sys.exit(0)

    # ── Apply updates ─────────────────────────────────────────────────────
    now = datetime.utcnow()
    with db.engine.begin() as conn:
        for food_id, photo_path in food_updates.items():
            conn.execute(
                text("UPDATE tbl_foods SET photo = :photo, updated_at = :now WHERE id = :id"),
                {"photo": photo_path, "id": food_id, "now": now},
            )
        for cf_id, photo_path in cooked_updates.items():
            conn.execute(
                text("UPDATE tbl_cooked_foods SET photo = :photo, updated_at = :now WHERE id = :id"),
                {"photo": photo_path, "id": cf_id, "now": now},
            )

    total = len(food_updates) + len(cooked_updates)
    print(f"\n✓ Applied {total} DB updates.")

    # ── Re-dump seeds ──────────────────────────────────────────────────────
    print("Re-dumping seed files…")
    import importlib, json as _json
    from seeds.seed import dump_all  # noqa: E402
    dump_all()
    print("✓ Seeds re-dumped.")
