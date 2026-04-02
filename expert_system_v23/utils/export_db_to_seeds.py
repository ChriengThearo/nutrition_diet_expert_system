import argparse
import base64
import json
import os
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

import pymysql
from dotenv import load_dotenv


def json_safe(value):
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, timedelta):
        return value.total_seconds()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (bytes, bytearray)):
        return base64.b64encode(value).decode("ascii")
    return str(value)


def normalize_row(row):
    return {key: json_safe(value) for key, value in row.items()}


def main():
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    load_dotenv(dotenv_path=os.path.join(root_dir, ".env"))

    parser = argparse.ArgumentParser(
        description="Export all MySQL tables to JSON files."
    )
    parser.add_argument(
        "--output",
        default=os.path.join(root_dir, "seeds"),
        help="Output directory for JSON files",
    )
    args = parser.parse_args()

    db_host = os.getenv("DB_HOST", "localhost")
    db_user = os.getenv("DB_USER", "root")
    db_password = os.getenv("DB_PASSWORD", "mysql")
    db_name = os.getenv("DB_NAME", "expert_system_test1")
    db_port = int(os.getenv("DB_PORT", "3306"))

    output_dir = os.path.abspath(args.output)
    os.makedirs(output_dir, exist_ok=True)

    connection = pymysql.connect(
        host=db_host,
        user=db_user,
        password=db_password,
        database=db_name,
        port=db_port,
        cursorclass=pymysql.cursors.DictCursor,
    )

    metadata = {
        "database": db_name,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "tables": [],
    }

    try:
        with connection.cursor() as cursor:
            cursor.execute("SHOW TABLES")
            table_rows = cursor.fetchall()
            table_names = [list(row.values())[0] for row in table_rows]

            for table in table_names:
                cursor.execute(f"SELECT * FROM `{table}`")
                rows = cursor.fetchall()
                normalized = [normalize_row(row) for row in rows]

                output_path = os.path.join(output_dir, f"{table}.json")
                with open(output_path, "w", encoding="utf-8") as handle:
                    json.dump(normalized, handle, indent=2, ensure_ascii=True)

                metadata["tables"].append(
                    {"name": table, "rows": len(normalized), "file": output_path}
                )
                print(f"Exported {table}: {len(normalized)} rows")
    finally:
        connection.close()

    meta_path = os.path.join(output_dir, "_meta.json")
    with open(meta_path, "w", encoding="utf-8") as handle:
        json.dump(metadata, handle, indent=2, ensure_ascii=True)
    print(f"Wrote metadata to {meta_path}")


if __name__ == "__main__":
    main()
