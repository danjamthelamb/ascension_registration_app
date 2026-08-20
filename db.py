from __future__ import annotations

import hashlib
import os
import secrets
from pathlib import Path
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

def _get_database_url() -> str:
    """
    Resolve the PostgreSQL connection URL.

    Priority:
        1. DATABASE_URL environment variable
        2. Streamlit secrets

    Streamlit handles the TOML parsing for us, including
    multiline arrays and other valid TOML syntax.
    """

    environment_url = (
        os.getenv(
            "DATABASE_URL",
            "",
        )
        .strip()
    )

    if environment_url:
        return environment_url

    try:

        streamlit_url = str(
            st.secrets[
                "database"
            ][
                "url"
            ]
        ).strip()

        if streamlit_url:
            return streamlit_url

    except Exception as exc:

        raise RuntimeError(
            "No database URL was found in DATABASE_URL "
            "or [database].url in .streamlit/secrets.toml."
        ) from exc

    raise RuntimeError(
        "No database URL was found in DATABASE_URL "
        "or [database].url in .streamlit/secrets.toml."
    )


def _connect() -> psycopg.Connection:
    """
    Open a PostgreSQL connection using the configured URL.
    """

    return psycopg.connect(
        _get_database_url(),
        row_factory=dict_row,
    )


# ---------------------------------------------------------
# Initialize database
# ---------------------------------------------------------

def init_db() -> None:
    """
    Create all application tables, indexes, migrations,
    and standard roster groups if they do not already exist.

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

                emergency_contact_name
                    TEXT NOT NULL DEFAULT '',

                emergency_contact_relationship
                    TEXT NOT NULL DEFAULT '',

                emergency_contact_phone
                    TEXT NOT NULL DEFAULT '',

                created_at TIMESTAMPTZ NOT NULL
                    DEFAULT CURRENT_TIMESTAMP
            );
            """
        )

        # -------------------------------------------------
        # Household migrations
        # -------------------------------------------------

        conn.execute(
            """
            ALTER TABLE households
            ADD COLUMN IF NOT EXISTS
                emergency_contact_name
                TEXT NOT NULL DEFAULT '';
            """
        )

        conn.execute(
            """
            ALTER TABLE households
            ADD COLUMN IF NOT EXISTS
                emergency_contact_relationship
                TEXT NOT NULL DEFAULT '';
            """
        )

        conn.execute(
            """
            ALTER TABLE households
            ADD COLUMN IF NOT EXISTS
                emergency_contact_phone
                TEXT NOT NULL DEFAULT '';
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
        # Child migrations
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
                catechists TEXT NOT NULL DEFAULT '',
                classroom TEXT NOT NULL DEFAULT ''
            );
            """
        )

        # -------------------------------------------------
        # Roster group migrations
        # -------------------------------------------------

        conn.execute(
            """
            ALTER TABLE roster_groups
            ADD COLUMN IF NOT EXISTS
                classroom TEXT NOT NULL DEFAULT '';
            """
        )

        # -------------------------------------------------
        # Household messaging
        # -------------------------------------------------

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                message_id BIGSERIAL PRIMARY KEY,

                created_at TIMESTAMPTZ NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,

                created_by TEXT NOT NULL,

                message_text TEXT NOT NULL,

                audiences TEXT[] NOT NULL
                    DEFAULT '{}'::TEXT[],

                status TEXT NOT NULL
                    DEFAULT 'draft',

                is_test BOOLEAN NOT NULL
                    DEFAULT FALSE,

                request_key TEXT,

                CONSTRAINT chk_messages_status
                    CHECK (
                        status IN (
                            'draft',
                            'queued',
                            'completed',
                            'partial',
                            'failed',
                            'cancelled'
                        )
                    )
            );
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS
                idx_messages_created_at
            ON messages (created_at DESC);
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS
                idx_messages_status
            ON messages (status);
            """
        )

        # -------------------------------------------------
        # Household message recipient snapshots
        # -------------------------------------------------

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS message_recipients (
                recipient_id BIGSERIAL PRIMARY KEY,

                message_id BIGINT NOT NULL,

                household_reference TEXT NOT NULL,

                contact_name TEXT NOT NULL,
                phone TEXT NOT NULL,
                contact_source TEXT NOT NULL,

                children TEXT NOT NULL
                    DEFAULT '',

                status TEXT NOT NULL
                    DEFAULT 'draft',

                claimed_at TIMESTAMPTZ,
                claim_token TEXT,

                submitted_at TIMESTAMPTZ,
                sent_at TIMESTAMPTZ,

                transport TEXT,
                error_message TEXT,

                CONSTRAINT fk_message_recipient_message
                    FOREIGN KEY (message_id)
                    REFERENCES messages (message_id)
                    ON DELETE CASCADE,

                CONSTRAINT uq_message_household
                    UNIQUE (
                        message_id,
                        household_reference
                    ),

                CONSTRAINT chk_message_recipient_status
                    CHECK (
                        status IN (
                            'draft',
                            'queued',
                            'claimed',
                            'submitted',
                            'sent',
                            'failed',
                            'cancelled'
                        )
                    )
            );
            """
        )

        # -------------------------------------------------
        # Household messaging migrations
        # -------------------------------------------------

        conn.execute(
            """
            ALTER TABLE message_recipients
            ADD COLUMN IF NOT EXISTS
                claimed_at TIMESTAMPTZ;
            """
        )

        conn.execute(
            """
            ALTER TABLE message_recipients
            ADD COLUMN IF NOT EXISTS
                claim_token TEXT;
            """
        )

        conn.execute(
            """
            ALTER TABLE message_recipients
            ADD COLUMN IF NOT EXISTS
                submitted_at TIMESTAMPTZ;
            """
        )

        conn.execute(
            """
            ALTER TABLE message_recipients
            ADD COLUMN IF NOT EXISTS
                transport TEXT;
            """
        )

        conn.execute(
            """
            ALTER TABLE messages
            ADD COLUMN IF NOT EXISTS
                is_test BOOLEAN NOT NULL DEFAULT FALSE;
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS
                idx_messages_test_status
            ON messages (is_test, status);
            """
        )

        conn.execute(
            """
            ALTER TABLE messages
            ADD COLUMN IF NOT EXISTS
                request_key TEXT;
            """
        )

        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS
                uq_messages_test_request_key
            ON messages (request_key)
            WHERE is_test = TRUE
              AND request_key IS NOT NULL;
            """
        )

        # Recreate status checks so existing DEV databases
        # gain the new queue / gateway states safely.
        conn.execute(
            """
            ALTER TABLE messages
            DROP CONSTRAINT IF EXISTS
                chk_messages_status;
            """
        )

        conn.execute(
            """
            ALTER TABLE messages
            ADD CONSTRAINT
                chk_messages_status
            CHECK (
                status IN (
                    'draft',
                    'queued',
                    'completed',
                    'partial',
                    'failed',
                    'cancelled'
                )
            );
            """
        )

        conn.execute(
            """
            ALTER TABLE message_recipients
            DROP CONSTRAINT IF EXISTS
                chk_message_recipient_status;
            """
        )

        conn.execute(
            """
            ALTER TABLE message_recipients
            ADD CONSTRAINT
                chk_message_recipient_status
            CHECK (
                status IN (
                    'draft',
                    'queued',
                    'claimed',
                    'submitted',
                    'sent',
                    'failed',
                    'cancelled'
                )
            );
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS
                idx_message_recipients_message_id
            ON message_recipients (message_id);
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS
                idx_message_recipients_queue
            ON message_recipients (
                status,
                recipient_id
            );
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS
                idx_message_recipients_status
            ON message_recipients (status);
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
                    catechists,
                    classroom
                )
                VALUES (%s, %s, %s, '', '')
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
                zip_code,

                emergency_contact_name,
                emergency_contact_relationship,
                emergency_contact_phone
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

                household.get(
                    "emergency_contact_name",
                    "",
                ),

                household.get(
                    "emergency_contact_relationship",
                    "",
                ),

                household.get(
                    "emergency_contact_phone",
                    "",
                ),
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
        emergency contact changes
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
                zip_code = %s,

                emergency_contact_name = %s,
                emergency_contact_relationship = %s,
                emergency_contact_phone = %s

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

                household.get(
                    "emergency_contact_name",
                    "",
                ),

                household.get(
                    "emergency_contact_relationship",
                    "",
                ),

                household.get(
                    "emergency_contact_phone",
                    "",
                ),

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
                h.zip_code,

                h.emergency_contact_name,
                h.emergency_contact_relationship,
                h.emergency_contact_phone

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
    roster groups including editable catechist
    names and classroom assignments.
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
                catechists,
                classroom
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


# ---------------------------------------------------------
# Update roster classroom
# ---------------------------------------------------------

def update_roster_group_classroom(
    group_key: str,
    classroom: str,
) -> None:
    """
    Update the classroom assigned to one roster group.

    Example:
        Room 1 - St. Monica
    """

    group_key = (
        group_key
        .strip()
        .lower()
    )

    classroom = (
        classroom
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
            SET classroom = %s
            WHERE group_key = %s;
            """,
            (
                classroom,
                group_key,
            ),
        )

        if cursor.rowcount == 0:

            raise ValueError(
                f"Unknown roster group: "
                f"{group_key}"
            )


# ---------------------------------------------------------
# Household messaging
# ---------------------------------------------------------

def create_message_draft(
    created_by: str,
    message_text: str,
    audiences: list[str],
    recipients: list[dict],
) -> int:
    """
    Create one message draft and snapshot its resolved
    household recipients.

    This function does not send anything.

    Each recipient dict should contain:
        Household ID
        Contact
        Phone
        Using
        Children

    One household may appear only once per message.
    """

    created_by = (
        created_by
        .strip()
        .lower()
    )

    message_text = (
        message_text
        .strip()
    )

    audiences = [
        str(audience).strip()

        for audience in audiences

        if str(audience).strip()
    ]

    if not created_by:

        raise ValueError(
            "Message creator cannot be empty."
        )

    if not message_text:

        raise ValueError(
            "Message text cannot be empty."
        )

    if not audiences:

        raise ValueError(
            "At least one audience must be selected."
        )

    if not recipients:

        raise ValueError(
            "At least one recipient is required."
        )

    seen_households = set()

    with _connect() as conn:

        message_row = conn.execute(
            """
            INSERT INTO messages (
                created_by,
                message_text,
                audiences,
                status
            )
            VALUES (
                %s,
                %s,
                %s,
                'draft'
            )
            RETURNING message_id;
            """,
            (
                created_by,
                message_text,
                audiences,
            ),
        ).fetchone()

        message_id = message_row[
            "message_id"
        ]

        for recipient in recipients:

            household_reference = str(
                recipient.get(
                    "Household ID",
                    "",
                )
                or ""
            ).strip()

            contact_name = str(
                recipient.get(
                    "Contact",
                    "",
                )
                or ""
            ).strip()

            phone = str(
                recipient.get(
                    "Phone",
                    "",
                )
                or ""
            ).strip()

            contact_source = str(
                recipient.get(
                    "Using",
                    "",
                )
                or ""
            ).strip()

            children = str(
                recipient.get(
                    "Children",
                    "",
                )
                or ""
            ).strip()

            if not household_reference:

                raise ValueError(
                    "Recipient Household ID cannot be empty."
                )

            if household_reference in seen_households:

                raise ValueError(
                    "A household may only appear once "
                    "in a message draft."
                )

            if not contact_name:

                raise ValueError(
                    f"Recipient contact name is missing for "
                    f"{household_reference}."
                )

            if not phone:

                raise ValueError(
                    f"Recipient phone is missing for "
                    f"{household_reference}."
                )

            if not contact_source:

                raise ValueError(
                    f"Recipient contact source is missing for "
                    f"{household_reference}."
                )

            seen_households.add(
                household_reference
            )

            conn.execute(
                """
                INSERT INTO message_recipients (
                    message_id,
                    household_reference,
                    contact_name,
                    phone,
                    contact_source,
                    children,
                    status
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    'draft'
                );
                """,
                (
                    message_id,
                    household_reference,
                    contact_name,
                    phone,
                    contact_source,
                    children,
                ),
            )

    return message_id


def get_message_history(
    limit: int = 50,
) -> list[dict]:
    """
    Return the most recent message drafts / messages
    with their snapshotted recipient counts.
    """

    if limit < 1:

        return []

    with _connect() as conn:

        rows = conn.execute(
            """
            SELECT
                m.message_id,
                m.created_at,
                m.created_by,
                m.message_text,
                m.audiences,
                m.status,

                COUNT(
                    mr.recipient_id
                ) AS recipient_count

            FROM messages AS m

            LEFT JOIN message_recipients AS mr
                ON mr.message_id = m.message_id

            WHERE m.is_test = FALSE

            GROUP BY
                m.message_id,
                m.created_at,
                m.created_by,
                m.message_text,
                m.audiences,
                m.status

            ORDER BY
                m.created_at DESC,
                m.message_id DESC

            LIMIT %s;
            """,
            (
                limit,
            ),
        ).fetchall()

    return [
        dict(row)
        for row in rows
    ]


def get_message(
    message_id: int,
) -> dict | None:
    """
    Return one message record.
    """

    with _connect() as conn:

        row = conn.execute(
            """
            SELECT
                message_id,
                created_at,
                created_by,
                message_text,
                audiences,
                status
            FROM messages
            WHERE message_id = %s;
            """,
            (
                message_id,
            ),
        ).fetchone()

    if row is None:

        return None

    return dict(
        row
    )


def get_message_recipients(
    message_id: int,
) -> list[dict]:
    """
    Return the snapshotted recipients for one message.
    """

    with _connect() as conn:

        rows = conn.execute(
            """
            SELECT
                recipient_id,
                message_id,
                household_reference,
                contact_name,
                phone,
                contact_source,
                children,
                status,
                claimed_at,
                claim_token,
                submitted_at,
                sent_at,
                transport,
                error_message
            FROM message_recipients
            WHERE message_id = %s
            ORDER BY
                household_reference,
                recipient_id;
            """,
            (
                message_id,
            ),
        ).fetchall()

    return [
        dict(row)
        for row in rows
    ]


def delete_message_draft(
    message_id: int,
) -> bool:
    """
    Delete one unsent draft and all of its recipient snapshots.

    Returns True if a draft was deleted.
    Returns False if the message does not exist or is no
    longer in draft status.
    """

    with _connect() as conn:

        cursor = conn.execute(
            """
            DELETE FROM messages
            WHERE message_id = %s
              AND status = 'draft';
            """,
            (
                message_id,
            ),
        )

        return (
            cursor.rowcount
            > 0
        )



# ---------------------------------------------------------
# DEV gateway test messages
# ---------------------------------------------------------

def create_gateway_test_message(
    created_by: str,
    contact_name: str,
    phone: str,
    message_text: str,
    request_key: str,
) -> int:
    """
    Create and immediately queue one DEV-only gateway test.

    request_key makes this operation idempotent. If Streamlit
    submits the same request twice, the existing test message ID
    is returned instead of inserting another recipient.
    """

    created_by = created_by.strip().lower()
    contact_name = contact_name.strip()
    phone = phone.strip()
    message_text = message_text.strip()
    request_key = request_key.strip()

    if not created_by:
        raise ValueError(
            "Message creator cannot be empty."
        )

    if not contact_name:
        raise ValueError(
            "Test recipient name cannot be empty."
        )

    if not phone:
        raise ValueError(
            "Test phone number cannot be empty."
        )

    phone_digits = "".join(
        character
        for character in phone
        if character.isdigit()
    )

    if len(phone_digits) < 10:
        raise ValueError(
            "Enter a complete test phone number."
        )

    if not message_text:
        raise ValueError(
            "Test message cannot be empty."
        )

    if not request_key:
        raise ValueError(
            "Gateway test request key cannot be empty."
        )

    test_reference = (
        "DEV-TEST-"
        + secrets.token_hex(6).upper()
    )

    with _connect() as conn:

        existing = conn.execute(
            """
            SELECT message_id
            FROM messages
            WHERE is_test = TRUE
              AND request_key = %s
            LIMIT 1;
            """,
            (request_key,),
        ).fetchone()

        if existing is not None:
            return existing["message_id"]

        message_row = conn.execute(
            """
            INSERT INTO messages (
                created_by,
                message_text,
                audiences,
                status,
                is_test,
                request_key
            )
            VALUES (
                %s,
                %s,
                %s,
                'queued',
                TRUE,
                %s
            )
            ON CONFLICT DO NOTHING
            RETURNING message_id;
            """,
            (
                created_by,
                message_text,
                ["Gateway Test"],
                request_key,
            ),
        ).fetchone()

        if message_row is None:
            existing = conn.execute(
                """
                SELECT message_id
                FROM messages
                WHERE is_test = TRUE
                  AND request_key = %s
                LIMIT 1;
                """,
                (request_key,),
            ).fetchone()

            if existing is None:
                raise RuntimeError(
                    "Gateway test could not be created or recovered."
                )

            return existing["message_id"]

        message_id = message_row["message_id"]

        conn.execute(
            """
            INSERT INTO message_recipients (
                message_id,
                household_reference,
                contact_name,
                phone,
                contact_source,
                children,
                status
            )
            VALUES (
                %s,
                %s,
                %s,
                %s,
                'Manual DEV Test',
                'DEV gateway test recipient',
                'queued'
            );
            """,
            (
                message_id,
                test_reference,
                contact_name,
                phone,
            ),
        )

    return message_id

def get_gateway_test_messages(
    limit: int = 20,
) -> list[dict]:
    """
    Return recent DEV gateway test messages and their one
    manually entered recipient.
    """

    if limit < 1:
        return []

    with _connect() as conn:

        rows = conn.execute(
            """
            SELECT
                m.message_id,
                m.created_at,
                m.created_by,
                m.message_text,
                m.status,
                m.is_test,

                mr.recipient_id,
                mr.household_reference,
                mr.contact_name,
                mr.phone,
                mr.status AS recipient_status,
                mr.claimed_at,
                mr.submitted_at,
                mr.sent_at,
                mr.transport,
                mr.error_message

            FROM messages AS m

            INNER JOIN message_recipients AS mr
                ON mr.message_id = m.message_id

            WHERE m.is_test = TRUE

            ORDER BY
                m.created_at DESC,
                m.message_id DESC

            LIMIT %s;
            """,
            (
                limit,
            ),
        ).fetchall()

    return [
        dict(row)
        for row in rows
    ]


def cancel_gateway_test_message(
    message_id: int,
) -> bool:
    """
    Cancel a DEV-only test only while it is still queued.

    Claimed tests are owned by a Pixel claim token and must be
    cancelled from that Pixel. This prevents a Streamlit/phone
    race where the web app cancels an item while Android is
    preparing to send it.
    """

    with _connect() as conn:

        message = conn.execute(
            """
            SELECT
                m.message_id,
                m.is_test,
                mr.recipient_id,
                mr.status AS recipient_status
            FROM messages AS m
            INNER JOIN message_recipients AS mr
                ON mr.message_id = m.message_id
            WHERE m.message_id = %s
            FOR UPDATE OF m, mr;
            """,
            (message_id,),
        ).fetchone()

        if (
            message is None
            or not message["is_test"]
            or message["recipient_status"] != "queued"
        ):
            return False

        conn.execute(
            """
            UPDATE message_recipients
            SET
                status = 'cancelled',
                claim_token = NULL,
                error_message = NULL
            WHERE recipient_id = %s
              AND status = 'queued';
            """,
            (message["recipient_id"],),
        )

        conn.execute(
            """
            UPDATE messages
            SET status = 'cancelled'
            WHERE message_id = %s;
            """,
            (message_id,),
        )

    return True

def _refresh_message_status(
    conn: psycopg.Connection,
    message_id: int,
) -> None:
    """
    Recalculate one message's summary status from its
    recipient snapshot statuses.
    """

    rows = conn.execute(
        """
        SELECT status
        FROM message_recipients
        WHERE message_id = %s;
        """,
        (
            message_id,
        ),
    ).fetchall()

    statuses = [
        row[
            "status"
        ]
        for row in rows
    ]

    if not statuses:
        return

    if any(
        status in (
            "queued",
            "claimed",
        )
        for status in statuses
    ):
        message_status = "queued"

    elif all(
        status in (
            "submitted",
            "sent",
        )
        for status in statuses
    ):
        message_status = "completed"

    elif all(
        status == "failed"
        for status in statuses
    ):
        message_status = "failed"

    elif any(
        status in (
            "submitted",
            "sent",
            "failed",
        )
        for status in statuses
    ):
        message_status = "partial"

    elif all(
        status == "cancelled"
        for status in statuses
    ):
        message_status = "cancelled"

    else:
        return

    conn.execute(
        """
        UPDATE messages
        SET status = %s
        WHERE message_id = %s;
        """,
        (
            message_status,
            message_id,
        ),
    )


def queue_message(
    message_id: int,
) -> bool:
    """
    Lock one saved draft into the gateway queue.

    Once queued, its recipient snapshot is no longer
    editable or deletable through the normal draft path.

    Returns True when the draft was queued.
    Returns False when it was not an eligible draft.
    """

    with _connect() as conn:

        message = conn.execute(
            """
            SELECT
                message_id,
                status
            FROM messages
            WHERE message_id = %s
            FOR UPDATE;
            """,
            (
                message_id,
            ),
        ).fetchone()

        if (
            message is None
            or message[
                "status"
            ] != "draft"
        ):
            return False

        recipient_count = conn.execute(
            """
            SELECT COUNT(*) AS count
            FROM message_recipients
            WHERE message_id = %s
              AND status = 'draft';
            """,
            (
                message_id,
            ),
        ).fetchone()[
            "count"
        ]

        if recipient_count < 1:
            return False

        conn.execute(
            """
            UPDATE message_recipients
            SET
                status = 'queued',
                claimed_at = NULL,
                claim_token = NULL,
                submitted_at = NULL,
                sent_at = NULL,
                transport = NULL,
                error_message = NULL
            WHERE message_id = %s
              AND status = 'draft';
            """,
            (
                message_id,
            ),
        )

        conn.execute(
            """
            UPDATE messages
            SET status = 'queued'
            WHERE message_id = %s;
            """,
            (
                message_id,
            ),
        )

    return True


def claim_next_queued_test_recipient() -> dict | None:
    """
    Atomically reserve the next queued DEV test recipient.

    This function can never claim a real parish household because
    it requires messages.is_test = TRUE.
    """

    claim_token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)

    with _connect() as conn:

        row = conn.execute(
            """
            SELECT
                mr.recipient_id,
                mr.message_id,
                mr.household_reference,
                mr.contact_name,
                mr.phone,
                mr.contact_source,
                mr.children,
                m.message_text,
                m.audiences,
                m.is_test
            FROM message_recipients AS mr
            INNER JOIN messages AS m
                ON m.message_id = mr.message_id
            WHERE mr.status = 'queued'
              AND m.status = 'queued'
              AND m.is_test = TRUE
            ORDER BY
                m.created_at,
                m.message_id,
                mr.recipient_id
            FOR UPDATE OF mr
            SKIP LOCKED
            LIMIT 1;
            """
        ).fetchone()

        if row is None:
            return None

        recipient_id = row["recipient_id"]

        conn.execute(
            """
            UPDATE message_recipients
            SET
                status = 'claimed',
                claimed_at = %s,
                claim_token = %s
            WHERE recipient_id = %s
              AND status = 'queued';
            """,
            (now, claim_token, recipient_id),
        )

        result = dict(row)
        result["claim_token"] = claim_token
        result["claimed_at"] = now
        return result


def claim_next_queued_recipient() -> dict | None:
    """
    Atomically reserve the next queued household recipient
    for one gateway device.

    There is intentionally no automatic timeout / retry.
    If a device disappears after claiming an item, that item
    remains claimed so the system never guesses that it is
    safe to send the household a duplicate message.
    """

    claim_token = (
        secrets.token_urlsafe(
            32
        )
    )

    now = datetime.now(
        timezone.utc
    )

    with _connect() as conn:

        row = conn.execute(
            """
            SELECT
                mr.recipient_id,
                mr.message_id,
                mr.household_reference,
                mr.contact_name,
                mr.phone,
                mr.contact_source,
                mr.children,

                m.message_text,
                m.audiences,
                m.is_test

            FROM message_recipients AS mr

            INNER JOIN messages AS m
                ON m.message_id = mr.message_id

            WHERE mr.status = 'queued'
              AND m.status = 'queued'
              AND m.is_test = FALSE

            ORDER BY
                m.created_at,
                m.message_id,
                mr.recipient_id

            FOR UPDATE OF mr
            SKIP LOCKED

            LIMIT 1;
            """
        ).fetchone()

        if row is None:
            return None

        recipient_id = row[
            "recipient_id"
        ]

        conn.execute(
            """
            UPDATE message_recipients
            SET
                status = 'claimed',
                claimed_at = %s,
                claim_token = %s
            WHERE recipient_id = %s;
            """,
            (
                now,
                claim_token,
                recipient_id,
            ),
        )

        result = dict(
            row
        )

        result[
            "claim_token"
        ] = claim_token

        result[
            "claimed_at"
        ] = now

        return result


def _update_claimed_recipient(
    recipient_id: int,
    claim_token: str,
    new_status: str,
    *,
    transport: str | None = None,
    error_message: str | None = None,
) -> bool:
    """
    Update a gateway-owned recipient only when its private
    claim token matches.
    """

    claim_token = (
        claim_token
        .strip()
    )

    if not claim_token:
        return False

    now = datetime.now(
        timezone.utc
    )

    with _connect() as conn:

        recipient = conn.execute(
            """
            SELECT
                recipient_id,
                message_id,
                status
            FROM message_recipients
            WHERE recipient_id = %s
              AND claim_token = %s
            FOR UPDATE;
            """,
            (
                recipient_id,
                claim_token,
            ),
        ).fetchone()

        if recipient is None:
            return False

        current_status = recipient[
            "status"
        ]

        # Gateway callbacks can race. For example, a fast SMS SENT
        # callback may reach the API before the Android thread posts
        # the earlier SUBMITTED handoff. Treat repeat updates and a
        # late SUBMITTED after SENT as successful no-ops so a stronger
        # terminal state is never downgraded or reported as an error.
        if current_status == new_status:
            return True

        if (
            current_status == "sent"
            and new_status == "submitted"
        ):
            return True

        allowed_transitions = {
            "claimed": {
                "submitted",
                "sent",
                "failed",
            },
            "submitted": {
                "sent",
                "failed",
            },
        }

        if (
            new_status
            not in allowed_transitions.get(
                current_status,
                set(),
            )
        ):
            return False

        submitted_at = (
            now
            if new_status in (
                "submitted",
                "sent",
            )
            else None
        )

        sent_at = (
            now
            if new_status == "sent"
            else None
        )

        conn.execute(
            """
            UPDATE message_recipients
            SET
                status = %s,

                submitted_at =
                    CASE
                        WHEN %s IS NOT NULL
                            THEN COALESCE(
                                submitted_at,
                                %s
                            )
                        ELSE submitted_at
                    END,

                sent_at =
                    CASE
                        WHEN %s IS NOT NULL
                            THEN %s
                        ELSE sent_at
                    END,

                transport =
                    COALESCE(
                        %s,
                        transport
                    ),

                error_message = %s

            WHERE recipient_id = %s
              AND claim_token = %s;
            """,
            (
                new_status,

                submitted_at,
                submitted_at,

                sent_at,
                sent_at,

                transport,

                error_message,

                recipient_id,
                claim_token,
            ),
        )

        _refresh_message_status(
            conn,
            recipient[
                "message_id"
            ],
        )

    return True


def release_claimed_recipient(
    recipient_id: int,
    claim_token: str,
) -> bool:
    """
    Return one claimed real household recipient to the queue
    without sending it.

    Safety rules:
    - the private claim token must match;
    - the record must be a real household message, not a DEV test;
    - only CLAIMED may return to QUEUED;
    - submitted, sent, failed, or cancelled records can never
      be released through this path.
    """

    claim_token = claim_token.strip()

    if not claim_token:
        return False

    with _connect() as conn:

        recipient = conn.execute(
            """
            SELECT
                mr.recipient_id,
                mr.message_id,
                mr.status,
                m.is_test
            FROM message_recipients AS mr
            INNER JOIN messages AS m
                ON m.message_id = mr.message_id
            WHERE mr.recipient_id = %s
              AND mr.claim_token = %s
            FOR UPDATE OF mr;
            """,
            (
                recipient_id,
                claim_token,
            ),
        ).fetchone()

        if (
            recipient is None
            or recipient["is_test"]
            or recipient["status"] != "claimed"
        ):
            return False

        cursor = conn.execute(
            """
            UPDATE message_recipients
            SET
                status = 'queued',
                claimed_at = NULL,
                claim_token = NULL,
                error_message = NULL
            WHERE recipient_id = %s
              AND claim_token = %s
              AND status = 'claimed';
            """,
            (
                recipient_id,
                claim_token,
            ),
        )

        if cursor.rowcount != 1:
            return False

        _refresh_message_status(
            conn,
            recipient["message_id"],
        )

    return True


def cancel_claimed_test_recipient(
    recipient_id: int,
    claim_token: str,
) -> bool:
    """
    Cancel a claimed DEV test from the Pixel that owns the claim.

    Only is_test = TRUE records in CLAIMED state can transition
    this way. Submitted/sent items can never be cancelled here.
    """

    claim_token = claim_token.strip()
    if not claim_token:
        return False

    with _connect() as conn:

        recipient = conn.execute(
            """
            SELECT
                mr.recipient_id,
                mr.message_id,
                mr.status,
                m.is_test
            FROM message_recipients AS mr
            INNER JOIN messages AS m
                ON m.message_id = mr.message_id
            WHERE mr.recipient_id = %s
              AND mr.claim_token = %s
            FOR UPDATE OF mr;
            """,
            (recipient_id, claim_token),
        ).fetchone()

        if (
            recipient is None
            or not recipient["is_test"]
            or recipient["status"] != "claimed"
        ):
            return False

        conn.execute(
            """
            UPDATE message_recipients
            SET
                status = 'cancelled',
                error_message = NULL
            WHERE recipient_id = %s
              AND claim_token = %s
              AND status = 'claimed';
            """,
            (recipient_id, claim_token),
        )

        _refresh_message_status(
            conn,
            recipient["message_id"],
        )

    return True


def mark_recipient_submitted(
    recipient_id: int,
    claim_token: str,
    transport: str = "android_auto",
) -> bool:
    """
    Record that Android accepted the send request.

    For an RCS-upgraded recipient this may be the strongest
    callback available to our companion app, so SUBMITTED is
    treated as a terminal no-auto-retry state.
    """

    return _update_claimed_recipient(
        recipient_id,
        claim_token,
        "submitted",
        transport=transport,
    )


def mark_recipient_sent(
    recipient_id: int,
    claim_token: str,
    transport: str = "sms",
) -> bool:
    """
    Record a positive transport callback, such as the normal
    SMS sent PendingIntent result.
    """

    return _update_claimed_recipient(
        recipient_id,
        claim_token,
        "sent",
        transport=transport,
    )


def mark_recipient_failed(
    recipient_id: int,
    claim_token: str,
    error_message: str,
    transport: str = "android_auto",
) -> bool:
    """
    Record a definite send failure reported by the device.
    """

    return _update_claimed_recipient(
        recipient_id,
        claim_token,
        "failed",
        transport=transport,
        error_message=(
            error_message
            .strip()
            or "Unknown gateway failure"
        ),
    )


def get_gateway_queue_summary() -> dict:
    """
    Return recipient counts by gateway status.
    """

    with _connect() as conn:

        rows = conn.execute(
            """
            SELECT
                status,
                COUNT(*) AS count
            FROM message_recipients
            GROUP BY status;
            """
        ).fetchall()

    counts = {
        row[
            "status"
        ]:
            row[
                "count"
            ]
        for row in rows
    }

    return {
        "queued":
            counts.get(
                "queued",
                0,
            ),

        "claimed":
            counts.get(
                "claimed",
                0,
            ),

        "submitted":
            counts.get(
                "submitted",
                0,
            ),

        "sent":
            counts.get(
                "sent",
                0,
            ),

        "failed":
            counts.get(
                "failed",
                0,
            ),
    }

