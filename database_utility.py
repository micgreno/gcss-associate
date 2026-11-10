"""Read-only database browser and visual query builder for the local exercise app."""

from __future__ import annotations

import re
import sqlite3
from typing import Any


MAX_ROWS = 250
MAX_SQL_LENGTH = 10_000
MAX_STEPS = 2_000_000
BLOCKED_ACTIONS = {
    sqlite3.SQLITE_INSERT, sqlite3.SQLITE_UPDATE, sqlite3.SQLITE_DELETE,
    sqlite3.SQLITE_CREATE_INDEX, sqlite3.SQLITE_CREATE_TABLE,
    sqlite3.SQLITE_CREATE_TEMP_INDEX, sqlite3.SQLITE_CREATE_TEMP_TABLE,
    sqlite3.SQLITE_CREATE_TEMP_TRIGGER, sqlite3.SQLITE_CREATE_TEMP_VIEW,
    sqlite3.SQLITE_CREATE_TRIGGER, sqlite3.SQLITE_CREATE_VIEW,
    sqlite3.SQLITE_DROP_INDEX, sqlite3.SQLITE_DROP_TABLE,
    sqlite3.SQLITE_DROP_TEMP_INDEX, sqlite3.SQLITE_DROP_TEMP_TABLE,
    sqlite3.SQLITE_DROP_TEMP_TRIGGER, sqlite3.SQLITE_DROP_TEMP_VIEW,
    sqlite3.SQLITE_DROP_TRIGGER, sqlite3.SQLITE_DROP_VIEW,
    sqlite3.SQLITE_ALTER_TABLE, sqlite3.SQLITE_ATTACH, sqlite3.SQLITE_DETACH,
    sqlite3.SQLITE_CREATE_VTABLE, sqlite3.SQLITE_DROP_VTABLE,
    sqlite3.SQLITE_TRANSACTION, sqlite3.SQLITE_SAVEPOINT, sqlite3.SQLITE_PRAGMA,
}


class QueryError(ValueError):
    """A user-facing query or visual builder validation error."""


def supported_join_types() -> list[str]:
    types = ["INNER JOIN", "LEFT OUTER JOIN"]
    if sqlite3.sqlite_version_info >= (3, 39, 0):
        types.extend(["RIGHT OUTER JOIN", "FULL OUTER JOIN"])
    return types


def quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def catalog(db: sqlite3.Connection) -> list[dict[str, Any]]:
    tables = db.execute("""
        SELECT name FROM sqlite_master
        WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
        ORDER BY name
    """).fetchall()
    result = []
    for row in tables:
        name = row[0]
        columns = [dict(column) for column in db.execute(f"PRAGMA table_info({quote_identifier(name)})")]
        foreign_keys = [dict(fk) for fk in db.execute(f"PRAGMA foreign_key_list({quote_identifier(name)})")]
        result.append({"name": name, "columns": columns, "foreignKeys": foreign_keys})
    return result


def _authorizer(action: int, arg1: str | None, arg2: str | None, db_name: str | None, trigger: str | None) -> int:
    if action in BLOCKED_ACTIONS:
        return sqlite3.SQLITE_DENY
    if action == sqlite3.SQLITE_FUNCTION and (arg2 or arg1 or "").lower() in {"load_extension", "writefile", "readfile"}:
        return sqlite3.SQLITE_DENY
    return sqlite3.SQLITE_OK


def _run(db: sqlite3.Connection, sql: str) -> dict[str, Any]:
    if not isinstance(sql, str):
        raise QueryError("Enter a SQL SELECT statement.")
    sql = sql.strip()
    if not sql or len(sql) > MAX_SQL_LENGTH:
        raise QueryError(f"Enter a query under {MAX_SQL_LENGTH:,} characters.")
    if not re.match(r"^(SELECT|WITH)\b", sql, flags=re.IGNORECASE):
        raise QueryError("Only SELECT queries are allowed.")
    # sqlite3.execute() rejects multiple statements while allowing a semicolon
    # inside a quoted value or SQL comment.
    sql = sql.rstrip().removesuffix(";")
    db.set_authorizer(_authorizer)
    remaining_steps = MAX_STEPS

    def progress() -> int:
        nonlocal remaining_steps
        remaining_steps -= 10_000
        return int(remaining_steps <= 0)

    db.set_progress_handler(progress, 10_000)
    try:
        cursor = db.execute(sql)
        columns = [item[0] for item in cursor.description or []]
        if not columns:
            raise QueryError("The query did not return a result set. Use a SELECT query.")
        fetched = cursor.fetchmany(MAX_ROWS + 1)
        truncated = len(fetched) > MAX_ROWS
        rows = [[value for value in row] for row in fetched[:MAX_ROWS]]
        return {"columns": columns, "rows": rows, "truncated": truncated, "rowLimit": MAX_ROWS}
    except sqlite3.Error as error:
        message = str(error)
        if "not authorized" in message.lower():
            raise QueryError("This read-only utility allows SELECT queries only.") from error
        raise QueryError(message) from error
    finally:
        db.set_progress_handler(None, 0)
        db.set_authorizer(None)
def run_sql(db: sqlite3.Connection, sql: str) -> dict[str, Any]:
    return _run(db, sql)


def _schema_map(db: sqlite3.Connection) -> dict[str, dict[str, Any]]:
    return {table["name"]: table for table in catalog(db)}


def build_visual_sql(db: sqlite3.Connection, spec: dict[str, Any]) -> tuple[str, list[Any]]:
    if not isinstance(spec, dict):
        raise QueryError("The visual query settings are invalid.")
    schema = _schema_map(db)
    selected_tables = spec.get("tables", [])
    if not isinstance(selected_tables, list) or not selected_tables or not all(isinstance(table, str) for table in selected_tables):
        raise QueryError("Drag or add at least one table to the query canvas.")
    if len(selected_tables) > 8 or len(set(selected_tables)) != len(selected_tables):
        raise QueryError("Choose between one and eight distinct tables.")
    for table in selected_tables:
        if table not in schema:
            raise QueryError("The query includes an unknown table.")

    selections = spec.get("columns", [])
    if not isinstance(selections, list):
        raise QueryError("Choose columns from the tables on the canvas.")
    valid_fields = {
        (table, column["name"])
        for table in selected_tables
        for column in schema[table]["columns"]
    }
    if not all(isinstance(field, dict) for field in selections):
        raise QueryError("Each selected column must identify a table and column name.")
    selections = [(field.get("table"), field.get("column")) for field in selections]
    if any(not isinstance(table, str) or not isinstance(column, str) for table, column in selections):
        raise QueryError("Each selected column must identify a table and column name.")
    selections = list(dict.fromkeys(selections))
    if not selections or any(field not in valid_fields for field in selections):
        raise QueryError("Select at least one valid column from the tables on the canvas.")

    join_specs = spec.get("joins", [])
    if not isinstance(join_specs, list) or len(join_specs) != len(selected_tables) - 1:
        raise QueryError("Choose the join type and both join columns for every additional table.")
    joins: list[str] = []
    join_types = set(supported_join_types())
    for index, table in enumerate(selected_tables[1:]):
        join = join_specs[index]
        if not isinstance(join, dict) or join.get("table") != table:
            raise QueryError("Configure each join in the same order as the tables on the canvas.")
        join_type = join.get("joinType")
        left_table = join.get("leftTable")
        left_column = join.get("leftColumn")
        right_column = join.get("rightColumn")
        if not isinstance(join_type, str) or join_type not in join_types:
            raise QueryError("Choose a join type supported by this Python/SQLite installation.")
        if not isinstance(left_table, str) or left_table not in selected_tables[:index + 1]:
            raise QueryError("Choose a join column from a table already on the canvas.")
        available_left = {column["name"] for column in schema[left_table]["columns"]}
        available_right = {column["name"] for column in schema[table]["columns"]}
        if (not isinstance(left_column, str) or not isinstance(right_column, str)
                or left_column not in available_left or right_column not in available_right):
            raise QueryError("Choose valid columns on both sides of the join.")
        join_clause = (
            f"{quote_identifier(left_table)}.{quote_identifier(left_column)} = "
            f"{quote_identifier(table)}.{quote_identifier(right_column)}"
        )
        joins.append(f"{join_type} {quote_identifier(table)} ON {join_clause}")

    operators = {"=": "=", "!=": "!=", ">": ">", ">=": ">=", "<": "<", "<=": "<=", "contains": "LIKE", "is empty": "IS NULL", "is not empty": "IS NOT NULL"}
    conditions = []
    values: list[Any] = []
    filters = spec.get("filters", [])
    if not isinstance(filters, list) or len(filters) > 20:
        raise QueryError("Use no more than 20 visual filters.")
    for rule in filters:
        if not isinstance(rule, dict):
            raise QueryError("Each filter must identify a column and operation.")
        field = (rule.get("table"), rule.get("column"))
        op = rule.get("operator")
        if (not isinstance(field[0], str) or not isinstance(field[1], str)
                or field not in valid_fields or not isinstance(op, str) or op not in operators):
            raise QueryError("A filter refers to an unknown column or operator.")
        reference = f"{quote_identifier(field[0])}.{quote_identifier(field[1])}"
        if op in {"is empty", "is not empty"}:
            conditions.append(f"{reference} {operators[op]}")
        else:
            conditions.append(f"{reference} {operators[op]} ?")
            value = rule.get("value", "")
            if not isinstance(value, (str, int, float, type(None))):
                raise QueryError("Filter values must be text or numbers.")
            values.append(f"%{value}%" if op == "contains" else value)

    order = []
    order_specs = spec.get("order", [])
    if not isinstance(order_specs, list) or len(order_specs) > 8:
        raise QueryError("Choose no more than eight sort columns.")
    for item in order_specs:
        if not isinstance(item, dict):
            raise QueryError("Each sort rule must identify a selected column.")
        field = (item.get("table"), item.get("column"))
        if not isinstance(field[0], str) or not isinstance(field[1], str):
            raise QueryError("Each sort rule must identify a selected column.")
        if field not in valid_fields:
            raise QueryError("Sort columns must belong to a table on the canvas.")
        direction = item.get("direction", "ASC")
        if not isinstance(direction, str) or direction.upper() not in {"ASC", "DESC"}:
            raise QueryError("Sort direction must be ASC or DESC.")
        order.append(f"{quote_identifier(field[0])}.{quote_identifier(field[1])} {direction.upper()}")

    select_sql = ", ".join(f"{quote_identifier(table)}.{quote_identifier(column)}" for table, column in selections)
    sql = f"SELECT {select_sql} FROM {quote_identifier(selected_tables[0])} " + " ".join(joins)
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    if order:
        sql += " ORDER BY " + ", ".join(order)
    sql += f" LIMIT {MAX_ROWS + 1}"
    return sql, values


def run_visual(db: sqlite3.Connection, spec: dict[str, Any]) -> dict[str, Any]:
    sql, values = build_visual_sql(db, spec)
    db.set_authorizer(_authorizer)
    remaining_steps = MAX_STEPS

    def progress() -> int:
        nonlocal remaining_steps
        remaining_steps -= 10_000
        return int(remaining_steps <= 0)

    db.set_progress_handler(progress, 10_000)
    try:
        cursor = db.execute(sql, values)
        columns = [item[0] for item in cursor.description or []]
        rows = [[value for value in row] for row in cursor.fetchmany(MAX_ROWS + 1)]
        return {"columns": columns, "rows": rows[:MAX_ROWS], "truncated": len(rows) > MAX_ROWS, "rowLimit": MAX_ROWS, "generatedSql": sql}
    except (sqlite3.Error, TypeError, ValueError) as error:
        raise QueryError(str(error)) from error
    finally:
        db.set_progress_handler(None, 0)
        db.set_authorizer(None)
