"""Connection management for the local SQLite implementation."""

from __future__ import annotations

import os
import sqlite3
from contextlib import closing
from pathlib import Path
from threading import Lock

from seed_data import create_database, install_integrity_guards


ROOT = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("EXPOSURE_DB", ROOT / "instance" / "exposure.db"))
_GUARD_LOCK = Lock()
_GUARDED_DATABASES: set[str] = set()


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    database_key = str(DB_PATH.absolute())
    with _GUARD_LOCK:
        if not DB_PATH.exists():
            create_database(DB_PATH)
        db = sqlite3.connect(DB_PATH)
        db.row_factory = sqlite3.Row
        try:
            db.execute("PRAGMA foreign_keys = ON")
            if database_key not in _GUARDED_DATABASES:
                install_integrity_guards(db)
                _GUARDED_DATABASES.add(database_key)
        except Exception:
            db.close()
            raise
    return db


def connect_readonly() -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise FileNotFoundError("The database has not been initialized. Start the app first.")
    db = sqlite3.connect(f"{DB_PATH.resolve().as_uri()}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA query_only = ON")
    return db


def read_connection() -> closing:
    """Return a context manager that always closes a normal connection."""
    return closing(connect())


def readonly_connection() -> closing:
    """Return a context manager that always closes a read-only connection."""
    return closing(connect_readonly())
