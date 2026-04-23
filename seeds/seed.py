import base64
import json
import sys
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

from sqlalchemy import MetaData, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.sql.sqltypes import Boolean, Date, DateTime, LargeBinary, Numeric


ROOT_DIR = Path(__file__).resolve().parents[1]
SEEDS_DIR = Path(__file__).resolve().parent
IGNORED_TABLES = {"alembic_version"}

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app import create_app  # noqa: E402
from extensions import db  # noqa: E402


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

    print("Usage:")
    print("  python seeds/seed.py dump")
    print("  python seeds/seed.py restore")


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
