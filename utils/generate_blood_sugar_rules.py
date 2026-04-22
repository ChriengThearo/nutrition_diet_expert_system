import argparse
import json
import random
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app import create_app  # noqa: E402
from app.models.cooked_food import CookedFoodsTable  # noqa: E402
from app.models.diet_rule import DietRulesTable  # noqa: E402
from app.models.food import FoodsTable  # noqa: E402
from app.models.food_group import FoodGroupTable  # noqa: E402
from app.models.rule_food_map import RuleFoodMapTable  # noqa: E402
from app.models.associations import tbl_goal_diet_rules  # noqa: E402
from extensions import db  # noqa: E402


GENERATOR_SOURCE = "auto_bs_v1"
GENERATOR_VERSION = 1
GROUP_COUNT = 4
RULE_NAME_MAX = 120
RULE_DESCRIPTION_MAX = 255
SUGAR_CLAMP_MIN = 80
SUGAR_CLAMP_MAX = 320

ALLERGY_SCOPE = {"eggs", "soy", "seafood"}

SEAFOOD_TOKENS = {
    "seafood",
    "fish",
    "salmon",
    "tuna",
    "crab",
    "lobster",
    "shrimp",
    "prawn",
    "oyster",
    "mackerel",
    "sardine",
    "anchovy",
    "squid",
    "clam",
    "mussel",
}
EGG_TOKENS = {"egg", "eggs", "omelet", "omelette", "quail eggs", "goose eggs"}
SOY_TOKENS = {"soy", "soybean", "tofu", "tempeh", "miso"}


@dataclass(frozen=True)
class BloodSugarBand:
    code: str
    label: str
    sugar_multiplier: float
    rec_weights: Tuple[float, float, float]
    avoid_weights: Tuple[float, float, float]
    conditions: Tuple[Tuple[str, str, float], ...]


BANDS: Tuple[BloodSugarBand, ...] = (
    BloodSugarBand(
        code="LOW",
        label="Low",
        sugar_multiplier=1.05,
        rec_weights=(0.20, 0.30, 0.50),
        avoid_weights=(0.50, 0.30, 0.20),
        conditions=(
            ("blood_sugar", "greater_than_or_equals", 0),
            ("blood_sugar", "less_than", 70),
        ),
    ),
    BloodSugarBand(
        code="NORMAL",
        label="Normal",
        sugar_multiplier=1.00,
        rec_weights=(0.34, 0.33, 0.33),
        avoid_weights=(0.25, 0.30, 0.45),
        conditions=(
            ("blood_sugar", "greater_than_or_equals", 70),
            ("blood_sugar", "less_than", 100),
        ),
    ),
    BloodSugarBand(
        code="PREDIABETES",
        label="Prediabetes",
        sugar_multiplier=0.95,
        rec_weights=(0.45, 0.35, 0.20),
        avoid_weights=(0.20, 0.30, 0.50),
        conditions=(
            ("blood_sugar", "greater_than_or_equals", 100),
            ("blood_sugar", "less_than", 126),
        ),
    ),
    BloodSugarBand(
        code="DIABETES",
        label="Diabetes",
        sugar_multiplier=0.90,
        rec_weights=(0.55, 0.30, 0.15),
        avoid_weights=(0.10, 0.25, 0.65),
        conditions=(
            ("blood_sugar", "greater_than_or_equals", 126),
            ("blood_sugar", "less_than_or_equals", 1000),
        ),
    ),
)


def _to_text(value: Any) -> str:
    return str(value or "").strip()


def _parse_json(value: str) -> Any:
    try:
        return json.loads(value)
    except Exception:
        return None


def _normalize_operator(op: str) -> str:
    normalized = _to_text(op).lower()
    if normalized == ">":
        return "greater_than"
    if normalized == "<":
        return "less_than"
    if normalized == ">=":
        return "greater_than_or_equals"
    if normalized == "<=":
        return "less_than_or_equals"
    if normalized == "greater_or_equals":
        return "greater_than_or_equals"
    if normalized == "less_or_equals":
        return "less_than_or_equals"
    return normalized


def _parse_rule_meta(rule: DietRulesTable) -> Dict[str, Any]:
    raw = _to_text(rule.conditions)
    parsed = _parse_json(raw) if raw else None

    meta: Dict[str, Any] = {
        "category": "health",
        "priority": "medium",
        "active": bool(rule.is_active),
        "conditions": [],
        "actions": [],
    }
    if isinstance(parsed, dict):
        meta["category"] = _to_text(parsed.get("category")) or "health"
        meta["priority"] = _to_text(parsed.get("priority")) or "medium"
        meta["active"] = bool(parsed.get("active", rule.is_active))
        meta["conditions"] = [
            _to_text(item) for item in (parsed.get("conditions") or []) if _to_text(item)
        ]
        meta["actions"] = [
            _to_text(item) for item in (parsed.get("actions") or []) if _to_text(item)
        ]
        for passthrough_key in (
            "source",
            "base_rule_id",
            "blood_sugar_band",
            "goal_type",
            "food_groups",
            "recommended_food_ids",
            "excluded_food_ids",
            "recommended_cooked_food_ids",
            "excluded_cooked_food_ids",
        ):
            if passthrough_key in parsed:
                meta[passthrough_key] = parsed.get(passthrough_key)
        return meta

    if isinstance(parsed, list):
        meta["conditions"] = [_to_text(item) for item in parsed if _to_text(item)]
        return meta

    if raw:
        parts = [part.strip() for part in raw.replace(";", ",").split(",")]
        meta["conditions"] = [part for part in parts if part]

    return meta


def _fmt_number(value: float) -> str:
    if abs(value - round(value)) < 1e-9:
        return str(int(round(value)))
    return f"{value:.2f}".rstrip("0").rstrip(".")


def _safe_round_int(value: float) -> int:
    return int(round(float(value)))


def _extract_numeric_condition(condition: str) -> Optional[Tuple[str, str, float]]:
    text = _to_text(condition)
    if not text:
        return None
    parts = text.split()
    if len(parts) < 3:
        return None
    param = parts[0].lower().replace("-", "_")
    if param == "bloodsugar":
        param = "blood_sugar"
    op = _normalize_operator(parts[1])
    raw_value = " ".join(parts[2:])
    try:
        number = float(raw_value)
    except Exception:
        return None
    return param, op, number


def _extract_rule_axes(meta: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    conditions = meta.get("conditions") or []
    lower_bmi = None
    upper_bmi = None
    gender = None
    diet_type = None
    allergies: List[str] = []
    has_blood_sugar = False

    for condition in conditions:
        normalized = _to_text(condition).lower()
        if normalized.startswith("recommend foods:") or normalized.startswith("avoid foods:"):
            continue

        parts = normalized.split()
        if len(parts) < 3:
            continue
        param = parts[0].replace("-", "_")
        if param == "bloodsugar":
            param = "blood_sugar"
        operator = _normalize_operator(parts[1])
        value = " ".join(parts[2:]).strip()

        if param == "blood_sugar":
            has_blood_sugar = True
            continue

        if param == "bmi":
            try:
                numeric = float(value)
            except Exception:
                continue
            if operator in {"greater_than", "greater_than_or_equals"}:
                lower_bmi = numeric
            elif operator in {"less_than", "less_than_or_equals"}:
                upper_bmi = numeric
            continue

        if param == "gender" and operator == "equals":
            candidate = value.lower()
            if candidate in {"male", "female"}:
                gender = candidate
            continue

        if param == "diet_type" and operator == "equals":
            candidate = value.lower()
            if candidate in {"normal", "vegan"}:
                diet_type = candidate
            continue

        if param in {"allergy", "allergies"} and operator in {"contains", "equals"}:
            candidate = value.lower()
            if candidate in ALLERGY_SCOPE and candidate not in allergies:
                allergies.append(candidate)

    if lower_bmi is None:
        lower_bmi = 0.0

    if upper_bmi is None or gender is None or diet_type is None:
        return None

    return {
        "lower_bmi": lower_bmi,
        "upper_bmi": upper_bmi,
        "gender": gender,
        "diet_type": diet_type,
        "allergies": sorted(allergies),
        "has_blood_sugar": has_blood_sugar,
    }


def _extract_action_targets(actions: Sequence[str]) -> Dict[str, Optional[float]]:
    targets: Dict[str, Optional[float]] = {
        "calories": None,
        "protein": None,
        "sugar": None,
        "fat": None,
    }
    for action in actions:
        text = _to_text(action).lower()
        if not text:
            continue

        if "set_calories" in text:
            match = re.search(r"calories\s*=\s*(-?\d+(?:\.\d+)?)", text)
            if not match:
                match = re.search(r"(-?\d+(?:\.\d+)?)", text)
            if match:
                targets["calories"] = float(match.group(1))

        if "set_macros" in text:
            for macro in ("protein", "sugar", "fat"):
                match = re.search(rf"{macro}\s*=\s*(-?\d+(?:\.\d+)?)", text)
                if match:
                    targets[macro] = float(match.group(1))
    return targets


def _infer_tags(
    *,
    name: str,
    description: str,
    food_type: str,
    cooking_method: str = "",
) -> List[str]:
    text = " ".join([name, description, food_type, cooking_method]).lower()
    tags = set()

    if any(token in text for token in EGG_TOKENS) or "egg" in food_type.lower():
        tags.add("eggs")
    if any(token in text for token in SOY_TOKENS) or "soy" in food_type.lower():
        tags.add("soy")
    if any(token in text for token in SEAFOOD_TOKENS) or "seafood" in food_type.lower():
        tags.add("seafood")

    return sorted(tags)


def _load_raw_foods() -> List[Dict[str, Any]]:
    rows = FoodsTable.query.order_by(FoodsTable.id.asc()).all()
    items: List[Dict[str, Any]] = []
    for row in rows:
        items.append(
            {
                "id": int(row.id),
                "name": _to_text(row.name),
                "description": _to_text(row.description),
                "food_type": _to_text(row.food_type),
                "is_vegan": bool(row.is_gevan),
                "sugar": float(row.sugar or 0),
                "tags": _infer_tags(
                    name=_to_text(row.name),
                    description=_to_text(row.description),
                    food_type=_to_text(row.food_type),
                ),
            }
        )
    return items


def _load_cooked_foods() -> List[Dict[str, Any]]:
    rows = CookedFoodsTable.query.order_by(CookedFoodsTable.id.asc()).all()
    items: List[Dict[str, Any]] = []
    for row in rows:
        items.append(
            {
                "id": int(row.id),
                "name": _to_text(row.name),
                "description": _to_text(row.description),
                "food_type": _to_text(row.food_type),
                "cooking_method": _to_text(row.cooking_method),
                "is_vegan": bool(row.is_gevan),
                "sugar": float(row.sugar or 0),
                "tags": _infer_tags(
                    name=_to_text(row.name),
                    description=_to_text(row.description),
                    food_type=_to_text(row.food_type),
                    cooking_method=_to_text(row.cooking_method),
                ),
            }
        )
    return items


def _filter_pool(
    items: Sequence[Dict[str, Any]],
    *,
    diet_type: str,
    allergies: Sequence[str],
) -> List[Dict[str, Any]]:
    allergy_set = {item for item in allergies if item in ALLERGY_SCOPE}
    filtered: List[Dict[str, Any]] = []
    for item in items:
        if diet_type == "vegan" and not bool(item.get("is_vegan")):
            continue
        tags = set(item.get("tags") or [])
        if tags.intersection(allergy_set):
            continue
        filtered.append(item)
    return filtered


def _split_tertiles(items: Sequence[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], ...]:
    ordered = sorted(items, key=lambda item: (float(item.get("sugar") or 0), int(item["id"])))
    total = len(ordered)
    if total == 0:
        return ([], [], [])
    low_end = max(1, total // 3)
    mid_end = max(low_end + 1, (2 * total) // 3)
    if mid_end > total:
        mid_end = total
    low = ordered[:low_end]
    mid = ordered[low_end:mid_end]
    high = ordered[mid_end:]
    return (list(low), list(mid), list(high))


def _weighted_pick_bin(
    available: Sequence[str],
    weight_map: Dict[str, float],
    rng: random.Random,
) -> str:
    total_weight = sum(weight_map[name] for name in available)
    if total_weight <= 0:
        return available[-1]
    pick = rng.random() * total_weight
    cumulative = 0.0
    selected = available[-1]
    for name in available:
        cumulative += weight_map[name]
        if pick <= cumulative:
            selected = name
            break
    return selected


def _weighted_sample_items(
    *,
    pool: Sequence[Dict[str, Any]],
    weights: Tuple[float, float, float],
    count: int,
    rng: random.Random,
    exclude_ids: Optional[Sequence[int]] = None,
) -> List[Dict[str, Any]]:
    excluded = {int(item) for item in (exclude_ids or [])}
    source = [item for item in pool if int(item["id"]) not in excluded]
    low, mid, high = _split_tertiles(source)
    bins = {"low": low, "mid": mid, "high": high}
    weight_map = {"low": weights[0], "mid": weights[1], "high": weights[2]}
    selected: List[Dict[str, Any]] = []

    while len(selected) < count:
        available_bins = [name for name in ("low", "mid", "high") if bins[name]]
        if not available_bins:
            break
        chosen_bin = _weighted_pick_bin(available_bins, weight_map, rng)
        bin_items = bins[chosen_bin]
        pick_index = rng.randrange(len(bin_items))
        selected.append(bin_items.pop(pick_index))

    if len(selected) < count:
        remainder = []
        for name in ("low", "mid", "high"):
            remainder.extend(bins[name])
        rng.shuffle(remainder)
        for item in remainder:
            if len(selected) >= count:
                break
            selected.append(item)

    return selected[:count]


def _dedupe_names(items: Sequence[Dict[str, Any]]) -> List[str]:
    names: List[str] = []
    seen = set()
    for item in items:
        name = _to_text(item.get("name"))
        lower = name.lower()
        if not name or lower in seen:
            continue
        seen.add(lower)
        names.append(name)
    return names


def _trim_text(text: str, limit: int) -> str:
    value = _to_text(text)
    if len(value) <= limit:
        return value
    return value[: max(0, limit - 1)].rstrip() + "…"


def _build_rule_name(base_name: str, band_label: str) -> str:
    return _trim_text(f"{_to_text(base_name)} [Blood Sugar {band_label}]", RULE_NAME_MAX)


def _build_rule_description(base_description: str, band_label: str) -> str:
    prefix = _to_text(base_description) or "Auto-generated blood sugar optimized diet rule."
    return _trim_text(f"{prefix} Blood sugar band: {band_label}.", RULE_DESCRIPTION_MAX)


def _cleanup_previous_generated_rules(dry_run: bool = False) -> Dict[str, int]:
    all_rules = DietRulesTable.query.all()
    generated_ids: List[int] = []
    for rule in all_rules:
        meta = _parse_rule_meta(rule)
        if _to_text(meta.get("source")).lower() == GENERATOR_SOURCE:
            generated_ids.append(int(rule.id))

    if not generated_ids:
        return {"rules_deleted": 0, "food_groups_deleted": 0, "maps_deleted": 0}

    group_rows = FoodGroupTable.query.filter(
        FoodGroupTable.diet_rule_id.in_(generated_ids)
    ).all()
    map_ids = sorted(
        {
            int(row.rule_food_map_id)
            for row in group_rows
            if row.rule_food_map_id is not None
        }
    )

    if dry_run:
        return {
            "rules_deleted": len(generated_ids),
            "food_groups_deleted": len(group_rows),
            "maps_deleted": len(map_ids),
        }

    if group_rows:
        FoodGroupTable.query.filter(
            FoodGroupTable.diet_rule_id.in_(generated_ids)
        ).delete(synchronize_session=False)
    if map_ids:
        RuleFoodMapTable.query.filter(
            RuleFoodMapTable.id.in_(map_ids)
        ).delete(synchronize_session=False)
    db.session.execute(
        tbl_goal_diet_rules.delete().where(
            tbl_goal_diet_rules.c.diet_rule_id.in_(generated_ids)
        )
    )
    DietRulesTable.query.filter(DietRulesTable.id.in_(generated_ids)).delete(
        synchronize_session=False
    )
    db.session.commit()

    return {
        "rules_deleted": len(generated_ids),
        "food_groups_deleted": len(group_rows),
        "maps_deleted": len(map_ids),
    }


def _collect_base_templates() -> List[Tuple[DietRulesTable, Dict[str, Any], Dict[str, Any]]]:
    templates: List[Tuple[DietRulesTable, Dict[str, Any], Dict[str, Any]]] = []
    all_rules = DietRulesTable.query.order_by(DietRulesTable.id.asc()).all()

    for rule in all_rules:
        if not bool(rule.is_active):
            continue
        meta = _parse_rule_meta(rule)
        if _to_text(meta.get("source")).lower() == GENERATOR_SOURCE:
            continue

        axes = _extract_rule_axes(meta)
        if not axes:
            continue
        if axes.get("has_blood_sugar"):
            continue
        templates.append((rule, meta, axes))

    return templates


def _build_actions(
    base_actions: Sequence[str],
    *,
    sugar_multiplier: float,
) -> List[str]:
    targets = _extract_action_targets(base_actions)
    calories = targets.get("calories")
    protein = targets.get("protein")
    sugar = targets.get("sugar")
    fat = targets.get("fat")

    adjusted_sugar = None
    if sugar is not None:
        adjusted_sugar = _safe_round_int(sugar * sugar_multiplier)
        adjusted_sugar = max(SUGAR_CLAMP_MIN, min(SUGAR_CLAMP_MAX, adjusted_sugar))

    actions: List[str] = []
    if calories is not None:
        actions.append(
            f"set_calories: calories={_fmt_number(float(calories))} kcal/day"
        )

    macro_parts: List[str] = []
    if protein is not None:
        macro_parts.append(f"protein={_fmt_number(float(protein))}g")
    if adjusted_sugar is not None:
        macro_parts.append(f"sugar={_fmt_number(float(adjusted_sugar))}g")
    elif sugar is not None:
        macro_parts.append(f"sugar={_fmt_number(float(sugar))}g")
    if fat is not None:
        macro_parts.append(f"fat={_fmt_number(float(fat))}g")
    if macro_parts:
        actions.append(f"set_macros: {', '.join(macro_parts)}")

    return actions


def _build_conditions(
    *,
    axes: Dict[str, Any],
    band: BloodSugarBand,
    recommend_names: Sequence[str],
    avoid_names: Sequence[str],
) -> List[str]:
    conditions: List[str] = []
    conditions.append(
        f"bmi greater_than_or_equals {_fmt_number(float(axes['lower_bmi']))}"
    )
    conditions.append(f"bmi less_than {_fmt_number(float(axes['upper_bmi']))}")
    conditions.append(f"gender equals {axes['gender']}")
    conditions.append(f"diet_type equals {axes['diet_type']}")
    for allergy in axes.get("allergies") or []:
        conditions.append(f"allergy contains {allergy}")
    for param, op, value in band.conditions:
        conditions.append(f"{param} {op} {_fmt_number(float(value))}")
    if recommend_names:
        conditions.append(f"recommend foods: {', '.join(recommend_names)}")
    if avoid_names:
        conditions.append(f"avoid foods: {', '.join(avoid_names)}")
    return conditions


def _add_group_mappings(
    *,
    rule_id: int,
    group_key: str,
    recommended_raw_ids: Sequence[int],
    avoid_raw_ids: Sequence[int],
    recommended_cooked_ids: Sequence[int],
    avoid_cooked_ids: Sequence[int],
) -> int:
    created = 0

    def attach_mapping(*, food_id: Optional[int], cooked_food_id: Optional[int], notes: str):
        nonlocal created
        mapping = RuleFoodMapTable(
            food_id=food_id,
            cooked_food_id=cooked_food_id,
            notes=notes,
        )
        db.session.add(mapping)
        db.session.flush()
        db.session.add(
            FoodGroupTable(
                diet_rule_id=rule_id,
                rule_food_map_id=mapping.id,
                group_key=group_key,
            )
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


def generate_rules(*, dry_run: bool = False) -> Dict[str, int]:
    raw_items = _load_raw_foods()
    cooked_items = _load_cooked_foods()

    cleanup_stats = _cleanup_previous_generated_rules(dry_run=dry_run)
    templates = _collect_base_templates()

    inserted_rules = 0
    inserted_maps = 0
    inserted_groups = 0

    if dry_run:
        expected_rules = len(templates) * len(BANDS)
        expected_maps = expected_rules * GROUP_COUNT * (4 + 2 + 4 + 2)
        return {
            "base_templates": len(templates),
            "rules_deleted": cleanup_stats["rules_deleted"],
            "food_groups_deleted": cleanup_stats["food_groups_deleted"],
            "maps_deleted": cleanup_stats["maps_deleted"],
            "rules_inserted": expected_rules,
            "food_groups_inserted": expected_maps,
            "maps_inserted": expected_maps,
        }

    for template_index, (base_rule, base_meta, axes) in enumerate(templates, start=1):
        base_actions = base_meta.get("actions") or []
        base_description = _to_text(base_rule.description)
        base_category = _to_text(base_meta.get("category")) or "health"
        goal_type = _to_text(base_meta.get("goal_type"))

        filtered_raw = _filter_pool(
            raw_items,
            diet_type=axes["diet_type"],
            allergies=axes.get("allergies") or [],
        )
        filtered_cooked = _filter_pool(
            cooked_items,
            diet_type=axes["diet_type"],
            allergies=axes.get("allergies") or [],
        )

        if len(filtered_raw) < 6 or len(filtered_cooked) < 6:
            continue

        for band in BANDS:
            groups_payload: List[Dict[str, Any]] = []
            all_recommended_raw: List[Dict[str, Any]] = []
            all_avoid_raw: List[Dict[str, Any]] = []

            for group_index in range(1, GROUP_COUNT + 1):
                rng = random.Random(f"{int(base_rule.id)}:{band.code}:{group_index}")

                rec_raw = _weighted_sample_items(
                    pool=filtered_raw,
                    weights=band.rec_weights,
                    count=4,
                    rng=rng,
                )
                avoid_raw = _weighted_sample_items(
                    pool=filtered_raw,
                    weights=band.avoid_weights,
                    count=2,
                    rng=rng,
                    exclude_ids=[item["id"] for item in rec_raw],
                )
                rec_cooked = _weighted_sample_items(
                    pool=filtered_cooked,
                    weights=band.rec_weights,
                    count=4,
                    rng=rng,
                )
                avoid_cooked = _weighted_sample_items(
                    pool=filtered_cooked,
                    weights=band.avoid_weights,
                    count=2,
                    rng=rng,
                    exclude_ids=[item["id"] for item in rec_cooked],
                )

                group_payload = {
                    "group_key": f"group_{group_index}",
                    "recommended_food_ids": [int(item["id"]) for item in rec_raw],
                    "excluded_food_ids": [int(item["id"]) for item in avoid_raw],
                    "recommended_cooked_food_ids": [int(item["id"]) for item in rec_cooked],
                    "excluded_cooked_food_ids": [int(item["id"]) for item in avoid_cooked],
                }
                groups_payload.append(group_payload)
                all_recommended_raw.extend(rec_raw)
                all_avoid_raw.extend(avoid_raw)

            recommend_names = _dedupe_names(all_recommended_raw)
            avoid_names = _dedupe_names(all_avoid_raw)
            generated_actions = _build_actions(
                base_actions,
                sugar_multiplier=band.sugar_multiplier,
            )
            generated_conditions = _build_conditions(
                axes=axes,
                band=band,
                recommend_names=recommend_names,
                avoid_names=avoid_names,
            )

            meta: Dict[str, Any] = {
                "category": base_category,
                "priority": "high",
                "active": True,
                "source": GENERATOR_SOURCE,
                "generator_version": GENERATOR_VERSION,
                "base_rule_id": int(base_rule.id),
                "base_rule_name": _to_text(base_rule.rule_name),
                "blood_sugar_band": band.code,
                "blood_sugar_label": band.label,
                "conditions": generated_conditions,
                "actions": generated_actions,
                "food_groups": groups_payload,
                "recommended_food_ids": sorted(
                    {
                        food_id
                        for group in groups_payload
                        for food_id in group["recommended_food_ids"]
                    }
                ),
                "excluded_food_ids": sorted(
                    {
                        food_id
                        for group in groups_payload
                        for food_id in group["excluded_food_ids"]
                    }
                ),
                "recommended_cooked_food_ids": sorted(
                    {
                        food_id
                        for group in groups_payload
                        for food_id in group["recommended_cooked_food_ids"]
                    }
                ),
                "excluded_cooked_food_ids": sorted(
                    {
                        food_id
                        for group in groups_payload
                        for food_id in group["excluded_cooked_food_ids"]
                    }
                ),
            }
            if goal_type:
                meta["goal_type"] = goal_type

            rule = DietRulesTable(
                rule_name=_build_rule_name(base_rule.rule_name, band.label),
                description=_build_rule_description(base_description, band.label),
                is_active=True,
                conditions=json.dumps(meta, ensure_ascii=False),
            )
            db.session.add(rule)
            db.session.flush()

            inserted_rules += 1

            for group in groups_payload:
                created = _add_group_mappings(
                    rule_id=int(rule.id),
                    group_key=group["group_key"],
                    recommended_raw_ids=group["recommended_food_ids"],
                    avoid_raw_ids=group["excluded_food_ids"],
                    recommended_cooked_ids=group["recommended_cooked_food_ids"],
                    avoid_cooked_ids=group["excluded_cooked_food_ids"],
                )
                inserted_maps += created
                inserted_groups += created

        if template_index % 12 == 0:
            db.session.commit()

    db.session.commit()

    return {
        "base_templates": len(templates),
        "rules_deleted": cleanup_stats["rules_deleted"],
        "food_groups_deleted": cleanup_stats["food_groups_deleted"],
        "maps_deleted": cleanup_stats["maps_deleted"],
        "rules_inserted": inserted_rules,
        "food_groups_inserted": inserted_groups,
        "maps_inserted": inserted_maps,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Generate blood-sugar matrix diet rules and grouped food mappings."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show expected generation counts without writing to DB.",
    )
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        stats = generate_rules(dry_run=bool(args.dry_run))
        print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
