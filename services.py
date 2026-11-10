"""Application services that compose stored procedures for the API layer."""

from __future__ import annotations

from typing import Any

from database import read_connection, readonly_connection
from database_utility import QueryError, catalog, run_sql, run_visual, supported_join_types
import stored_procedures as procedures


DEFAULT_USER = "superuser"


class ServiceError(ValueError):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def _viewer(db, user_id: str | None):
    users = procedures.sp_list_users(db)
    selected_id = user_id or DEFAULT_USER
    viewer = next((user for user in users if user["user_id"] == selected_id), None)
    if viewer is None:
        raise ServiceError("Choose a valid app role.", 400)
    return viewer, users


def _session(db, viewer, users) -> dict[str, Any]:
    return {
        "userId": viewer["user_id"],
        "displayName": viewer["display_name"],
        "isSuperuser": bool(viewer["is_superuser"]),
        "access": procedures.sp_get_user_access(db, viewer["user_id"], bool(viewer["is_superuser"])),
        "users": [{"userId": row["user_id"], "displayName": row["display_name"]} for row in users],
    }


def get_session(user_id: str | None) -> dict[str, Any]:
    with read_connection() as db:
        viewer, users = _viewer(db, user_id)
        return _session(db, viewer, users)


def _summary_json(summary: dict[str, Any] | None) -> dict[str, Any]:
    summary = summary or {"total_cad": 0.0, "total_usd": 0.0, "groups": {}}
    groups = {}
    for key, value in summary.get("groups", {}).items():
        groups[key] = {
            "cad": value["cad"],
            "usd": value["usd"],
            "facilityTypes": {
                name: {"cad": amounts["cad"], "usd": amounts["usd"]}
                for name, amounts in value["facility_types"].items()
            },
        }
    return {"totalCad": summary["total_cad"], "totalUsd": summary["total_usd"], "groups": groups}


def get_borrowers(user_id: str | None) -> dict[str, Any]:
    with read_connection() as db:
        viewer, users = _viewer(db, user_id)
        session = _session(db, viewer, users)
        summaries = procedures.sp_get_borrower_exposure(db)
        utilization = procedures.sp_get_borrower_utilization(db)
        visible_counts = procedures.sp_get_visible_facility_counts(
            db, viewer["user_id"], bool(viewer["is_superuser"])
        )
        teams: dict[int, list[dict[str, str]]] = {}
        for row in procedures.sp_get_account_teams(db):
            teams.setdefault(row["borrower_id"], []).append({
                "lineOfBusiness": row["line_of_business"],
                "role": row["role"],
                "name": row["person_name"],
            })
        borrowers = []
        for row in procedures.sp_list_borrowers(db):
            borrowers.append({
                "borrowerId": row["borrower_id"],
                "name": row["name"],
                "sector": row["sector"],
                "visibleFacilityCount": visible_counts.get(row["borrower_id"], 0),
                "summary": _summary_json(summaries.get(row["borrower_id"])),
                "utilizationPct": utilization.get(row["borrower_id"], {}).get("utilization_pct"),
                "teams": teams.get(row["borrower_id"], []),
            })
        return {"session": session, "borrowers": borrowers}


def get_borrower_detail(user_id: str | None, borrower_id: str) -> dict[str, Any]:
    try:
        borrower_key = int(borrower_id)
        if borrower_key <= 0:
            raise ValueError
    except (TypeError, ValueError):
        raise ServiceError("Borrower ID must be a positive integer.", 400) from None

    with read_connection() as db:
        viewer, users = _viewer(db, user_id)
        borrower = procedures.sp_get_borrower(db, borrower_key)
        if borrower is None:
            raise ServiceError("Borrower not found.", 404)
        summaries = procedures.sp_get_borrower_exposure(db, borrower_key)
        utilization = procedures.sp_get_borrower_utilization(db, borrower_key).get(
            borrower_key, {"utilization_pct": None, "drawn_cad": 0.0}
        )
        facilities = []
        for row in procedures.sp_get_borrower_facilities(
            db, borrower_key, viewer["user_id"], bool(viewer["is_superuser"])
        ):
            capacity = row["committed_amount"] + row["uncommitted_amount"]
            facility_pct = (
                row["drawn_amount"] / capacity * 100
                if row["status_code"] == "ACTIVE" and capacity else None
            )
            facilities.append({
                "facilityId": row["facility_id"],
                "lineOfBusiness": row["line_of_business"],
                "exposureClass": row["exposure_class"],
                "exposureSubclass": row["exposure_subclass"],
                "facilityType": row["facility_type"],
                "statusCode": row["status_code"],
                "status": row["status"],
                "description": row["facility_description"],
                "commitmentStartDate": row["commitment_start_date"],
                "maturityDate": row["maturity_date"],
                "currency": row["currency"],
                "currencyDescription": row["currency_description"],
                "committedAmount": row["committed_amount"],
                "uncommittedAmount": row["uncommitted_amount"],
                "drawnAmount": row["drawn_amount"],
                "utilizationPct": facility_pct,
            })
        teams = [
            {"lineOfBusiness": row["line_of_business"], "role": row["role"], "name": row["person_name"]}
            for row in procedures.sp_get_account_teams(db, borrower_key)
        ]
        return {
            "session": _session(db, viewer, users),
            "borrower": {
                "borrowerId": borrower["borrower_id"],
                "name": borrower["name"],
                "sector": borrower["sector"],
                "summary": _summary_json(summaries.get(borrower_key)),
                "drawnCad": utilization["drawn_cad"],
                "utilizationPct": utilization["utilization_pct"],
                "facilities": facilities,
                "teams": teams,
            },
        }


def get_database_catalog(user_id: str | None) -> dict[str, Any]:
    get_session(user_id)
    with readonly_connection() as db:
        return {"tables": catalog(db), "joinTypes": supported_join_types()}


def run_database_query(user_id: str | None, payload: Any) -> dict[str, Any]:
    get_session(user_id)
    if not isinstance(payload, dict):
        raise ServiceError("The query request must be an object.")
    try:
        with readonly_connection() as db:
            if payload.get("mode") == "visual":
                return run_visual(db, payload.get("spec", {}))
            if payload.get("mode") == "sql":
                return run_sql(db, payload.get("sql", ""))
            raise ServiceError("Choose SQL or visual query mode.")
    except QueryError as error:
        raise ServiceError(str(error), 400) from error
