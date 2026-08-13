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


# ---------------------------------------------------------
# Database connection
# ---------------------------------------------------------

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
# Database migration helpers
# ---------------------------------------------------------

def _column_exists(
    conn: sqlite3.Connection,
    table_name: str,
    column_name: str,
) -> bool:
    """
    Return True if a column already exists in a table.
    """

    columns = conn.execute(
        f"PRAGMA table_info({table_name});"
    ).fetchall()

    return any(
        column[1] == column_name
        for column in columns
    )


def _add_column_if_missing(
    conn: sqlite3.Connection,
    table_name: str,
    column_name: str,
    column_definition: str,
) -> None:
    """
    Add a column to an existing SQLite table
    only if the column is not already present.
    """

    if not _column_exists(
        conn,
        table_name,
        column_name,
    ):
        conn.execute(
            f"""
            ALTER TABLE {table_name}
            ADD COLUMN {column_name} {column_definition};
            """
        )


# ---------------------------------------------------------
# Initialize database
# ---------------------------------------------------------

def init_db() -> None:
    """
    Create the application's database tables if they
    do not already exist.

    Also performs simple migrations for new columns
    added during development.
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

                receiving_first_communion_reconciliation
                    INTEGER NOT NULL DEFAULT 0,

                receiving_confirmation
                    INTEGER NOT NULL DEFAULT 0,

                baptism_status TEXT,
                first_reconciliation_status TEXT,
                first_communion_status TEXT,

                FOREIGN KEY (household_id)
                    REFERENCES households (household_id)
                    ON DELETE CASCADE
            );
            """
        )

        # -------------------------------------------------
        # Migrate existing children table
        # -------------------------------------------------

        _add_column_if_missing(
            conn,
            "children",
            "receiving_first_communion_reconciliation",
            "INTEGER NOT NULL DEFAULT 0",
        )

        _add_column_if_missing(
            conn,
            "children",
            "receiving_confirmation",
            "INTEGER NOT NULL DEFAULT 0",
        )

        _add_column_if_missing(
            conn,
            "children",
            "baptism_status",
            "TEXT",
        )

        _add_column_if_missing(
            conn,
            "children",
            "first_reconciliation_status",
            "TEXT",
        )

        _add_column_if_missing(
            conn,
            "children",
            "first_communion_status",
            "TEXT",
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_children_household_id
            ON children (household_id);
            """
        )

        # -------------------------------------------------
        # Household verification codes
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

        # -------------------------------------------------
        # Admin verification codes
        # -------------------------------------------------

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS admin_verification_codes (
                verification_id INTEGER PRIMARY KEY AUTOINCREMENT,

                email TEXT NOT NULL,

                code_hash TEXT NOT NULL,
                salt TEXT NOT NULL,

                attempt_count INTEGER NOT NULL DEFAULT 0,
                max_attempts INTEGER NOT NULL DEFAULT 5,

                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                used_at TEXT
            );
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_admin_verification_email
            ON admin_verification_codes (email);
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
# Household ID recovery
# ---------------------------------------------------------

def get_household_references_by_email(
    email: str,
) -> list[str]:
    """
    Find household references associated with an email.

    Searches both Parent / Guardian A and
    Parent / Guardian B.

    Matching is case-insensitive.

    Returns an empty list if no matching household exists.
    """

    email = email.strip().lower()

    if not email:
        return []

    with _connect() as conn:

        rows = conn.execute(
            """
            SELECT household_reference
            FROM households
            WHERE LOWER(TRIM(parent_a_email)) = ?
               OR LOWER(TRIM(parent_b_email)) = ?
            ORDER BY household_id;
            """,
            (
                email,
                email,
            ),
        ).fetchall()

    return [
        row[0]
        for row in rows
    ]


# ---------------------------------------------------------
# Create household email verification code
# ---------------------------------------------------------

def create_household_verification(
    household_reference: str,
) -> dict | None:
    """
    Create a new verification code for an existing household.

    Returns information needed by the email layer.

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

        code = _generate_verification_code()

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
        "household_reference":
            stored_reference,

        "email":
            email,

        "code":
            code,

        "expires_minutes":
            VERIFICATION_CODE_TTL_MINUTES,
    }


# ---------------------------------------------------------
# Verify household email code
# ---------------------------------------------------------

def verify_household_code(
    household_reference: str,
    code: str,
) -> tuple[bool, str]:
    """
    Verify a one-time household email code.

    Possible responses:

        (True, "verified")

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

        new_attempt_count = (
            attempt_count + 1
        )

        if new_attempt_count >= max_attempts:

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
# Create admin verification code
# ---------------------------------------------------------

def create_admin_verification(
    email: str,
) -> dict:
    """
    Create a new one-time verification code for
    an authorized admin email address.

    IMPORTANT:
    Authorization is handled by the application.

    The app should check the email against the approved
    admin allowlist in Streamlit secrets BEFORE calling
    this function.

    Returns:

        {
            "email": "admin@example.com",
            "code": "482913",
            "expires_minutes": 10
        }

    The plaintext code is returned so the application
    can email it, but it is NOT stored in SQLite.
    """

    email = email.strip().lower()

    if not email:
        raise ValueError(
            "Admin email cannot be empty."
        )

    code = _generate_verification_code()

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

    with _connect() as conn:

        # Invalidate any previous unused admin codes
        # for this email address.
        conn.execute(
            """
            UPDATE admin_verification_codes
            SET used_at = ?
            WHERE LOWER(TRIM(email)) = ?
            AND used_at IS NULL;
            """,
            (
                now_text,
                email,
            ),
        )

        conn.execute(
            """
            INSERT INTO admin_verification_codes (
                email,
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
                email,
                code_hash,
                salt,
                VERIFICATION_MAX_ATTEMPTS,
                now_text,
                expires_text,
            ),
        )

    return {
        "email":
            email,

        "code":
            code,

        "expires_minutes":
            VERIFICATION_CODE_TTL_MINUTES,
    }


# ---------------------------------------------------------
# Verify admin code
# ---------------------------------------------------------

def verify_admin_code(
    email: str,
    code: str,
) -> tuple[bool, str]:
    """
    Verify a one-time admin login code.

    Possible responses:

        (True, "verified")

        (False, "invalid")
        (False, "expired")
        (False, "locked")
        (False, "no_active_code")
    """

    email = email.strip().lower()
    code = code.strip()

    if not email:
        return False, "no_active_code"

    now = datetime.now(timezone.utc)
    now_text = now.isoformat()

    with _connect() as conn:

        verification = conn.execute(
            """
            SELECT
                verification_id,
                code_hash,
                salt,
                attempt_count,
                max_attempts,
                expires_at
            FROM admin_verification_codes
            WHERE LOWER(TRIM(email)) = ?
            AND used_at IS NULL
            ORDER BY verification_id DESC
            LIMIT 1;
            """,
            (email,),
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
                UPDATE admin_verification_codes
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

            # Successful login codes become unusable
            # immediately.
            conn.execute(
                """
                UPDATE admin_verification_codes
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

        new_attempt_count = (
            attempt_count + 1
        )

        if new_attempt_count >= max_attempts:

            conn.execute(
                """
                UPDATE admin_verification_codes
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
            UPDATE admin_verification_codes
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

                household[
                    "address_line_1"
                ],

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

            date_of_birth = (
                child["date_of_birth"]
            )

            if hasattr(
                date_of_birth,
                "isoformat",
            ):
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

                    receiving_first_communion_reconciliation,
                    receiving_confirmation,

                    baptism_status,
                    first_reconciliation_status,
                    first_communion_status
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?
                );
                """,
                (
                    household_id,

                    child[
                        "first_name"
                    ],

                    child.get(
                        "middle_name",
                        "",
                    ),

                    child[
                        "last_name"
                    ],

                    date_of_birth,

                    child[
                        "grade"
                    ],

                    child[
                        "school"
                    ],

                    int(
                        child.get(
                            "receiving_first_communion_reconciliation",
                            False,
                        )
                    ),

                    int(
                        child.get(
                            "receiving_confirmation",
                            False,
                        )
                    ),

                    child.get(
                        "baptism_status"
                    ),

                    child.get(
                        "first_reconciliation_status"
                    ),

                    child.get(
                        "first_communion_status"
                    ),
                ),
            )

    return (
        household_id,
        household_reference,
    )


# ---------------------------------------------------------
# Load existing registration
# ---------------------------------------------------------

def get_registration_by_reference(
    household_reference: str,
) -> tuple[dict, list[dict]] | None:
    """
    Load a household and all of its children using
    the public Household ID.

    This should only be called by the public
    application AFTER email verification.
    """

    household_reference = (
        household_reference
        .strip()
        .upper()
    )

    with _connect() as conn:

        conn.row_factory = sqlite3.Row

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

        child_rows = conn.execute(
            """
            SELECT *
            FROM children
            WHERE household_id = ?
            ORDER BY child_id;
            """,
            (
                household_row[
                    "household_id"
                ],
            ),
        ).fetchall()

    household = dict(
        household_row
    )

    children = []

    for row in child_rows:

        child = dict(row)

        child["date_of_birth"] = (
            date.fromisoformat(
                child[
                    "date_of_birth"
                ]
            )
        )

        child[
            "receiving_first_communion_reconciliation"
        ] = bool(
            child.get(
                "receiving_first_communion_reconciliation",
                0,
            )
        )

        child[
            "receiving_confirmation"
        ] = bool(
            child.get(
                "receiving_confirmation",
                0,
            )
        )

        children.append(
            child
        )

    return (
        household,
        children,
    )


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
        - sacramental preparation
        - sacramental history
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

                household[
                    "address_line_1"
                ],

                household.get(
                    "address_line_2",
                    "",
                ),

                household[
                    "city"
                ],

                household[
                    "state"
                ],

                household[
                    "zip_code"
                ],

                household_id,
            ),
        )

        # ---------------------------------------------
        # Existing child IDs
        # ---------------------------------------------

        existing_child_ids = {
            row[0]
            for row in conn.execute(
                """
                SELECT child_id
                FROM children
                WHERE household_id = ?;
                """,
                (
                    household_id,
                ),
            ).fetchall()
        }

        # ---------------------------------------------
        # Children still present
        # ---------------------------------------------

        submitted_child_ids = {
            child["child_id"]
            for child in children
            if child.get(
                "child_id"
            ) is not None
        }

        # ---------------------------------------------
        # Delete removed children
        # ---------------------------------------------

        children_to_delete = (
            existing_child_ids
            - submitted_child_ids
        )

        for child_id in (
            children_to_delete
        ):

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
        # Update existing / insert new
        # ---------------------------------------------

        for child in children:

            date_of_birth = (
                child[
                    "date_of_birth"
                ]
            )

            if hasattr(
                date_of_birth,
                "isoformat",
            ):
                date_of_birth = (
                    date_of_birth.isoformat()
                )

            child_id = child.get(
                "child_id"
            )

            # -----------------------------------------
            # Existing child
            # -----------------------------------------

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

                        receiving_first_communion_reconciliation = ?,
                        receiving_confirmation = ?,

                        baptism_status = ?,
                        first_reconciliation_status = ?,
                        first_communion_status = ?

                    WHERE child_id = ?
                    AND household_id = ?;
                    """,
                    (
                        child[
                            "first_name"
                        ],

                        child.get(
                            "middle_name",
                            "",
                        ),

                        child[
                            "last_name"
                        ],

                        date_of_birth,

                        child[
                            "grade"
                        ],

                        child[
                            "school"
                        ],

                        int(
                            child.get(
                                "receiving_first_communion_reconciliation",
                                False,
                            )
                        ),

                        int(
                            child.get(
                                "receiving_confirmation",
                                False,
                            )
                        ),

                        child.get(
                            "baptism_status"
                        ),

                        child.get(
                            "first_reconciliation_status"
                        ),

                        child.get(
                            "first_communion_status"
                        ),

                        child_id,

                        household_id,
                    ),
                )

            # -----------------------------------------
            # New child
            # -----------------------------------------

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

                        receiving_first_communion_reconciliation,
                        receiving_confirmation,

                        baptism_status,
                        first_reconciliation_status,
                        first_communion_status
                    )
                    VALUES (
                        ?, ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?
                    );
                    """,
                    (
                        household_id,

                        child[
                            "first_name"
                        ],

                        child.get(
                            "middle_name",
                            "",
                        ),

                        child[
                            "last_name"
                        ],

                        date_of_birth,

                        child[
                            "grade"
                        ],

                        child[
                            "school"
                        ],

                        int(
                            child.get(
                                "receiving_first_communion_reconciliation",
                                False,
                            )
                        ),

                        int(
                            child.get(
                                "receiving_confirmation",
                                False,
                            )
                        ),

                        child.get(
                            "baptism_status"
                        ),

                        child.get(
                            "first_reconciliation_status"
                        ),

                        child.get(
                            "first_communion_status"
                        ),
                    ),
                )