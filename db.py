from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import psycopg
from psycopg.rows import dict_row
import streamlit as st


# ---------------------------------------------------------
# Verification settings
# ---------------------------------------------------------

VERIFICATION_CODE_DIGITS = 6
VERIFICATION_CODE_TTL_MINUTES = 10
VERIFICATION_MAX_ATTEMPTS = 5


# ---------------------------------------------------------
# Database connection
# ---------------------------------------------------------

def _connect() -> psycopg.Connection:
    """
    Open a connection to the PostgreSQL database.

    The connection URL is stored in:
        .streamlit/secrets.toml

    [database]
    url = "postgresql://..."
    """

    database_url = st.secrets["database"]["url"]

    return psycopg.connect(
        database_url,
        row_factory=dict_row,
    )


# ---------------------------------------------------------
# Initialize database
# ---------------------------------------------------------

def init_db() -> None:
    """
    Create all application tables, indexes, and
    standard roster groups if they do not already exist.

    Safe to run every time the app starts.
    """

    with _connect() as conn:

        # -------------------------------------------------
        # Households
        # -------------------------------------------------

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS households (
                household_id BIGSERIAL PRIMARY KEY,

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

                created_at TIMESTAMPTZ NOT NULL
                    DEFAULT CURRENT_TIMESTAMP
            );
            """
        )

        # -------------------------------------------------
        # Children
        # -------------------------------------------------

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS children (
                child_id BIGSERIAL PRIMARY KEY,

                household_id BIGINT NOT NULL,

                first_name TEXT NOT NULL,
                middle_name TEXT,
                last_name TEXT NOT NULL,

                date_of_birth DATE NOT NULL,

                grade TEXT NOT NULL,
                school TEXT NOT NULL,

                receiving_first_communion_reconciliation
                    BOOLEAN NOT NULL DEFAULT FALSE,

                receiving_confirmation
                    BOOLEAN NOT NULL DEFAULT FALSE,

                baptism_status TEXT,
                first_reconciliation_status TEXT,
                first_communion_status TEXT,

                CONSTRAINT fk_children_household
                    FOREIGN KEY (household_id)
                    REFERENCES households (household_id)
                    ON DELETE CASCADE
            );
            """
        )

        # -------------------------------------------------
        # Simple migrations
        # -------------------------------------------------

        conn.execute(
            """
            ALTER TABLE children
            ADD COLUMN IF NOT EXISTS
                receiving_first_communion_reconciliation
                BOOLEAN NOT NULL DEFAULT FALSE;
            """
        )

        conn.execute(
            """
            ALTER TABLE children
            ADD COLUMN IF NOT EXISTS
                receiving_confirmation
                BOOLEAN NOT NULL DEFAULT FALSE;
            """
        )

        conn.execute(
            """
            ALTER TABLE children
            ADD COLUMN IF NOT EXISTS
                baptism_status TEXT;
            """
        )

        conn.execute(
            """
            ALTER TABLE children
            ADD COLUMN IF NOT EXISTS
                first_reconciliation_status TEXT;
            """
        )

        conn.execute(
            """
            ALTER TABLE children
            ADD COLUMN IF NOT EXISTS
                first_communion_status TEXT;
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS
                idx_children_household_id
            ON children (household_id);
            """
        )

        # -------------------------------------------------
        # Household verification codes
        # -------------------------------------------------

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS verification_codes (
                verification_id BIGSERIAL PRIMARY KEY,

                household_id BIGINT NOT NULL,

                code_hash TEXT NOT NULL,
                salt TEXT NOT NULL,

                attempt_count INTEGER NOT NULL DEFAULT 0,
                max_attempts INTEGER NOT NULL DEFAULT 5,

                created_at TIMESTAMPTZ NOT NULL,
                expires_at TIMESTAMPTZ NOT NULL,
                used_at TIMESTAMPTZ,

                CONSTRAINT fk_verification_household
                    FOREIGN KEY (household_id)
                    REFERENCES households (household_id)
                    ON DELETE CASCADE
            );
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS
                idx_verification_household_id
            ON verification_codes (household_id);
            """
        )

        # -------------------------------------------------
        # Admin verification codes
        # -------------------------------------------------

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS admin_verification_codes (
                verification_id BIGSERIAL PRIMARY KEY,

                email TEXT NOT NULL,

                code_hash TEXT NOT NULL,
                salt TEXT NOT NULL,

                attempt_count INTEGER NOT NULL DEFAULT 0,
                max_attempts INTEGER NOT NULL DEFAULT 5,

                created_at TIMESTAMPTZ NOT NULL,
                expires_at TIMESTAMPTZ NOT NULL,
                used_at TIMESTAMPTZ
            );
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS
                idx_admin_verification_email
            ON admin_verification_codes (email);
            """
        )

        # -------------------------------------------------
        # Roster groups
        # -------------------------------------------------

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS roster_groups (
                group_key TEXT PRIMARY KEY,
                display_name TEXT NOT NULL,
                category TEXT NOT NULL,
                catechists TEXT NOT NULL DEFAULT ''
            );
            """
        )

        # -------------------------------------------------
        # Seed standard roster groups
        # -------------------------------------------------

        roster_groups = [
            (
                "kindergarten",
                "Kindergarten",
                "PSR",
            ),
            (
                "grade_1",
                "Grade 1",
                "PSR",
            ),
            (
                "grade_2",
                "Grade 2",
                "PSR",
            ),
            (
                "grade_3",
                "Grade 3",
                "PSR",
            ),
            (
                "grade_4",
                "Grade 4",
                "PSR",
            ),
            (
                "grade_5",
                "Grade 5",
                "PSR",
            ),
            (
                "edge",
                "EDGE",
                "Youth Ministry",
            ),
            (
                "life_teen",
                "Life Teen",
                "Youth Ministry",
            ),
        ]

        with conn.cursor() as cursor:

            cursor.executemany(
                """
                INSERT INTO roster_groups (
                    group_key,
                    display_name,
                    category,
                    catechists
                )
                VALUES (%s, %s, %s, '')
                ON CONFLICT (group_key)
                DO NOTHING;
                """,
                roster_groups,
            )


# ---------------------------------------------------------
# Household reference generator
# ---------------------------------------------------------

def _generate_household_reference() -> str:
    """
    Generate a human-friendly public Household ID.

    Example:
        ASC-K7M4P9
    """

    # Avoid:
    # I, O, 0, 1
    characters = (
        "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    )

    while True:

        code = "".join(
            secrets.choice(
                characters
            )
            for _ in range(6)
        )

        household_reference = (
            f"ASC-{code}"
        )

        with _connect() as conn:

            existing = conn.execute(
                """
                SELECT 1
                FROM households
                WHERE household_reference = %s;
                """,
                (
                    household_reference,
                ),
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
    Hash a verification code using a unique salt.

    Plaintext verification codes are never
    stored in the database.
    """

    value = (
        f"{salt}:{code}"
        .encode(
            "utf-8"
        )
    )

    return hashlib.sha256(
        value
    ).hexdigest()


def _generate_verification_code() -> str:
    """
    Generate a zero-padded 6-digit verification code.

    Example:
        042817
    """

    upper_limit = (
        10 ** VERIFICATION_CODE_DIGITS
    )

    number = secrets.randbelow(
        upper_limit
    )

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

    Searches both Parent / Guardian A and B.

    Matching is case-insensitive.
    """

    email = (
        email
        .strip()
        .lower()
    )

    if not email:

        return []

    with _connect() as conn:

        rows = conn.execute(
            """
            SELECT household_reference
            FROM households
            WHERE LOWER(TRIM(parent_a_email)) = %s
               OR LOWER(TRIM(parent_b_email)) = %s
            ORDER BY household_id;
            """,
            (
                email,
                email,
            ),
        ).fetchall()

    return [
        row[
            "household_reference"
        ]
        for row in rows
    ]


# ---------------------------------------------------------
# Create household verification
# ---------------------------------------------------------

def create_household_verification(
    household_reference: str,
) -> dict | None:
    """
    Create a new email verification code for
    an existing household.

    The plaintext code is returned to the app once
    so it can be emailed.

    Only the salted hash is stored.
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
            WHERE household_reference = %s;
            """,
            (
                household_reference,
            ),
        ).fetchone()

        if household is None:

            return None

        household_id = household[
            "household_id"
        ]

        email = household[
            "parent_a_email"
        ]

        code = (
            _generate_verification_code()
        )

        salt = secrets.token_hex(
            16
        )

        code_hash = (
            _hash_verification_code(
                code,
                salt,
            )
        )

        now = datetime.now(
            timezone.utc
        )

        expires_at = (
            now
            + timedelta(
                minutes=(
                    VERIFICATION_CODE_TTL_MINUTES
                )
            )
        )

        # Invalidate previous unused codes.
        conn.execute(
            """
            UPDATE verification_codes
            SET used_at = %s
            WHERE household_id = %s
              AND used_at IS NULL;
            """,
            (
                now,
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
            VALUES (
                %s,
                %s,
                %s,
                0,
                %s,
                %s,
                %s,
                NULL
            );
            """,
            (
                household_id,
                code_hash,
                salt,
                VERIFICATION_MAX_ATTEMPTS,
                now,
                expires_at,
            ),
        )

    return {
        "household_reference":
            household[
                "household_reference"
            ],

        "email":
            email,

        "code":
            code,

        "expires_minutes":
            VERIFICATION_CODE_TTL_MINUTES,
    }


# ---------------------------------------------------------
# Verify household code
# ---------------------------------------------------------

def verify_household_code(
    household_reference: str,
    code: str,
) -> tuple[bool, str]:
    """
    Verify a one-time household email code.

    Status values:
        verified
        invalid
        expired
        locked
        no_active_code
        household_not_found
    """

    household_reference = (
        household_reference
        .strip()
        .upper()
    )

    code = (
        code
        .strip()
    )

    now = datetime.now(
        timezone.utc
    )

    with _connect() as conn:

        household = conn.execute(
            """
            SELECT household_id
            FROM households
            WHERE household_reference = %s;
            """,
            (
                household_reference,
            ),
        ).fetchone()

        if household is None:

            return (
                False,
                "household_not_found",
            )

        household_id = household[
            "household_id"
        ]

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
            WHERE household_id = %s
              AND used_at IS NULL
            ORDER BY verification_id DESC
            LIMIT 1;
            """,
            (
                household_id,
            ),
        ).fetchone()

        if verification is None:

            return (
                False,
                "no_active_code",
            )

        verification_id = verification[
            "verification_id"
        ]

        stored_hash = verification[
            "code_hash"
        ]

        salt = verification[
            "salt"
        ]

        attempt_count = verification[
            "attempt_count"
        ]

        max_attempts = verification[
            "max_attempts"
        ]

        expires_at = verification[
            "expires_at"
        ]

        if now >= expires_at:

            conn.execute(
                """
                UPDATE verification_codes
                SET used_at = %s
                WHERE verification_id = %s;
                """,
                (
                    now,
                    verification_id,
                ),
            )

            return (
                False,
                "expired",
            )

        if (
            attempt_count
            >= max_attempts
        ):

            return (
                False,
                "locked",
            )

        submitted_hash = (
            _hash_verification_code(
                code,
                salt,
            )
        )

        code_matches = (
            secrets.compare_digest(
                stored_hash,
                submitted_hash,
            )
        )

        if code_matches:

            conn.execute(
                """
                UPDATE verification_codes
                SET used_at = %s
                WHERE verification_id = %s;
                """,
                (
                    now,
                    verification_id,
                ),
            )

            return (
                True,
                "verified",
            )

        new_attempt_count = (
            attempt_count + 1
        )

        if (
            new_attempt_count
            >= max_attempts
        ):

            conn.execute(
                """
                UPDATE verification_codes
                SET
                    attempt_count = %s,
                    used_at = %s
                WHERE verification_id = %s;
                """,
                (
                    new_attempt_count,
                    now,
                    verification_id,
                ),
            )

            return (
                False,
                "locked",
            )

        conn.execute(
            """
            UPDATE verification_codes
            SET attempt_count = %s
            WHERE verification_id = %s;
            """,
            (
                new_attempt_count,
                verification_id,
            ),
        )

        return (
            False,
            "invalid",
        )


# ---------------------------------------------------------
# Create admin verification
# ---------------------------------------------------------

def create_admin_verification(
    email: str,
) -> dict:
    """
    Create a one-time verification code for
    an authorized administrator.

    Admin authorization itself remains handled
    by app.py.
    """

    email = (
        email
        .strip()
        .lower()
    )

    if not email:

        raise ValueError(
            "Admin email cannot be empty."
        )

    code = (
        _generate_verification_code()
    )

    salt = secrets.token_hex(
        16
    )

    code_hash = (
        _hash_verification_code(
            code,
            salt,
        )
    )

    now = datetime.now(
        timezone.utc
    )

    expires_at = (
        now
        + timedelta(
            minutes=(
                VERIFICATION_CODE_TTL_MINUTES
            )
        )
    )

    with _connect() as conn:

        # Invalidate previous unused codes.
        conn.execute(
            """
            UPDATE admin_verification_codes
            SET used_at = %s
            WHERE LOWER(TRIM(email)) = %s
              AND used_at IS NULL;
            """,
            (
                now,
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
            VALUES (
                %s,
                %s,
                %s,
                0,
                %s,
                %s,
                %s,
                NULL
            );
            """,
            (
                email,
                code_hash,
                salt,
                VERIFICATION_MAX_ATTEMPTS,
                now,
                expires_at,
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
    Verify a one-time administrator login code.
    """

    email = (
        email
        .strip()
        .lower()
    )

    code = (
        code
        .strip()
    )

    if not email:

        return (
            False,
            "no_active_code",
        )

    now = datetime.now(
        timezone.utc
    )

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
            WHERE LOWER(TRIM(email)) = %s
              AND used_at IS NULL
            ORDER BY verification_id DESC
            LIMIT 1;
            """,
            (
                email,
            ),
        ).fetchone()

        if verification is None:

            return (
                False,
                "no_active_code",
            )

        verification_id = verification[
            "verification_id"
        ]

        stored_hash = verification[
            "code_hash"
        ]

        salt = verification[
            "salt"
        ]

        attempt_count = verification[
            "attempt_count"
        ]

        max_attempts = verification[
            "max_attempts"
        ]

        expires_at = verification[
            "expires_at"
        ]

        if now >= expires_at:

            conn.execute(
                """
                UPDATE admin_verification_codes
                SET used_at = %s
                WHERE verification_id = %s;
                """,
                (
                    now,
                    verification_id,
                ),
            )

            return (
                False,
                "expired",
            )

        if (
            attempt_count
            >= max_attempts
        ):

            return (
                False,
                "locked",
            )

        submitted_hash = (
            _hash_verification_code(
                code,
                salt,
            )
        )

        code_matches = (
            secrets.compare_digest(
                stored_hash,
                submitted_hash,
            )
        )

        if code_matches:

            conn.execute(
                """
                UPDATE admin_verification_codes
                SET used_at = %s
                WHERE verification_id = %s;
                """,
                (
                    now,
                    verification_id,
                ),
            )

            return (
                True,
                "verified",
            )

        new_attempt_count = (
            attempt_count + 1
        )

        if (
            new_attempt_count
            >= max_attempts
        ):

            conn.execute(
                """
                UPDATE admin_verification_codes
                SET
                    attempt_count = %s,
                    used_at = %s
                WHERE verification_id = %s;
                """,
                (
                    new_attempt_count,
                    now,
                    verification_id,
                ),
            )

            return (
                False,
                "locked",
            )

        conn.execute(
            """
            UPDATE admin_verification_codes
            SET attempt_count = %s
            WHERE verification_id = %s;
            """,
            (
                new_attempt_count,
                verification_id,
            ),
        )

        return (
            False,
            "invalid",
        )


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

    The entire registration is committed as one
    PostgreSQL transaction.
    """

    if not children:

        raise ValueError(
            "At least one child must be added."
        )

    household_reference = (
        _generate_household_reference()
    )

    with _connect() as conn:

        household_row = conn.execute(
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
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s
            )
            RETURNING household_id;
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

                household[
                    "city"
                ],

                household[
                    "state"
                ],

                household[
                    "zip_code"
                ],
            ),
        ).fetchone()

        household_id = household_row[
            "household_id"
        ]

        for child in children:

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
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s
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

                    child[
                        "date_of_birth"
                    ],

                    child[
                        "grade"
                    ],

                    child[
                        "school"
                    ],

                    bool(
                        child.get(
                            "receiving_first_communion_reconciliation",
                            False,
                        )
                    ),

                    bool(
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
    Load a household and all children using
    the public Household ID.

    app.py should only call this after the
    household has passed email verification.
    """

    household_reference = (
        household_reference
        .strip()
        .upper()
    )

    with _connect() as conn:

        household = conn.execute(
            """
            SELECT *
            FROM households
            WHERE household_reference = %s;
            """,
            (
                household_reference,
            ),
        ).fetchone()

        if household is None:

            return None

        child_rows = conn.execute(
            """
            SELECT *
            FROM children
            WHERE household_id = %s
            ORDER BY child_id;
            """,
            (
                household[
                    "household_id"
                ],
            ),
        ).fetchall()

    # dict_row already gives us dictionaries.
    # PostgreSQL DATE values are returned as Python dates
    # and BOOLEAN values are returned as Python bools.

    children = [
        dict(row)
        for row in child_rows
    ]

    return (
        dict(household),
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
        household changes
        edited children
        new children
        removed children
        sacrament preparation
        sacramental history
    """

    if not children:

        raise ValueError(
            "At least one child must be added."
        )

    with _connect() as conn:

        # -------------------------------------------------
        # Update household
        # -------------------------------------------------

        conn.execute(
            """
            UPDATE households
            SET
                parent_a_first_name = %s,
                parent_a_last_name = %s,
                parent_a_email = %s,
                parent_a_phone = %s,

                parent_b_first_name = %s,
                parent_b_last_name = %s,
                parent_b_email = %s,
                parent_b_phone = %s,

                address_line_1 = %s,
                address_line_2 = %s,

                city = %s,
                state = %s,
                zip_code = %s

            WHERE household_id = %s;
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

        # -------------------------------------------------
        # Existing child IDs
        # -------------------------------------------------

        existing_rows = conn.execute(
            """
            SELECT child_id
            FROM children
            WHERE household_id = %s;
            """,
            (
                household_id,
            ),
        ).fetchall()

        existing_child_ids = {
            row[
                "child_id"
            ]
            for row in existing_rows
        }

        # -------------------------------------------------
        # Submitted existing IDs
        # -------------------------------------------------

        submitted_child_ids = {
            child[
                "child_id"
            ]
            for child in children
            if child.get(
                "child_id"
            ) is not None
        }

        # -------------------------------------------------
        # Delete removed children
        # -------------------------------------------------

        children_to_delete = (
            existing_child_ids
            - submitted_child_ids
        )

        for child_id in children_to_delete:

            conn.execute(
                """
                DELETE FROM children
                WHERE child_id = %s
                  AND household_id = %s;
                """,
                (
                    child_id,
                    household_id,
                ),
            )

        # -------------------------------------------------
        # Update existing / insert new children
        # -------------------------------------------------

        for child in children:

            child_id = child.get(
                "child_id"
            )

            # ---------------------------------------------
            # Existing child
            # ---------------------------------------------

            if child_id is not None:

                conn.execute(
                    """
                    UPDATE children
                    SET
                        first_name = %s,
                        middle_name = %s,
                        last_name = %s,

                        date_of_birth = %s,

                        grade = %s,
                        school = %s,

                        receiving_first_communion_reconciliation = %s,
                        receiving_confirmation = %s,

                        baptism_status = %s,
                        first_reconciliation_status = %s,
                        first_communion_status = %s

                    WHERE child_id = %s
                      AND household_id = %s;
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

                        child[
                            "date_of_birth"
                        ],

                        child[
                            "grade"
                        ],

                        child[
                            "school"
                        ],

                        bool(
                            child.get(
                                "receiving_first_communion_reconciliation",
                                False,
                            )
                        ),

                        bool(
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

            # ---------------------------------------------
            # New child
            # ---------------------------------------------

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
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s
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

                        child[
                            "date_of_birth"
                        ],

                        child[
                            "grade"
                        ],

                        child[
                            "school"
                        ],

                        bool(
                            child.get(
                                "receiving_first_communion_reconciliation",
                                False,
                            )
                        ),

                        bool(
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


# ---------------------------------------------------------
# Admin roster
# ---------------------------------------------------------

def get_admin_roster() -> list[dict]:
    """
    Return all registered children with their
    associated household information for
    the administrative dashboard.
    """

    with _connect() as conn:

        rows = conn.execute(
            """
            SELECT
                c.child_id,
                c.household_id,

                c.first_name,
                c.middle_name,
                c.last_name,

                c.date_of_birth,

                c.grade,
                c.school,

                c.receiving_first_communion_reconciliation,
                c.receiving_confirmation,

                c.baptism_status,
                c.first_reconciliation_status,
                c.first_communion_status,

                h.household_reference,

                h.parent_a_first_name,
                h.parent_a_last_name,
                h.parent_a_email,
                h.parent_a_phone,

                h.parent_b_first_name,
                h.parent_b_last_name,
                h.parent_b_email,
                h.parent_b_phone,

                h.address_line_1,
                h.address_line_2,

                h.city,
                h.state,
                h.zip_code

            FROM children AS c

            INNER JOIN households AS h
                ON c.household_id = h.household_id

            ORDER BY
                CASE c.grade
                    WHEN 'Pre-K' THEN 0
                    WHEN 'K' THEN 1
                    WHEN '1' THEN 2
                    WHEN '2' THEN 3
                    WHEN '3' THEN 4
                    WHEN '4' THEN 5
                    WHEN '5' THEN 6
                    WHEN '6' THEN 7
                    WHEN '7' THEN 8
                    WHEN '8' THEN 9
                    WHEN '9' THEN 10
                    WHEN '10' THEN 11
                    WHEN '11' THEN 12
                    WHEN '12' THEN 13
                    ELSE 99
                END,

                c.last_name,
                c.first_name;
            """
        ).fetchall()

    return [
        dict(row)
        for row in rows
    ]


# ---------------------------------------------------------
# Roster groups
# ---------------------------------------------------------

def get_roster_groups() -> list[dict]:
    """
    Return the standard PSR and Youth Ministry
    roster groups including editable catechist names.
    """

    group_order = [
        "kindergarten",
        "grade_1",
        "grade_2",
        "grade_3",
        "grade_4",
        "grade_5",
        "edge",
        "life_teen",
    ]

    with _connect() as conn:

        rows = conn.execute(
            """
            SELECT
                group_key,
                display_name,
                category,
                catechists
            FROM roster_groups;
            """
        ).fetchall()

    groups_by_key = {
        row[
            "group_key"
        ]: dict(row)
        for row in rows
    }

    return [
        groups_by_key[
            group_key
        ]
        for group_key in group_order
        if group_key in groups_by_key
    ]


# ---------------------------------------------------------
# Update roster catechists
# ---------------------------------------------------------

def update_roster_group_catechists(
    group_key: str,
    catechists: str,
) -> None:
    """
    Update the editable catechist names
    for one roster group.

    Example:
        Jane Smith, John Doe
    """

    group_key = (
        group_key
        .strip()
        .lower()
    )

    catechists = (
        catechists
        .strip()
    )

    if not group_key:

        raise ValueError(
            "Roster group cannot be empty."
        )

    with _connect() as conn:

        cursor = conn.execute(
            """
            UPDATE roster_groups
            SET catechists = %s
            WHERE group_key = %s;
            """,
            (
                catechists,
                group_key,
            ),
        )

        if cursor.rowcount == 0:

            raise ValueError(
                f"Unknown roster group: "
                f"{group_key}"
            )