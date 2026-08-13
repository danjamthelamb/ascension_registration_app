from __future__ import annotations

import sqlite3
from pathlib import Path
import secrets
import string


PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "registration.sqlite"


def _connect() -> sqlite3.Connection:
    """
    Open a connection to the registration database.
    """
    DATA_DIR.mkdir(exist_ok=True)

    conn = sqlite3.connect(DB_PATH)

    # SQLite does not enforce foreign keys unless we turn them on.
    conn.execute("PRAGMA foreign_keys = ON;")

    return conn


def init_db() -> None:
    """
    Create the application's database tables if they do not already exist.
    """

    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS households (
                household_id INTEGER PRIMARY KEY AUTOINCREMENT,
                household_reference TEXT NOT NULL UNIQUE,

                parent_a_first_name TEXT NOT NULL,
                parent_a_last_name TEXT NOT NULL,
                parent_a_email TEXT NOT NULL,
                parent_a_phone TEXT NOT NULL,

                parent_b_first_name TEXT,
                parent_b_last_name TEXT,
                parent_b_email TEXT,
                parent_b_phone TEXT,

                address_line_1 TEXT NOT NULL,
                address_line_2 TEXT,
                city TEXT NOT NULL,
                state TEXT NOT NULL,
                zip_code TEXT NOT NULL,

                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS children (
                child_id INTEGER PRIMARY KEY AUTOINCREMENT,
                household_id INTEGER NOT NULL,

                first_name TEXT NOT NULL,
                middle_name TEXT,
                last_name TEXT NOT NULL,
                date_of_birth TEXT NOT NULL,
                grade TEXT NOT NULL,
                school TEXT NOT NULL,
                receiving_confirmation INTEGER NOT NULL DEFAULT 0,

                FOREIGN KEY (household_id)
                    REFERENCES households (household_id)
                    ON DELETE CASCADE
            );
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_children_household_id
            ON children (household_id);
            """
        )

def _generate_household_reference() -> str:
    """
    Generate a human-friendly public household reference.

    Example:
        ASC-K7M4P9
    """

    characters = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"

    while True:
        code = "".join(
            secrets.choice(characters)
            for _ in range(6)
        )

        household_reference = f"ASC-{code}"

        with _connect() as conn:
            existing = conn.execute(
                """
                SELECT 1
                FROM households
                WHERE household_reference = ?;
                """,
                (household_reference,),
            ).fetchone()

        if existing is None:
            return household_reference

def save_registration(
    household: dict,
    children: list[dict],
) -> tuple[int, str]:
    """
    Save one complete household registration and all of its children.

    Returns the new household_id and household_reference.
    """

    if not children:
        raise ValueError("At least one child must be added.")

    household_reference = _generate_household_reference()

    with _connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO households (
                household_reference,
                parent_a_first_name,
                parent_a_last_name,
                parent_a_email,
                parent_a_phone,

                parent_b_first_name,
                parent_b_last_name,
                parent_b_email,
                parent_b_phone,

                address_line_1,
                address_line_2,
                city,
                state,
                zip_code
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                household_reference,

                household["parent_a_first_name"],
                household["parent_a_last_name"],
                household["parent_a_email"],
                household["parent_a_phone"],

                household.get("parent_b_first_name", ""),
                household.get("parent_b_last_name", ""),
                household.get("parent_b_email", ""),
                household.get("parent_b_phone", ""),

                household["address_line_1"],
                household.get("address_line_2", ""),
                household["city"],
                household["state"],
                household["zip_code"],
            ),
        )

        household_id = cursor.lastrowid

        for child in children:
            date_of_birth = child["date_of_birth"]

            if hasattr(date_of_birth, "isoformat"):
                date_of_birth = date_of_birth.isoformat()

            conn.execute(
                """
                INSERT INTO children (
                    household_id,
                    first_name,
                    middle_name,
                    last_name,
                    date_of_birth,
                    grade,
                    school,
                    receiving_confirmation
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    household_id,
                    child["first_name"],
                    child.get("middle_name", ""),
                    child["last_name"],
                    date_of_birth,
                    child["grade"],
                    child["school"],
                    int(child.get("receiving_confirmation", False)),
                ),
            )

    return household_id, household_reference