# /// script
# dependencies = ["SQLAlchemy<2", "clickhouse-sqlalchemy>=0.2.9,<0.3"]
# ///
"""Regenerate ClickHouse ORM mappings from system.columns.

Run from the repository root: python bin/generate_clickhouse_models.py
The schema is externally managed; review the generated diff before committing.
"""

import ast
import keyword
import os
import sys
from pathlib import Path

from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from open_bus_stride_db.clickhouse import get_session

TYPES = {
    "String": "String",
    "DateTime": "DateTime",
    "Date": "Date",
    "Int64": "BigInteger",
    "Int32": "Integer",
    "UInt8": "Integer",
    "Float32": "Float",
}

# Migration bookkeeping is managed by the upstream ClickHouse project.
EXCLUDED_TABLES = frozenset({"goose_db_version"})
OUTPUT = Path(__file__).resolve().parents[1] / "open_bus_stride_db/clickhouse/models.py"


def existing_tables(path):
    if not path.exists():
        return set()
    nodes = ast.parse(path.read_text(encoding="utf-8")).body
    names = set()
    for node in nodes:
        if isinstance(node, ast.ClassDef):
            for item in node.body:
                if (
                    isinstance(item, ast.Assign)
                    and any(
                        isinstance(t, ast.Name) and t.id == "__tablename__"
                        for t in item.targets
                    )
                    and isinstance(item.value, ast.Constant)
                    and isinstance(item.value.value, str)
                ):
                    names.add(item.value.value)
        elif isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            call = node.value
            if (
                isinstance(call.func, ast.Name)
                and call.func.id == "Table"
                and call.args
                and isinstance(call.args[0], ast.Constant)
                and isinstance(call.args[0].value, str)
            ):
                names.add(call.args[0].value)
    return names


def generate():
    database = os.getenv("CLICKHOUSE_DATABASE", "default")
    query = text(
        "SELECT table, name, type, is_in_primary_key FROM system.columns "
        "WHERE database = :database ORDER BY table, position"
    )
    with get_session() as session:
        rows = session.execute(query, {"database": database}).mappings().all()
    tables = {}
    for row in rows:
        if row["table"] in EXCLUDED_TABLES:
            continue
        tables.setdefault(row["table"], []).append(row)
    if not tables:
        raise ValueError("No tables or views found in ClickHouse database: " + database)
    lines = [
        '"""Generated ClickHouse ORM mappings; run bin/generate_clickhouse_models.py."""',
        "",
        "from sqlalchemy import BigInteger, Column, Date, DateTime, Float, Integer, String, Table",
        "from sqlalchemy.orm import declarative_base",
        "",
        "Base = declarative_base()",
        "",
    ]
    for table, columns in tables.items():
        if not table.isidentifier() or keyword.iskeyword(table):
            raise ValueError("Unsupported table name: " + table)
        has_key = any(row["is_in_primary_key"] for row in columns)
        if has_key:
            class_name = "".join(part.title() for part in table.split("_"))
            lines.extend(
                [
                    "",
                    f"class {class_name}(Base):",
                    f"    __tablename__ = {table!r}",
                ]
            )
        else:
            lines.extend(["", f"{table} = Table({table!r}, Base.metadata,"])
        for row in columns:
            name, db_type = row["name"], row["type"]
            if (
                not name.isidentifier()
                or keyword.iskeyword(name)
                or (name.startswith("__") and name.endswith("__"))
                or (has_key and name in {"metadata", "registry"})
            ):
                raise ValueError("Unsupported column name: " + name)
            nullable = db_type.startswith("Nullable(") and db_type.endswith(")")
            base_type = db_type[9:-1] if nullable else db_type
            if base_type not in TYPES:
                raise ValueError("Unsupported ClickHouse type: " + db_type)
            constraint = (
                "primary_key=True"
                if row["is_in_primary_key"]
                else f"nullable={nullable}"
            )
            options = f"{TYPES[base_type]}, {constraint}"
            if has_key:
                lines.append(f"    {name} = Column({options})")
            else:
                lines.append(f"    Column({name!r}, {options}),")
        if not has_key:
            lines.append(")")
        lines.append("")
    missing = existing_tables(OUTPUT) - tables.keys()
    if missing:
        raise ValueError(
            "Existing tables or views missing from ClickHouse database: "
            + ", ".join(sorted(missing))
        )
    OUTPUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Updated {OUTPUT}")


if __name__ == "__main__":
    generate()
