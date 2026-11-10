"""SQLite-backed stored-procedure equivalents for the interview application.

SQLite does not support stored procedures. Each ``sp_*`` function below is the
local equivalent of a parameterized database procedure: it owns one database
operation and returns rows for the service/API layer. The API and UI do not
contain SQL.
"""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from typing import Any


def sp_list_users(db: sqlite3.Connection) -> list[sqlite3.Row]:
    return db.execute("""
        SELECT u.user_id, u.is_superuser,
               CASE WHEN u.is_superuser = 1 THEN 'Superuser'
                    ELSE lob.description || ' User' END AS display_name
        FROM users u
        JOIN line_of_business_domain lob
          ON lob.line_of_business_code = u.home_line_of_business_code
        ORDER BY CASE u.is_superuser WHEN 1 THEN 0 ELSE 1 END, display_name
    """).fetchall()


def sp_list_borrowers(db: sqlite3.Connection) -> list[sqlite3.Row]:
    return db.execute("""
        SELECT b.borrower_id, b.name, sector.description AS sector
        FROM borrowers b
        JOIN sector_domain sector USING (sector_code)
        ORDER BY sector.description, b.name
    """).fetchall()


def sp_get_borrower(db: sqlite3.Connection, borrower_id: int) -> sqlite3.Row | None:
    return db.execute("""
        SELECT b.borrower_id, b.name, sector.description AS sector
        FROM borrowers b
        JOIN sector_domain sector USING (sector_code)
        WHERE b.borrower_id = ?
    """, (borrower_id,)).fetchone()


def sp_get_account_teams(db: sqlite3.Connection, borrower_id: int | None = None) -> list[sqlite3.Row]:
    sql = """
        SELECT t.borrower_id, lob.description AS line_of_business,
               role.description AS role, t.person_name
        FROM account_teams t
        JOIN line_of_business_domain lob USING (line_of_business_code)
        JOIN account_team_role_domain role USING (role_code)
    """
    params: tuple[Any, ...] = ()
    if borrower_id is not None:
        sql += " WHERE t.borrower_id = ?"
        params = (borrower_id,)
    sql += " ORDER BY t.borrower_id, lob.description, role.description"
    return db.execute(sql, params).fetchall()


def sp_get_user_access(db: sqlite3.Connection, user_id: str, is_superuser: bool) -> list[str]:
    if is_superuser:
        rows = db.execute("""
            SELECT DISTINCT lob.description
            FROM facilities f JOIN line_of_business_domain lob USING (line_of_business_code)
            ORDER BY lob.description
        """).fetchall()
    else:
        rows = db.execute("""
            SELECT lob.description
            FROM user_lob_access a
            JOIN line_of_business_domain lob USING (line_of_business_code)
            WHERE a.user_id = ?
            ORDER BY lob.description
        """, (user_id,)).fetchall()
    return [row[0] for row in rows]


def sp_get_visible_facility_counts(db: sqlite3.Connection, user_id: str, is_superuser: bool) -> dict[int, int]:
    if is_superuser:
        rows = db.execute("""
            SELECT borrower_id, COUNT(*) AS facility_count
            FROM facilities GROUP BY borrower_id
        """).fetchall()
    else:
        rows = db.execute("""
            SELECT f.borrower_id, COUNT(*) AS facility_count
            FROM facilities f
            WHERE f.line_of_business_code IN (
                SELECT line_of_business_code FROM user_lob_access WHERE user_id = ?
            )
            GROUP BY f.borrower_id
        """, (user_id,)).fetchall()
    return {row["borrower_id"]: row["facility_count"] for row in rows}


def sp_get_borrower_facilities(
    db: sqlite3.Connection, borrower_id: int, user_id: str, is_superuser: bool
) -> list[sqlite3.Row]:
    return db.execute("""
        SELECT f.facility_id, lob.description AS line_of_business,
               ec.description AS exposure_class, es.description AS exposure_subclass,
               ft.description AS facility_type, f.status_code, st.description AS status,
               f.facility_description, f.commitment_start_date, f.maturity_date,
               f.currency_code AS currency, cd.description AS currency_description,
               f.committed_amount, f.uncommitted_amount, f.drawn_amount
        FROM facilities f
        JOIN line_of_business_domain lob USING (line_of_business_code)
        JOIN exposure_class_domain ec USING (exposure_class_code)
        JOIN exposure_subclass_domain es USING (exposure_subclass_code)
        JOIN facility_type_domain ft USING (facility_type_code)
        JOIN facility_status_domain st ON st.status_code = f.status_code
        JOIN currency_domain cd ON cd.currency_code = f.currency_code
        WHERE f.borrower_id = ?
          AND (? = 1 OR f.line_of_business_code IN (
              SELECT line_of_business_code FROM user_lob_access WHERE user_id = ?
          ))
        ORDER BY f.facility_id
    """, (borrower_id, int(is_superuser), user_id)).fetchall()


def sp_get_borrower_exposure(db: sqlite3.Connection, borrower_id: int | None = None) -> dict[int, dict[str, Any]]:
    """Return borrower totals and a grouped breakdown for the summary view."""
    sql = """
        SELECT f.borrower_id, ec.description AS exposure_class,
               es.description AS exposure_subclass, ft.description AS facility_type,
               COUNT(*) AS facility_count,
               SUM((f.committed_amount + f.drawn_amount) * x.to_cad) AS exposure_cad,
               SUM((f.committed_amount + f.drawn_amount) * x.to_usd) AS exposure_usd
        FROM facilities f
        JOIN fx_rates x ON x.currency_code = f.currency_code
        JOIN exposure_class_domain ec ON ec.exposure_class_code = f.exposure_class_code
        JOIN exposure_subclass_domain es ON es.exposure_subclass_code = f.exposure_subclass_code
        JOIN facility_type_domain ft ON ft.facility_type_code = f.facility_type_code
        WHERE f.status_code = 'ACTIVE'
          AND f.exposure_class_code = 'CREDIT'
    """
    params: tuple[Any, ...] = ()
    if borrower_id is not None:
        sql += " AND f.borrower_id = ?"
        params = (borrower_id,)
    sql += " GROUP BY f.borrower_id, ec.description, es.description, ft.description"

    result: dict[int, dict[str, Any]] = defaultdict(lambda: {
        "total_cad": 0.0, "total_usd": 0.0, "groups": defaultdict(lambda: {
            "cad": 0.0, "usd": 0.0, "facility_types": defaultdict(lambda: {"cad": 0.0, "usd": 0.0})
        })
    })
    for row in db.execute(sql, params):
        borrower = result[row["borrower_id"]]
        amount_cad = row["exposure_cad"] or 0
        amount_usd = row["exposure_usd"] or 0
        group_key = f'{row["exposure_class"]} · {row["exposure_subclass"]}'
        borrower["total_cad"] += amount_cad
        borrower["total_usd"] += amount_usd
        group = borrower["groups"][group_key]
        group["cad"] += amount_cad
        group["usd"] += amount_usd
        group["facility_types"][row["facility_type"]]["cad"] += amount_cad
        group["facility_types"][row["facility_type"]]["usd"] += amount_usd
    return dict(result)


def sp_get_borrower_utilization(
    db: sqlite3.Connection, borrower_id: int | None = None
) -> dict[int, dict[str, float | None]]:
    """Calculate utilization separately, on a CAD-equivalent basis."""
    sql = """
        SELECT f.borrower_id,
               SUM((f.committed_amount + f.uncommitted_amount) * x.to_cad) AS exposure_cad,
               SUM(f.drawn_amount * x.to_cad) AS drawn_cad
        FROM facilities f
        JOIN fx_rates x ON x.currency_code = f.currency_code
        WHERE f.status_code = 'ACTIVE'
    """
    params: tuple[Any, ...] = ()
    if borrower_id is not None:
        sql += " AND f.borrower_id = ?"
        params = (borrower_id,)
    sql += " GROUP BY f.borrower_id"
    result: dict[int, dict[str, float | None]] = {}
    for row in db.execute(sql, params):
        exposure = row["exposure_cad"] or 0.0
        drawn = row["drawn_cad"] or 0.0
        result[row["borrower_id"]] = {
            "exposure_cad": exposure,
            "drawn_cad": drawn,
            "utilization_pct": (drawn / exposure * 100) if exposure else None,
        }
    return result
