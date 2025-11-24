"""Utility script to demonstrate basic write and database capabilities.

The script performs the following steps:
1. Writes a `Hello, world!` message to a text file.
2. Creates (or opens) a SQLite database.
3. Creates a demonstration table inside the database.
4. Inserts a row into the table.
5. Updates the previously inserted row.
6. Prints the results of each operation so they can be reviewed by the caller.

This script does not require network access and therefore can be executed in
restricted environments.  It is intentionally self‑contained so it can be used
as a quick verification tool during deployments.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Dict


BASE_DIR = Path(__file__).resolve().parent.parent
ARTIFACTS_DIR = BASE_DIR / "integration_artifacts"
HELLO_WORLD_FILE = ARTIFACTS_DIR / "hello_world.txt"
SQLITE_DB = ARTIFACTS_DIR / "integration_proof.sqlite3"
TABLE_NAME = "integration_proof"


def ensure_artifacts_directory() -> None:
    """Create the artefacts directory if it does not already exist."""
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)


def write_hello_world() -> Path:
    """Write a Hello World message to a text file and return the path."""
    ensure_artifacts_directory()
    HELLO_WORLD_FILE.write_text("Hello, world!\n", encoding="utf-8")
    return HELLO_WORLD_FILE


def run_sqlite_demo() -> Dict[str, Any]:
    """Create a SQLite database, insert and update a record."""
    ensure_artifacts_directory()

    conn = sqlite3.connect(SQLITE_DB)
    try:
        cursor = conn.cursor()

        cursor.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message TEXT NOT NULL,
                updated INTEGER NOT NULL DEFAULT 0
            )
            """
        )

        cursor.execute(
            f"INSERT INTO {TABLE_NAME} (message, updated) VALUES (?, ?)",
            ("initial message", 0),
        )
        row_id = cursor.lastrowid

        cursor.execute(
            f"UPDATE {TABLE_NAME} SET message = ?, updated = 1 WHERE id = ?",
            ("Hello from SQLite!", row_id),
        )

        cursor.execute(f"SELECT id, message, updated FROM {TABLE_NAME} WHERE id = ?", (row_id,))
        row = cursor.fetchone()

        conn.commit()

        return {
            "database_path": str(SQLITE_DB),
            "table": TABLE_NAME,
            "row": {"id": row[0], "message": row[1], "updated": row[2]} if row else None,
        }
    finally:
        conn.close()


def main() -> None:
    hello_path = write_hello_world()
    sqlite_results = run_sqlite_demo()

    print("Hello world written to:", hello_path)
    print("Database operations summary:")
    print(f"  Database file: {sqlite_results['database_path']}")
    print(f"  Table name   : {sqlite_results['table']}")
    print(f"  Row snapshot : {sqlite_results['row']}")


if __name__ == "__main__":
    main()
