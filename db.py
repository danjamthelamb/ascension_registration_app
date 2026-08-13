from __future__ import annotations

import hashlib
import secrets
import sqlite3
from datetime import date, datetime, timedelta, timezone
from pathlib import Path


# ---------------------------------------------------------
# Database setup
# ---------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "registration.sqlite"


# ---------------------------------------------------------
# Verification settings
# ---------------------------------------------------------

VERIFICATION_CODE_DIGITS = 6
VERIFICATION_CODE_TTL_MINUTES = 10
VERIFICATION_MAX_ATTEMPTS = 5


def _connect() -> sqlite3.Connection:
    """
    Open a connection to the registration database.
    """

    DATA_DIR.mkdir(exist_ok=True)

    conn = sqlite3.connect(DB_PATH)

    # SQLite does not enforce foreign keys unless enabled.
    conn.execute("PRAGMA foreign_keys = ON;")

    return conn


# ---------------------------------------------------------
# Initialize database
# ---------------------------------------------------------

def init_db() -> None:
    """
    Create the application's database tables if they
    do not already exist.
    """

    with _connect() as conn:

        # -------------------------------------------------
        # Households
        # -------------------------------------------------

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

        # -------------------------------------------------
        # Children
        # -------------------------------------------------

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

        # -------------------------------------------------
        # Email verification codes
        # -------------------------------------------------

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS verification_codes (
                verification_id INTEGER PRIMARY KEY AUTOINCREMENT,
                household_id INTEGER NOT NULL,

                code_hash TEXT NOT NULL,
                salt TEXT NOT NULL,

                attempt_count INTEGER NOT NULL DEFAULT 0,
                max_attempts INTEGER NOT NULL DEFAULT 5,

                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                used_at TEXT,

                FOREIGN KEY (household_id)
                    REFERENCES households (household_id)
                    ON DELETE CASCADE
            );
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_verification_household_id
            ON verification_codes (household_id);
            """
        )


# ---------------------------------------------------------
# Household reference generator
# ---------------------------------------------------------

def _generate_household_reference() -> str:
    """
    Generate a human-friendly public household reference.

    Example:
        ASC-K7M4P9
    """

    # Avoid ambiguous characters:
    # I, O, 0, 1
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


# ---------------------------------------------------------
# Verification helpers
# ---------------------------------------------------------

def _hash_verification_code(
    code: str,
    salt: str,
) -> str:
    """
    Hash a verification code with a unique salt.

    The plaintext verification code is never stored
    in the database.
    """

    value = f"{salt}:{code}".encode("utf-8")

    return hashlib.sha256(value).hexdigest()


def _generate_verification_code() -> str:
    """
    Generate a zero-padded numeric verification code.

    Example:
        042817
    """

    upper_limit = 10 ** VERIFICATION_CODE_DIGITS

    number = secrets.randbelow(upper_limit)

    return str(number).zfill(
        VERIFICATION_CODE_DIGITS
    )


# ---------------------------------------------------------
# Create email verification code
# ---------------------------------------------------------

def create_household_verification(
    household_reference: str,
) -> dict | None:
    """
    Create a new verification code for an existing household.

    Returns information needed by the email layer:

        {
            "household_reference": "ASC-ABC123",
            "email": "parent@example.com",
            "code": "482913",
            "expires_minutes": 10
        }

    Returns None if the Household ID does not exist.

    The plaintext code is returned so the application
    can email it, but it is NOT stored in SQLite.
    """

    household_reference = (
        household_reference
        .strip()
        .upper()
    )

    with _connect() as conn:

        household = conn.execute(
            """
            SELECT
                household_id,
                household_reference,
                parent_a_email
            FROM households
            WHERE household_reference = ?;
            """,
            (household_reference,),
        ).fetchone()

        if household is None:
            return None

        household_id = household[0]
        stored_reference = household[1]
        email = household[2]

        # Generate the new one-time code.
        code = _generate_verification_code()

        # Unique salt for this verification request.
        salt = secrets.token_hex(16)

        code_hash = _hash_verification_code(
            code,
            salt,
        )

        now = datetime.now(timezone.utc)

        expires_at = (
            now
            + timedelta(
                minutes=VERIFICATION_CODE_TTL_MINUTES
            )
        )

        now_text = now.isoformat()
        expires_text = expires_at.isoformat()

        # Invalidate any previous unused codes.
        #
        # If the parent clicks "resend code", only the
        # newest code should remain valid.
        conn.execute(
            """
            UPDATE verification_codes
            SET used_at = ?
            WHERE household_id = ?
            AND used_at IS NULL;
            """,
            (
                now_text,
                household_id,
            ),
        )

        conn.execute(
            """
            INSERT INTO verification_codes (
                household_id,
                code_hash,
                salt,
                attempt_count,
                max_attempts,
                created_at,
                expires_at,
                used_at
            )
            VALUES (?, ?, ?, 0, ?, ?, ?, NULL);
            """,
            (
                household_id,
                code_hash,
                salt,
                VERIFICATION_MAX_ATTEMPTS,
                now_text,
                expires_text,
            ),
        )

    return {
        "household_reference": stored_reference,
        "email": email,
        "code": code,
        "expires_minutes":
            VERIFICATION_CODE_TTL_MINUTES,
    }


# ---------------------------------------------------------
# Verify email code
# ---------------------------------------------------------

def verify_household_code(
    household_reference: str,
    code: str,
) -> tuple[bool, str]:
    """
    Verify a one-time email code.

    Returns:

        (True, "verified")

    or:

        (False, "invalid")
        (False, "expired")
        (False, "locked")
        (False, "no_active_code")
        (False, "household_not_found")
    """

    household_reference = (
        household_reference
        .strip()
        .upper()
    )

    code = code.strip()

    now = datetime.now(timezone.utc)
    now_text = now.isoformat()

    with _connect() as conn:

        household = conn.execute(
            """
            SELECT household_id
            FROM households
            WHERE household_reference = ?;
            """,
            (household_reference,),
        ).fetchone()

        if household is None:
            return False, "household_not_found"

        household_id = household[0]

        verification = conn.execute(
            """
            SELECT
                verification_id,
                code_hash,
                salt,
                attempt_count,
                max_attempts,
                expires_at
            FROM verification_codes
            WHERE household_id = ?
            AND used_at IS NULL
            ORDER BY verification_id DESC
            LIMIT 1;
            """,
            (household_id,),
        ).fetchone()

        if verification is None:
            return False, "no_active_code"

        verification_id = verification[0]
        stored_hash = verification[1]
        salt = verification[2]
        attempt_count = verification[3]
        max_attempts = verification[4]
        expires_at_text = verification[5]

        # ---------------------------------------------
        # Check expiration
        # ---------------------------------------------

        expires_at = datetime.fromisoformat(
            expires_at_text
        )

        if now >= expires_at:

            conn.execute(
                """
                UPDATE verification_codes
                SET used_at = ?
                WHERE verification_id = ?;
                """,
                (
                    now_text,
                    verification_id,
                ),
            )

            return False, "expired"

        # ---------------------------------------------
        # Check attempt limit
        # ---------------------------------------------

        if attempt_count >= max_attempts:
            return False, "locked"

        # ---------------------------------------------
        # Compare submitted code
        # ---------------------------------------------

        submitted_hash = _hash_verification_code(
            code,
            salt,
        )

        code_matches = secrets.compare_digest(
            stored_hash,
            submitted_hash,
        )

        if code_matches:

            # Mark the code used immediately.
            #
            # The same code cannot be used twice.
            conn.execute(
                """
                UPDATE verification_codes
                SET used_at = ?
                WHERE verification_id = ?;
                """,
                (
                    now_text,
                    verification_id,
                ),
            )

            return True, "verified"

        # ---------------------------------------------
        # Incorrect code
        # ---------------------------------------------

        new_attempt_count = attempt_count + 1

        if new_attempt_count >= max_attempts:

            # Lock/invalidate after the final attempt.
            conn.execute(
                """
                UPDATE verification_codes
                SET
                    attempt_count = ?,
                    used_at = ?
                WHERE verification_id = ?;
                """,
                (
                    new_attempt_count,
                    now_text,
                    verification_id,
                ),
            )

            return False, "locked"

        conn.execute(
            """
            UPDATE verification_codes
            SET attempt_count = ?
            WHERE verification_id = ?;
            """,
            (
                new_attempt_count,
                verification_id,
            ),
        )

        return False, "invalid"


# ---------------------------------------------------------
# Save new registration
# ---------------------------------------------------------

def save_registration(
    household: dict,
    children: list[dict],
) -> tuple[int, str]:
    """
    Save one complete new household registration
    and all of its children.

    Returns:
        household_id
        household_reference
    """

    if not children:
        raise ValueError(
            "At least one child must be added."
        )

    household_reference = (
        _generate_household_reference()
    )

    with _connect() as conn:

        # ---------------------------------------------
        # Insert household
        # ---------------------------------------------

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
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?
            );
            """,
            (
                household_reference,

                household["parent_a_first_name"],
                household["parent_a_last_name"],
                household["parent_a_email"],
                household["parent_a_phone"],

                household.get(
                    "parent_b_first_name",
                    "",
                ),
                household.get(
                    "parent_b_last_name",
                    "",
                ),
                household.get(
                    "parent_b_email",
                    "",
                ),
                household.get(
                    "parent_b_phone",
                    "",
                ),

                household["address_line_1"],
                household.get(
                    "address_line_2",
                    "",
                ),
                household["city"],
                household["state"],
                household["zip_code"],
            ),
        )

        household_id = cursor.lastrowid

        # ---------------------------------------------
        # Insert children
        # ---------------------------------------------

        for child in children:

            date_of_birth = child["date_of_birth"]

            if hasattr(date_of_birth, "isoformat"):
                date_of_birth = (
                    date_of_birth.isoformat()
                )

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
                    child.get(
                        "middle_name",
                        "",
                    ),
                    child["last_name"],
                    date_of_birth,
                    child["grade"],
                    child["school"],
                    int(
                        child.get(
                            "receiving_confirmation",
                            False,
                        )
                    ),
                ),
            )

    return household_id, household_reference


# ---------------------------------------------------------
# Load existing registration
# ---------------------------------------------------------

def get_registration_by_reference(
    household_reference: str,
) -> tuple[dict, list[dict]] | None:
    """
    Load a household and all of its children using
    the public Household ID.

    This function should only be called by the public
    application AFTER the household has passed email
    verification.
    """

    household_reference = (
        household_reference
        .strip()
        .upper()
    )

    with _connect() as conn:

        conn.row_factory = sqlite3.Row

        # ---------------------------------------------
        # Get household
        # ---------------------------------------------

        household_row = conn.execute(
            """
            SELECT *
            FROM households
            WHERE household_reference = ?;
            """,
            (household_reference,),
        ).fetchone()

        if household_row is None:
            return None

        # ---------------------------------------------
        # Get children
        # ---------------------------------------------

        child_rows = conn.execute(
            """
            SELECT *
            FROM children
            WHERE household_id = ?
            ORDER BY child_id;
            """,
            (
                household_row["household_id"],
            ),
        ).fetchall()

    household = dict(household_row)

    children = []

    for row in child_rows:

        child = dict(row)

        # Convert SQLite text date back to
        # a Python date object for Streamlit.
        child["date_of_birth"] = (
            date.fromisoformat(
                child["date_of_birth"]
            )
        )

        # SQLite stores booleans as 0/1.
        child["receiving_confirmation"] = bool(
            child["receiving_confirmation"]
        )

        children.append(child)

    return household, children


# ---------------------------------------------------------
# Update existing registration
# ---------------------------------------------------------

def update_registration(
    household_id: int,
    household: dict,
    children: list[dict],
) -> None:
    """
    Update an existing household registration.

    Handles:
        - household changes
        - edited children
        - newly added children
        - removed children
    """

    if not children:
        raise ValueError(
            "At least one child must be added."
        )

    with _connect() as conn:

        # ---------------------------------------------
        # Update household
        # ---------------------------------------------

        conn.execute(
            """
            UPDATE households
            SET
                parent_a_first_name = ?,
                parent_a_last_name = ?,
                parent_a_email = ?,
                parent_a_phone = ?,

                parent_b_first_name = ?,
                parent_b_last_name = ?,
                parent_b_email = ?,
                parent_b_phone = ?,

                address_line_1 = ?,
                address_line_2 = ?,
                city = ?,
                state = ?,
                zip_code = ?

            WHERE household_id = ?;
            """,
            (
                household[
                    "parent_a_first_name"
                ],
                household[
                    "parent_a_last_name"
                ],
                household[
                    "parent_a_email"
                ],
                household[
                    "parent_a_phone"
                ],

                household.get(
                    "parent_b_first_name",
                    "",
                ),
                household.get(
                    "parent_b_last_name",
                    "",
                ),
                household.get(
                    "parent_b_email",
                    "",
                ),
                household.get(
                    "parent_b_phone",
                    "",
                ),

                household["address_line_1"],
                household.get(
                    "address_line_2",
                    "",
                ),
                household["city"],
                household["state"],
                household["zip_code"],

                household_id,
            ),
        )

        # ---------------------------------------------
        # Find children already in database
        # ---------------------------------------------

        existing_child_ids = {
            row[0]
            for row in conn.execute(
                """
                SELECT child_id
                FROM children
                WHERE household_id = ?;
                """,
                (household_id,),
            ).fetchall()
        }

        # ---------------------------------------------
        # Find existing children still present
        # ---------------------------------------------

        submitted_child_ids = {
            child["child_id"]
            for child in children
            if child.get("child_id") is not None
        }

        # ---------------------------------------------
        # Delete children removed by parent
        # ---------------------------------------------

        children_to_delete = (
            existing_child_ids
            - submitted_child_ids
        )

        for child_id in children_to_delete:

            conn.execute(
                """
                DELETE FROM children
                WHERE child_id = ?
                AND household_id = ?;
                """,
                (
                    child_id,
                    household_id,
                ),
            )

        # ---------------------------------------------
        # Update existing children / insert new ones
        # ---------------------------------------------

        for child in children:

            date_of_birth = child["date_of_birth"]

            if hasattr(date_of_birth, "isoformat"):
                date_of_birth = (
                    date_of_birth.isoformat()
                )

            child_id = child.get("child_id")

            # Existing child
            if child_id is not None:

                conn.execute(
                    """
                    UPDATE children
                    SET
                        first_name = ?,
                        middle_name = ?,
                        last_name = ?,
                        date_of_birth = ?,
                        grade = ?,
                        school = ?,
                        receiving_confirmation = ?

                    WHERE child_id = ?
                    AND household_id = ?;
                    """,
                    (
                        child["first_name"],
                        child.get(
                            "middle_name",
                            "",
                        ),
                        child["last_name"],
                        date_of_birth,
                        child["grade"],
                        child["school"],
                        int(
                            child.get(
                                "receiving_confirmation",
                                False,
                            )
                        ),

                        child_id,
                        household_id,
                    ),
                )

            # New child
            else:

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
                        child.get(
                            "middle_name",
                            "",
                        ),
                        child["last_name"],
                        date_of_birth,
                        child["grade"],
                        child["school"],
                        int(
                            child.get(
                                "receiving_confirmation",
                                False,
                            )
                        ),
                    ),
                )