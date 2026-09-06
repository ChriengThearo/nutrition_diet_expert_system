"""Sync the base diet rules' stored `conditions` JSON with the food-group
data added by backfill_base_rule_groups.py.

backfill_base_rule_groups.py adds group_2..group_4 and cooked-food entries
directly into tbl_food_groups / tbl_rule_food_map. It intentionally does not
touch tbl_diet_rules.conditions, because the app's matching/food-selection
logic reads food groups from those DB tables, not from the JSON blob.

But the doctor dashboard's Rule Library reads the human-readable
"recommend foods: ..." / "avoid foods: ..." condition text, and the
top-level recommended_food_ids/excluded_food_ids lists, straight out of
that JSON blob (see doctor_rules() in dashboard_routes.py). After the
backfill those went stale - they still list only the original group_1
foods - so the Rule Library shows counts/food_groups that don't match the
condition text shown right next to them. This script regenerates that text
and the top-level id lists from the current DB state, for the 144 base
rules only, using the same "raw names only, deduped across groups"
convention generate_blood_sugar_rules.py uses for its own generated rules.

Usage:
    python utils/sync_base_rule_conditions.py --dry-run
    python utils/sync_base_rule_conditions.py --apply
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app import create_app  # noqa: E402
from app.models.diet_rule import DietRulesTable  # noqa: E402
from app.models.food_group import FoodGroupTable  # noqa: E402
from extensions import db  # noqa: E402

from utils.generate_blood_sugar_rules import _collect_base_templates  # noqa: E402


def _dedupe_names(names: List[str]) -> List[str]:
    seen = set()
    out = []
    for name in names:
        lower = name.lower()
        if not name or lower in seen:
            continue
        seen.add(lower)
        out.append(name)
    return out


def _rule_food_group_data(rule_id: int) -> Dict[str, Any]:
    rows = FoodGroupTable.query.filter_by(diet_rule_id=rule_id).order_by(
        FoodGroupTable.group_key.asc(), FoodGroupTable.id.asc()
    ).all()

    groups: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        mapping = row.rule_food_map
        if not mapping:
            continue
        group_key = str(row.group_key or "").strip() or "group_1"
        if group_key not in groups:
            groups[group_key] = {
                "group_key": group_key,
                "recommended_food_ids": [],
                "excluded_food_ids": [],
                "recommended_cooked_food_ids": [],
                "excluded_cooked_food_ids": [],
            }
        target = groups[group_key]
        is_avoid = (mapping.notes or "").strip().lower() == "avoid"

        if mapping.food_id is not None:
            key = "excluded_food_ids" if is_avoid else "recommended_food_ids"
            target[key].append(int(mapping.food_id))
            food = mapping.food
            if food is not None:
                bucket = "avoid_raw_names" if is_avoid else "rec_raw_names"
                target.setdefault(bucket, []).append(food.name)

        if mapping.cooked_food_id is not None:
            key = "excluded_cooked_food_ids" if is_avoid else "recommended_cooked_food_ids"
            target[key].append(int(mapping.cooked_food_id))

    return groups


def sync(*, dry_run: bool = True) -> Dict[str, Any]:
    templates = _collect_base_templates()
    updated = 0
    report = []

    for base_rule, base_meta, axes in templates:
        rule_id = int(base_rule.id)
        groups = _rule_food_group_data(rule_id)
        if not groups:
            continue

        all_rec_names: List[str] = []
        all_avoid_names: List[str] = []
        food_groups_payload = []
        for group_key in sorted(groups.keys()):
            group = groups[group_key]
            all_rec_names.extend(group.get("rec_raw_names", []))
            all_avoid_names.extend(group.get("avoid_raw_names", []))
            food_groups_payload.append(
                {
                    "group_key": group_key,
                    "recommended_food_ids": group["recommended_food_ids"],
                    "excluded_food_ids": group["excluded_food_ids"],
                    "recommended_cooked_food_ids": group["recommended_cooked_food_ids"],
                    "excluded_cooked_food_ids": group["excluded_cooked_food_ids"],
                }
            )

        recommend_names = _dedupe_names(all_rec_names)
        avoid_names = _dedupe_names(all_avoid_names)

        raw = base_rule.conditions or ""
        try:
            meta = json.loads(raw) if raw else {}
        except Exception:
            meta = {}
        if not isinstance(meta, dict):
            continue

        conditions_list = [str(item) for item in (meta.get("conditions") or [])]
        new_conditions_list = [
            item
            for item in conditions_list
            if not item.lower().startswith("recommend foods:")
            and not item.lower().startswith("avoid foods:")
        ]
        if recommend_names:
            new_conditions_list.append(f"recommend foods: {', '.join(recommend_names)}")
        if avoid_names:
            new_conditions_list.append(f"avoid foods: {', '.join(avoid_names)}")

        meta["conditions"] = new_conditions_list
        meta["food_groups"] = food_groups_payload
        meta["recommended_food_ids"] = sorted(
            {fid for g in food_groups_payload for fid in g["recommended_food_ids"]}
        )
        meta["excluded_food_ids"] = sorted(
            {fid for g in food_groups_payload for fid in g["excluded_food_ids"]}
        )
        meta["recommended_cooked_food_ids"] = sorted(
            {fid for g in food_groups_payload for fid in g["recommended_cooked_food_ids"]}
        )
        meta["excluded_cooked_food_ids"] = sorted(
            {fid for g in food_groups_payload for fid in g["excluded_cooked_food_ids"]}
        )

        new_raw = json.dumps(meta, ensure_ascii=False)
        if new_raw != raw:
            updated += 1
            report.append(
                {
                    "rule_id": rule_id,
                    "rule_name": base_rule.rule_name,
                    "recommend_foods": recommend_names,
                    "avoid_foods": avoid_names,
                }
            )
            if not dry_run:
                base_rule.conditions = new_raw

    if not dry_run:
        db.session.commit()

    return {
        "base_templates": len(templates),
        "rules_updated": updated,
        "details": report,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Sync base diet rules' conditions JSON with current food-group DB state."
    )
    parser.add_argument("--apply", action="store_true", help="Write changes to the database.")
    parser.add_argument("--dry-run", action="store_true", help="Report only, no writes (default).")
    parser.add_argument("--verbose", action="store_true", help="Print per-rule detail.")
    args = parser.parse_args()

    dry_run = not args.apply

    app = create_app()
    with app.app_context():
        stats = sync(dry_run=dry_run)
        if not args.verbose:
            stats = {k: v for k, v in stats.items() if k != "details"}
        print(json.dumps(stats, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
