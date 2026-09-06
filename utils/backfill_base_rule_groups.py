"""Backfill missing food groups (group_2..group_4) and cooked-food entries
for the base diet rules that never received the multi-group / cooked-food
treatment applied by generate_blood_sugar_rules.py.

Background
----------
generate_blood_sugar_rules.py reads the "base" rules (no blood_sugar
condition) as templates and generates *new* derived rules per blood-sugar
band with 4 food groups each, mixing raw + cooked food recommendations.
It never touches the base rules themselves. Users who don't submit a blood
sugar value match a base rule directly, so they only ever see:
  - a single group_1
  - raw-ingredient recommendations only (cooked_food_id is NULL everywhere)

This script fixes that in place, for the base rules only:
  1. Adds cooked-food recommended/avoid entries to the existing group_1.
  2. Generates group_2, group_3, group_4 (raw + cooked) so "Change food
     groups" has something to switch to.

It reuses the pool-filtering / weighted-sampling helpers from
generate_blood_sugar_rules.py so the generated data follows the same
allergy/diet-type/vegan rules as the already-generated blood-sugar rules.

Usage:
    python utils/backfill_base_rule_groups.py --dry-run
    python utils/backfill_base_rule_groups.py --apply
"""

import argparse
import json
import random
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app import create_app  # noqa: E402
from app.models.food_group import FoodGroupTable  # noqa: E402
from app.models.rule_food_map import RuleFoodMapTable  # noqa: E402
from extensions import db  # noqa: E402

from utils.generate_blood_sugar_rules import (  # noqa: E402
    _collect_base_templates,
    _filter_pool,
    _load_cooked_foods,
    _load_raw_foods,
    _weighted_sample_items,
)

TARGET_GROUP_COUNT = 4
NORMAL_REC_WEIGHTS = (0.34, 0.33, 0.33)
NORMAL_AVOID_WEIGHTS = (0.25, 0.30, 0.45)
GROUP1_KEY = "group_1"


def _existing_group_keys(rule_id: int) -> List[str]:
    rows = FoodGroupTable.query.filter_by(diet_rule_id=rule_id).all()
    return sorted({str(row.group_key or "").strip() or GROUP1_KEY for row in rows})


def _existing_group1_food_ids(rule_id: int) -> Dict[str, set]:
    rows = (
        FoodGroupTable.query.filter_by(diet_rule_id=rule_id, group_key=GROUP1_KEY).all()
    )
    raw_ids = set()
    cooked_ids = set()
    for row in rows:
        mapping = row.rule_food_map
        if not mapping:
            continue
        if mapping.food_id is not None:
            raw_ids.add(int(mapping.food_id))
        if mapping.cooked_food_id is not None:
            cooked_ids.add(int(mapping.cooked_food_id))
    return {"raw": raw_ids, "cooked": cooked_ids}


def _add_group_mappings(
    *,
    rule_id: int,
    group_key: str,
    recommended_raw_ids,
    avoid_raw_ids,
    recommended_cooked_ids,
    avoid_cooked_ids,
) -> int:
    created = 0

    def attach_mapping(*, food_id, cooked_food_id, notes: str):
        nonlocal created
        mapping = RuleFoodMapTable(food_id=food_id, cooked_food_id=cooked_food_id, notes=notes)
        db.session.add(mapping)
        db.session.flush()
        db.session.add(
            FoodGroupTable(diet_rule_id=rule_id, rule_food_map_id=mapping.id, group_key=group_key)
        )
        created += 1

    for food_id in recommended_raw_ids:
        attach_mapping(food_id=int(food_id), cooked_food_id=None, notes="recommended")
    for food_id in avoid_raw_ids:
        attach_mapping(food_id=int(food_id), cooked_food_id=None, notes="avoid")
    for cooked_food_id in recommended_cooked_ids:
        attach_mapping(food_id=None, cooked_food_id=int(cooked_food_id), notes="recommended")
    for cooked_food_id in avoid_cooked_ids:
        attach_mapping(food_id=None, cooked_food_id=int(cooked_food_id), notes="avoid")

    return created


def backfill(*, dry_run: bool = True) -> Dict[str, Any]:
    raw_items = _load_raw_foods()
    cooked_items = _load_cooked_foods()
    templates = _collect_base_templates()

    report: List[Dict[str, Any]] = []
    total_maps = 0
    total_groups_added = 0
    skipped_no_pool = 0
    skipped_already_done = 0

    for base_rule, base_meta, axes in templates:
        rule_id = int(base_rule.id)
        existing_keys = _existing_group_keys(rule_id)
        existing_group1 = _existing_group1_food_ids(rule_id)

        needs_group1_cooked = len(existing_group1["cooked"]) == 0
        missing_groups = [
            f"group_{i}" for i in range(1, TARGET_GROUP_COUNT + 1) if f"group_{i}" not in existing_keys
        ]

        if not needs_group1_cooked and not missing_groups:
            skipped_already_done += 1
            continue

        filtered_raw = _filter_pool(
            raw_items, diet_type=axes["diet_type"], allergies=axes.get("allergies") or []
        )
        filtered_cooked = _filter_pool(
            cooked_items, diet_type=axes["diet_type"], allergies=axes.get("allergies") or []
        )

        if len(filtered_raw) < 6 or len(filtered_cooked) < 6:
            skipped_no_pool += 1
            continue

        rule_maps_added = 0
        rule_groups_touched = []

        if needs_group1_cooked:
            rng = random.Random(f"{rule_id}:BASE:group_1:cooked")
            rec_cooked = _weighted_sample_items(
                pool=filtered_cooked, weights=NORMAL_REC_WEIGHTS, count=4, rng=rng
            )
            avoid_cooked = _weighted_sample_items(
                pool=filtered_cooked,
                weights=NORMAL_AVOID_WEIGHTS,
                count=2,
                rng=rng,
                exclude_ids=[item["id"] for item in rec_cooked],
            )
            if not dry_run:
                rule_maps_added += _add_group_mappings(
                    rule_id=rule_id,
                    group_key=GROUP1_KEY,
                    recommended_raw_ids=[],
                    avoid_raw_ids=[],
                    recommended_cooked_ids=[item["id"] for item in rec_cooked],
                    avoid_cooked_ids=[item["id"] for item in avoid_cooked],
                )
            else:
                rule_maps_added += len(rec_cooked) + len(avoid_cooked)
            rule_groups_touched.append(GROUP1_KEY)

        for group_key in missing_groups:
            group_index = int(group_key.split("_")[1])
            rng = random.Random(f"{rule_id}:BASE:{group_index}")

            rec_raw = _weighted_sample_items(
                pool=filtered_raw, weights=NORMAL_REC_WEIGHTS, count=4, rng=rng
            )
            avoid_raw = _weighted_sample_items(
                pool=filtered_raw,
                weights=NORMAL_AVOID_WEIGHTS,
                count=2,
                rng=rng,
                exclude_ids=[item["id"] for item in rec_raw],
            )
            rec_cooked = _weighted_sample_items(
                pool=filtered_cooked, weights=NORMAL_REC_WEIGHTS, count=4, rng=rng
            )
            avoid_cooked = _weighted_sample_items(
                pool=filtered_cooked,
                weights=NORMAL_AVOID_WEIGHTS,
                count=2,
                rng=rng,
                exclude_ids=[item["id"] for item in rec_cooked],
            )

            if not dry_run:
                rule_maps_added += _add_group_mappings(
                    rule_id=rule_id,
                    group_key=group_key,
                    recommended_raw_ids=[item["id"] for item in rec_raw],
                    avoid_raw_ids=[item["id"] for item in avoid_raw],
                    recommended_cooked_ids=[item["id"] for item in rec_cooked],
                    avoid_cooked_ids=[item["id"] for item in avoid_cooked],
                )
            else:
                rule_maps_added += len(rec_raw) + len(avoid_raw) + len(rec_cooked) + len(avoid_cooked)
            rule_groups_touched.append(group_key)

        total_maps += rule_maps_added
        total_groups_added += len(rule_groups_touched)
        report.append(
            {
                "rule_id": rule_id,
                "rule_name": base_rule.rule_name,
                "groups_touched": rule_groups_touched,
                "maps_added": rule_maps_added,
            }
        )

        if not dry_run and len(report) % 12 == 0:
            db.session.commit()

    if not dry_run:
        db.session.commit()

    return {
        "base_templates": len(templates),
        "rules_touched": len(report),
        "rules_skipped_already_done": skipped_already_done,
        "rules_skipped_no_pool": skipped_no_pool,
        "groups_added_or_extended": total_groups_added,
        "maps_added": total_maps,
        "details": report,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Backfill group_2..group_4 and cooked-food entries onto base diet rules."
    )
    parser.add_argument("--apply", action="store_true", help="Write changes to the database.")
    parser.add_argument("--dry-run", action="store_true", help="Report only, no writes (default).")
    parser.add_argument(
        "--verbose", action="store_true", help="Print per-rule detail instead of just totals."
    )
    args = parser.parse_args()

    dry_run = not args.apply

    app = create_app()
    with app.app_context():
        stats = backfill(dry_run=dry_run)
        if not args.verbose:
            stats = {k: v for k, v in stats.items() if k != "details"}
        print(json.dumps(stats, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
