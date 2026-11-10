"""JSON API routing between the browser UI and application services."""

from __future__ import annotations

import json
import re
import sqlite3
from typing import Any
from urllib.parse import parse_qs

import services


MAX_REQUEST_BYTES = 20_000


def _as_user(query: dict[str, list[str]]) -> str | None:
    values = query.get("as_user")
    return values[0] if values else None


def dispatch(method: str, path: str, query_string: str, body: bytes = b"") -> tuple[int, dict[str, Any]]:
    """Dispatch one API request and always return a JSON-safe response."""
    query = parse_qs(query_string, keep_blank_values=True)
    user_id = _as_user(query)
    try:
        if method == "GET" and path == "/api/session":
            return 200, services.get_session(user_id)
        if method == "GET" and path == "/api/borrowers":
            return 200, services.get_borrowers(user_id)
        match = re.fullmatch(r"/api/borrowers/([^/]+)", path)
        if method == "GET" and match:
            return 200, services.get_borrower_detail(user_id, match.group(1))
        if method == "GET" and path == "/api/database/catalog":
            return 200, services.get_database_catalog(user_id)
        if method == "POST" and path == "/api/database/query":
            if len(body) > MAX_REQUEST_BYTES:
                return 413, {"error": "The query request must not exceed 20 KB."}
            try:
                payload = json.loads(body.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError, RecursionError):
                return 400, {"error": "The query request must contain valid JSON."}
            return 200, services.run_database_query(user_id, payload)
        return 404, {"error": "API route not found."}
    except services.ServiceError as error:
        return error.status, {"error": str(error)}
    except (sqlite3.Error, FileNotFoundError) as error:
        return 500, {"error": f"The local database request failed: {error}"}
    except (TypeError, ValueError, KeyError, OverflowError):
        # Invalid request shapes should produce a controlled client error rather
        # than an unhandled exception or a dropped HTTP response.
        return 400, {"error": "The request contains invalid or unsupported values."}
