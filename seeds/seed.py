import base64
import json
import random
import re
import sys
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

from sqlalchemy import MetaData, delete, func, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.sql.sqltypes import Boolean, Date, DateTime, LargeBinary, Numeric


ROOT_DIR = Path(__file__).resolve().parents[1]
SEEDS_DIR = Path(__file__).resolve().parent
IGNORED_TABLES = {"alembic_version"}

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app import create_app  # noqa: E402
from extensions import db  # noqa: E402

CAMBODIAN_FAMILY_NAMES = [
    "Chan",
    "Chea",
    "Chhim",
    "Choun",
    "Heng",
    "Hor",
    "Khun",
    "Kim",
    "Kong",
    "Lim",
    "Ly",
    "Mao",
    "Meng",
    "Noun",
    "Nuon",
    "Oum",
    "Pen",
    "Pho",
    "Pich",
    "Prak",
    "Rin",
    "Run",
    "Sam",
    "Seng",
    "Sok",
    "Suon",
    "Tat",
    "Thy",
    "Touch",
    "Yim",
]

CAMBODIAN_MALE_GIVEN_NAMES = [
    "Borey",
    "Bunthoeun",
    "Chanthorn",
    "Chetra",
    "Dara",
    "Kimheng",
    "Kosal",
    "Mony",
    "Narin",
    "Phearum",
    "Piseth",
    "Ratanak",
    "Rithy",
    "Sok",
    "Sokha",
    "Sopheak",
    "Sovann",
    "Vannak",
    "Vathanak",
    "Vichea",
]

CAMBODIAN_FEMALE_GIVEN_NAMES = [
    "Bopha",
    "Chanrith",
    "Davy",
    "Kanika",
    "Kunthea",
    "Malis",
    "Monineath",
    "Nary",
    "Pheary",
    "Pich",
    "Rachana",
    "Rany",
    "Ratha",
    "Sokly",
    "Sokunthea",
    "Sophea",
    "Sreyleak",
    "Sreymao",
    "Sreyneang",
    "Sreypov",
]

ALLERGY_COMBINATIONS = [
    (),
    ("seafood",),
    ("eggs",),
    ("soy",),
    ("seafood", "eggs"),
    ("seafood", "soy"),
    ("eggs", "soy"),
    ("seafood", "eggs", "soy"),
]

DIET_TYPES = ["normal", "vegan"]
MEALS_PER_DAY_OPTIONS = [2, 3, 4]
FOOD_PREFERENCE_OPTIONS = ["raw", "cooked"]


def _serialize_value(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (bytes, bytearray)):
        encoded = base64.b64encode(bytes(value)).decode("ascii")
        return f"base64:{encoded}"
    return value


def _convert_value(column, value):
    if value is None:
        return None
    if isinstance(column.type, DateTime):
        if isinstance(value, str):
            return datetime.fromisoformat(value)
    if isinstance(column.type, Date):
        if isinstance(value, str):
            return date.fromisoformat(value)
    if isinstance(column.type, Boolean):
        if isinstance(value, bool):
            return value
        if isinstance(value, int):
            return bool(value)
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "t", "yes", "y"}
    if isinstance(column.type, LargeBinary):
        if isinstance(value, str) and value.startswith("base64:"):
            return base64.b64decode(value.split(":", 1)[1])
    if isinstance(column.type, Numeric):
        if isinstance(value, (str, int, float)):
            return Decimal(str(value))
    return value


def _reflect_metadata():
    metadata = MetaData()
    metadata.reflect(bind=db.engine)
    return metadata


def dump_all():
    metadata = _reflect_metadata()
    tables = [
        table for table in metadata.sorted_tables if table.name not in IGNORED_TABLES
    ]
    if not tables:
        print("No tables found to dump.")
        return

    meta_payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "database": str(db.engine.url.database or ""),
        "tables": [table.name for table in tables],
        "row_counts": {},
    }

    with db.engine.connect() as conn:
        for table in tables:
            order_by_cols = list(table.primary_key.columns) if table.primary_key else []
            if order_by_cols:
                result = conn.execute(table.select().order_by(*order_by_cols))
            else:
                result = conn.execute(table.select())
            rows = []
            for row in result:
                row_data = {}
                mapping = row._mapping
                for column in table.columns:
                    row_data[column.name] = _serialize_value(mapping[column.name])
                rows.append(row_data)
            meta_payload["row_counts"][table.name] = len(rows)

            table_path = SEEDS_DIR / f"{table.name}.json"
            with table_path.open("w", encoding="utf-8") as handle:
                json.dump(rows, handle, indent=2, ensure_ascii=True)

    meta_path = SEEDS_DIR / "_meta.json"
    with meta_path.open("w", encoding="utf-8") as handle:
        json.dump(meta_payload, handle, indent=2, ensure_ascii=True)

    print(f"Dumped {len(tables)} tables into {SEEDS_DIR}")


def _load_table_order():
    meta_path = SEEDS_DIR / "_meta.json"
    if meta_path.exists():
        try:
            with meta_path.open("r", encoding="utf-8") as handle:
                meta_payload = json.load(handle)
                tables = meta_payload.get("tables") or []
                if tables:
                    return [name for name in tables if name not in IGNORED_TABLES]
        except Exception:
            pass

    table_files = sorted(
        path.stem
        for path in SEEDS_DIR.glob("*.json")
        if path.name != "_meta.json" and path.stem not in IGNORED_TABLES
    )
    return table_files


def restore_all():
    metadata = _reflect_metadata()
    table_order = _load_table_order()
    if not table_order:
        print("No seed files found to restore.")
        return

    missing = [name for name in table_order if name not in metadata.tables]
    if missing:
        print(f"Skipping missing tables in database: {', '.join(missing)}")
        table_order = [name for name in table_order if name in metadata.tables]
        if not table_order:
            print("No matching seed tables found in current database schema.")
            return

    dialect_name = db.engine.dialect.name

    with db.engine.begin() as conn:
        if dialect_name == "mysql":
            conn.execute(text("SET FOREIGN_KEY_CHECKS=0;"))

        for table_name in reversed(table_order):
            table = metadata.tables[table_name]
            conn.execute(table.delete())

        for table_name in table_order:
            table = metadata.tables[table_name]
            table_path = SEEDS_DIR / f"{table_name}.json"
            if not table_path.exists():
                continue
            with table_path.open("r", encoding="utf-8") as handle:
                rows = json.load(handle)
            if not rows:
                continue
            payload = []
            for row in rows:
                converted = {}
                for column in table.columns:
                    if column.name in row:
                        converted[column.name] = _convert_value(
                            column, row[column.name]
                        )
                payload.append(converted)
            conn.execute(table.insert(), payload)

        if dialect_name == "mysql":
            conn.execute(text("SET FOREIGN_KEY_CHECKS=1;"))

    print(f"Restored data for {len(table_order)} tables from {SEEDS_DIR}")


def _slugify_username(text):
    base = re.sub(r"[^a-z0-9]+", "", str(text or "").strip().lower())
    return base or "user"


def _generate_cambodian_name(rng, used_full_names):
    max_attempts = 500
    for _ in range(max_attempts):
        if rng.choice([True, False]):
            gender = "male"
            given_name = rng.choice(CAMBODIAN_MALE_GIVEN_NAMES)
        else:
            gender = "female"
            given_name = rng.choice(CAMBODIAN_FEMALE_GIVEN_NAMES)

        family_name = rng.choice(CAMBODIAN_FAMILY_NAMES)
        full_name = f"{given_name} {family_name}"
        if full_name not in used_full_names:
            used_full_names.add(full_name)
            return full_name, gender

    raise RuntimeError("Unable to generate a unique Cambodian-style full name.")


def _make_unique_username_and_email(full_name, used_usernames, used_emails, domain):
    base = _slugify_username(full_name)[:24]
    if not base:
        base = "user"

    suffix = 0
    while True:
        suffix_text = str(suffix) if suffix else ""
        max_username_len = 80 - len(suffix_text)
        trimmed_base = base[: max(1, max_username_len)]
        username = f"{trimmed_base}{suffix_text}"

        email_local_max = 64 - len(suffix_text)
        trimmed_local = base[: max(1, email_local_max)]
        email_local = f"{trimmed_local}{suffix_text}"
        email = f"{email_local}@{domain}"

        if username not in used_usernames and email not in used_emails:
            used_usernames.add(username)
            used_emails.add(email)
            return username, email

        suffix += 1


def _build_profile_template(rng, gender):
    return {
        "gender": gender,
        "weight": round(rng.uniform(40, 80), 1),
        "height": rng.randint(155, 182),
        "blood_sugar": round(rng.uniform(55, 250), 1),
        "diet_type": rng.choice(DIET_TYPES),
        "allergies": list(rng.choice(ALLERGY_COMBINATIONS)),
    }


def _build_random_submission_payload(rng, profile_template):
    age = rng.randint(16, 43)
    gender = profile_template["gender"]
    weight = profile_template["weight"]
    height = profile_template["height"]
    blood_sugar = profile_template["blood_sugar"]
    allergies = list(profile_template["allergies"])
    diet_type = profile_template["diet_type"]
    meals_per_day = rng.choice(MEALS_PER_DAY_OPTIONS)
    food_preference = rng.choice(FOOD_PREFERENCE_OPTIONS)

    payload = {
        "personal": {
            "age": age,
            "gender": gender,
            "weight": weight,
            "height": height,
        },
        "health": {
            "dietType": diet_type,
            "allergies": allergies,
            "blood_sugar": blood_sugar,
        },
        "preferences": {
            "mealsPerDay": meals_per_day,
            "foodPreference": food_preference,
        },
    }

    signature = (
        age,
        gender,
        round(weight, 2),
        float(height),
        diet_type,
        round(blood_sugar, 2),
        tuple(sorted(allergies)),
        meals_per_day,
        food_preference,
    )

    return payload, signature


def reseed_users():
    from app.models.associations import tbl_user_goals, tbl_user_roles
    from app.models.diet_rule import DietRulesTable
    from app.models.role import RoleTable
    from app.models.user import UserTable
    from app.models.user_result import UserResultsTable
    from app.services.dashboard_services import DashboardService

    rng = random.Random()
    email_domain = "gmail.com"

    deleted_users = 0
    role_created = False
    users_with_shortfall = []

    try:
        user_role = (
            RoleTable.query.filter(func.lower(RoleTable.name) == "user")
            .order_by(RoleTable.id.asc())
            .first()
        )
        if user_role is None:
            user_role = RoleTable(name="user", description="User")
            db.session.add(user_role)
            db.session.flush()
            role_created = True

        target_user_ids = [
            row[0]
            for row in db.session.execute(
                db.select(UserTable.id)
                .join(UserTable.roles)
                .filter(func.lower(RoleTable.name) == "user")
                .distinct()
            ).all()
        ]
        deleted_users = len(target_user_ids)

        if target_user_ids:
            # Use a direct connection transaction for FK-safe bulk cleanup.
            with db.engine.begin() as conn:
                conn.execute(
                    delete(UserResultsTable.__table__).where(
                        UserResultsTable.user_id.in_(target_user_ids)
                    )
                )
                conn.execute(
                    tbl_user_goals.delete().where(
                        tbl_user_goals.c.user_id.in_(target_user_ids)
                    )
                )
                conn.execute(
                    tbl_user_roles.delete().where(
                        tbl_user_roles.c.user_id.in_(target_user_ids)
                    )
                )
                conn.execute(
                    delete(UserTable.__table__).where(UserTable.id.in_(target_user_ids))
                )
            db.session.expire_all()

        existing_users = UserTable.query.all()
        used_usernames = {
            str(user.username or "").strip().lower()
            for user in existing_users
            if user.username
        }
        used_emails = {
            str(user.email or "").strip().lower() for user in existing_users if user.email
        }
        used_full_names = set()

        new_users = []
        for _ in range(30):
            full_name, gender = _generate_cambodian_name(rng, used_full_names)
            username, email = _make_unique_username_and_email(
                full_name=full_name,
                used_usernames=used_usernames,
                used_emails=used_emails,
                domain=email_domain,
            )

            user = UserTable(
                username=username,
                email=email,
                full_name=full_name,
                is_active=True,
            )
            user.set_password("123456")
            user.roles = [user_role]
            db.session.add(user)
            new_users.append({"user": user, "gender": gender})

        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    submissions_attempted = 0
    submissions_created = 0
    retries = 0
    failures = 0

    # Speed up heavy reseed runs by caching rule parsing/matching and bypassing
    # expensive food-group lookups while preserving submission payload structure.
    # while still calling DashboardService.save_user_dashboard_submission(..., persist=True).
    original_select_matching_rule = DashboardService._select_matching_rule
    original_get_rule_food_groups = DashboardService._get_rule_food_groups

    compiled_rules = []
    for rule in DietRulesTable.query.all():
        meta = DashboardService._parse_rule_meta(rule)
        conditions = meta.get("conditions") or []
        if not meta.get("active", True) or not conditions:
            continue
        compiled_rules.append((rule, meta, conditions))

    priority_rank = {"high": 3, "medium": 2, "low": 1}
    rule_match_cache = {}
    def _profile_key(profile):
        profile = profile or {}
        allergies = tuple(
            sorted(
                str(item).strip().lower()
                for item in (profile.get("allergies") or [])
                if str(item).strip()
            )
        )

        bmi_value = profile.get("bmi")
        blood_sugar_value = profile.get("blood_sugar")

        return (
            round(float(bmi_value), 2) if bmi_value is not None else None,
            str(profile.get("gender") or "").strip().lower(),
            str(profile.get("diet_type") or "").strip().lower(),
            allergies,
            (
                round(float(blood_sugar_value), 2)
                if blood_sugar_value is not None
                else None
            ),
        )

    def cached_select_matching_rule(profile):
        key = _profile_key(profile)
        if key in rule_match_cache:
            return rule_match_cache[key]

        matched = []
        for rule, meta, conditions in compiled_rules:
            if DashboardService._rule_matches_profile(conditions, profile):
                matched.append((rule, meta))

        if not matched:
            rule_match_cache[key] = None
            return None

        matched.sort(
            key=lambda item: (
                priority_rank.get(str(item[1].get("priority", "")).lower(), 0),
                item[0].created_at or datetime.min,
            ),
            reverse=True,
        )
        selected_rule, selected_meta = matched[0]
        result = {**selected_meta, "rule": selected_rule}
        rule_match_cache[key] = result
        return result

    def cached_get_rule_food_groups(rule_id, food_preference=None):
        # Food groups are not required for reseed analytics and this query path is
        # the primary runtime bottleneck on remote DBs.
        return []

    DashboardService._select_matching_rule = staticmethod(cached_select_matching_rule)
    DashboardService._get_rule_food_groups = staticmethod(cached_get_rule_food_groups)

    try:
        for item in new_users:
            user = item["user"]
            gender = item["gender"]
            profile_template = _build_profile_template(rng, gender)

            target_submission_count = rng.randint(10, 20)
            max_attempts = target_submission_count * 200
            seen_payload_signatures = set()
            seen_result_ids = set()

            for _ in range(max_attempts):
                if len(seen_result_ids) >= target_submission_count:
                    break

                payload, signature = _build_random_submission_payload(
                    rng, profile_template
                )
                if signature in seen_payload_signatures:
                    retries += 1
                    continue

                seen_payload_signatures.add(signature)
                submissions_attempted += 1

                try:
                    result = DashboardService.save_user_dashboard_submission(
                        user_id=user.id,
                        payload=payload,
                        persist=True,
                    )
                    result_id = result.get("result_id")
                    if result_id and result_id not in seen_result_ids:
                        seen_result_ids.add(result_id)
                        submissions_created += 1
                    else:
                        retries += 1
                except Exception:
                    db.session.rollback()
                    failures += 1
                    retries += 1

            if len(seen_result_ids) < target_submission_count:
                users_with_shortfall.append(
                    {
                        "user_id": user.id,
                        "username": user.username,
                        "target": target_submission_count,
                        "created": len(seen_result_ids),
                    }
                )
    finally:
        DashboardService._select_matching_rule = staticmethod(original_select_matching_rule)
        DashboardService._get_rule_food_groups = staticmethod(original_get_rule_food_groups)

    print("Reseed users completed.")
    print(f"Role created: {'yes' if role_created else 'no'}")
    print(f"Deleted user-role accounts: {deleted_users}")
    print(f"Inserted user-role accounts: {len(new_users)}")
    print(f"Submission attempts: {submissions_attempted}")
    print(f"Submissions created: {submissions_created}")
    print(f"Retries/skips: {retries}")
    print(f"Submission failures: {failures}")
    if users_with_shortfall:
        print("Users with submission shortfall:")
        for row in users_with_shortfall:
            print(
                f"  - id={row['user_id']} username={row['username']} "
                f"created={row['created']} target={row['target']}"
            )
    else:
        print("All users reached their target of 10-20 submissions.")


def main():
    if len(sys.argv) <= 1:
        restore_all()
        return

    action = (sys.argv[1] or "").strip().lower()
    if action in {"dump", "export"}:
        dump_all()
        return
    if action in {"restore", "import"}:
        restore_all()
        return
    if action in {"reseed-users", "reseed_users"}:
        reseed_users()
        return

    print("Usage:")
    print("  python seeds/seed.py dump")
    print("  python seeds/seed.py restore")
    print("  python seeds/seed.py reseed-users")


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        try:
            main()
        except SQLAlchemyError as exc:
            print("Database connection failed while running seeds.")
            print(
                "Check DATABASE_URL (or SUPABASE_DB_URL) or DB_HOST/DB_USER/DB_PASSWORD/DB_NAME in .env."
            )
            raise SystemExit(1) from exc
