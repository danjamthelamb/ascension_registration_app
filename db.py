# ---------------------------------------------------------
# File Name: db.py
# Last Modified: 2024-06-19
# Last Modified By: Daniel James Ardoin
# ---------------------------------------------------------

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
    Create all application tables, indexes, and migrations
    if they do not already exist.

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

                CONSTRAINT fk_children_household
                    FOREIGN KEY (household_id)
                    REFERENCES households (household_id)
                    ON DELETE CASCADE
            );
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
        # Catechetical years
        # -------------------------------------------------

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS catechetical_years (
                year_id BIGSERIAL PRIMARY KEY,

                name TEXT NOT NULL UNIQUE,
                start_year INTEGER NOT NULL UNIQUE,
                end_year INTEGER NOT NULL UNIQUE,

                status TEXT NOT NULL DEFAULT 'closed',
                renewal_open BOOLEAN NOT NULL DEFAULT FALSE,

                started_at TIMESTAMPTZ,
                started_by TEXT,

                created_at TIMESTAMPTZ NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,

                CONSTRAINT chk_catechetical_year_status
                    CHECK (
                        status IN (
                            'active',
                            'closed'
                        )
                    ),

                CONSTRAINT chk_catechetical_year_range
                    CHECK (
                        end_year = start_year + 1
                    )
            );
            """
        )

        # Only one catechetical year may be active.
        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS
                idx_one_active_catechetical_year
            ON catechetical_years (
                (status)
            )
            WHERE status = 'active';
            """
        )

        # -------------------------------------------------
        # Renewal invitation batches
        # -------------------------------------------------

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS renewal_invitation_batches (
                batch_id BIGSERIAL PRIMARY KEY,

                year_id BIGINT NOT NULL UNIQUE,

                created_at TIMESTAMPTZ NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,

                created_by TEXT NOT NULL,

                household_count INTEGER NOT NULL,

                CONSTRAINT fk_renewal_invitation_year
                    FOREIGN KEY (year_id)
                    REFERENCES catechetical_years (year_id)
                    ON DELETE RESTRICT,

                CONSTRAINT chk_renewal_invitation_household_count
                    CHECK (
                        household_count >= 0
                    )
            );
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS
                idx_renewal_invitation_year_id
            ON renewal_invitation_batches (
                year_id
            );
            """
        )

        # -------------------------------------------------
        # Renewal invitation recipients
        # -------------------------------------------------

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS
                renewal_invitation_recipients (
                    recipient_id BIGSERIAL PRIMARY KEY,

                    batch_id BIGINT NOT NULL,
                    household_id BIGINT NOT NULL,

                    email_address TEXT NOT NULL,

                    status TEXT NOT NULL
                        DEFAULT 'pending',

                    attempt_count INTEGER NOT NULL
                        DEFAULT 0,

                    sent_at TIMESTAMPTZ,
                    last_attempt_at TIMESTAMPTZ,
                    error_message TEXT,

                    created_at TIMESTAMPTZ NOT NULL
                        DEFAULT CURRENT_TIMESTAMP,

                    CONSTRAINT fk_renewal_recipient_batch
                        FOREIGN KEY (batch_id)
                        REFERENCES renewal_invitation_batches (
                            batch_id
                        )
                        ON DELETE CASCADE,

                    CONSTRAINT fk_renewal_recipient_household
                        FOREIGN KEY (household_id)
                        REFERENCES households (
                            household_id
                        )
                        ON DELETE RESTRICT,

                    CONSTRAINT uq_renewal_recipient_household
                        UNIQUE (
                            batch_id,
                            household_id
                        ),

                    CONSTRAINT chk_renewal_recipient_status
                        CHECK (
                            status IN (
                                'pending',
                                'sending',
                                'sent',
                                'failed'
                            )
                        ),

                    CONSTRAINT chk_renewal_recipient_attempt_count
                        CHECK (
                            attempt_count >= 0
                        )
                );
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS
                idx_renewal_recipient_batch_id
            ON renewal_invitation_recipients (
                batch_id
            );
            """
        )

        # -------------------------------------------------
        # Renewal invitation recovery events
        # -------------------------------------------------

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS
                renewal_invitation_recovery_events (
                    recovery_event_id BIGSERIAL PRIMARY KEY,

                    recipient_id BIGINT NOT NULL,

                    action TEXT NOT NULL,

                    attempt_count INTEGER NOT NULL,

                    resolved_at TIMESTAMPTZ NOT NULL
                        DEFAULT CURRENT_TIMESTAMP,

                    resolved_by TEXT NOT NULL,

                    CONSTRAINT fk_renewal_recovery_recipient
                        FOREIGN KEY (recipient_id)
                        REFERENCES renewal_invitation_recipients (
                            recipient_id
                        )
                        ON DELETE CASCADE,

                    CONSTRAINT chk_renewal_recovery_action
                        CHECK (
                            action IN (
                                'mark_sent',
                                'return_pending'
                            )
                        ),

                    CONSTRAINT chk_renewal_recovery_attempt
                        CHECK (
                            attempt_count >= 1
                        )
                );
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS
                idx_renewal_recovery_recipient_id
            ON renewal_invitation_recovery_events (
                recipient_id
            );
            """
        )

        # -------------------------------------------------
        # Classes
        # -------------------------------------------------

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS classes (
                class_id BIGSERIAL PRIMARY KEY,

                year_id BIGINT NOT NULL,

                group_key TEXT NOT NULL,
                display_name TEXT NOT NULL,
                category TEXT NOT NULL,

                catechists TEXT NOT NULL DEFAULT '',
                classroom TEXT NOT NULL DEFAULT '',

                created_at TIMESTAMPTZ NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,

                CONSTRAINT fk_classes_year
                    FOREIGN KEY (year_id)
                    REFERENCES catechetical_years (year_id)
                    ON DELETE RESTRICT,

                CONSTRAINT uq_class_year_group
                    UNIQUE (year_id, group_key)
            );
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS
                idx_classes_year_id
            ON classes (year_id);
            """
        )

        # -------------------------------------------------
        # Yearly enrollments
        # -------------------------------------------------

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS yearly_enrollments (
                enrollment_id BIGSERIAL PRIMARY KEY,

                child_id BIGINT NOT NULL,
                year_id BIGINT NOT NULL,

                grade TEXT NOT NULL,
                school TEXT NOT NULL,

                school_verified BOOLEAN NOT NULL
                    DEFAULT FALSE,

                enrollment_status TEXT NOT NULL
                    DEFAULT 'enrolled',

                receiving_first_communion_reconciliation
                    BOOLEAN NOT NULL DEFAULT FALSE,

                receiving_confirmation
                    BOOLEAN NOT NULL DEFAULT FALSE,

                registered_at TIMESTAMPTZ NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,

                CONSTRAINT fk_yearly_enrollment_child
                    FOREIGN KEY (child_id)
                    REFERENCES children (child_id)
                    ON DELETE RESTRICT,

                CONSTRAINT fk_yearly_enrollment_year
                    FOREIGN KEY (year_id)
                    REFERENCES catechetical_years (year_id)
                    ON DELETE RESTRICT,

                CONSTRAINT uq_child_catechetical_year
                    UNIQUE (child_id, year_id),

                CONSTRAINT chk_enrollment_status
                    CHECK (
                        enrollment_status IN (
                            'enrolled',
                            'withdrawn'
                        )
                    )
            );
            """
        )

        # -------------------------------------------------
        # Yearly enrollment class migration
        # -------------------------------------------------

        conn.execute(
            """
            ALTER TABLE yearly_enrollments
            ADD COLUMN IF NOT EXISTS
                class_id BIGINT;
            """
        )

        conn.execute(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1
                    FROM pg_constraint
                    WHERE conname =
                        'fk_yearly_enrollment_class'
                ) THEN

                    ALTER TABLE yearly_enrollments
                    ADD CONSTRAINT
                        fk_yearly_enrollment_class
                    FOREIGN KEY (class_id)
                    REFERENCES classes (class_id)
                    ON DELETE RESTRICT;

                END IF;
            END
            $$;
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS
                idx_yearly_enrollments_class_id
            ON yearly_enrollments (class_id);
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS
                idx_yearly_enrollments_year_id
            ON yearly_enrollments (year_id);
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS
                idx_yearly_enrollments_child_id
            ON yearly_enrollments (child_id);
            """
        )

        # -------------------------------------------------
        # Child sacraments
        # -------------------------------------------------

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS child_sacraments (
                child_sacrament_id BIGSERIAL PRIMARY KEY,

                child_id BIGINT NOT NULL,

                sacrament TEXT NOT NULL,

                received BOOLEAN NOT NULL
                    DEFAULT FALSE,

                received_date DATE,

                parish TEXT,
                notes TEXT,

                created_at TIMESTAMPTZ NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,

                CONSTRAINT fk_child_sacrament_child
                    FOREIGN KEY (child_id)
                    REFERENCES children (child_id)
                    ON DELETE CASCADE,

                CONSTRAINT uq_child_sacrament
                    UNIQUE (child_id, sacrament)
            );
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS
                idx_child_sacraments_child_id
            ON child_sacraments (child_id);
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

        # -------------------------------------------------
        # Active catechetical year
        # -------------------------------------------------

        active_year = conn.execute(
            """
            SELECT year_id
            FROM catechetical_years
            WHERE status = 'active';
            """
        ).fetchone()

        if active_year is None:
            raise ValueError(
                "No active catechetical year was found."
            )

        active_year_id = active_year[
            "year_id"
        ]

        # -------------------------------------------------
        # Create children and yearly enrollments
        # -------------------------------------------------

        for child in children:

            # ---------------------------------------------
            # Create permanent child record
            # ---------------------------------------------

            child_row = conn.execute(
                """
                INSERT INTO children (
                    household_id,
                    first_name,
                    middle_name,
                    last_name,
                    date_of_birth
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s
                )
                RETURNING child_id;
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
                ),
            ).fetchone()

            child_id = child_row[
                "child_id"
            ]

            # ---------------------------------------------
            # Create permanent sacramental history
            # ---------------------------------------------

            sacrament_statuses = {
                "Baptism":
                    child.get(
                        "baptism_status"
                    ),

                "First Reconciliation":
                    child.get(
                        "first_reconciliation_status"
                    ),

                "First Communion":
                    child.get(
                        "first_communion_status"
                    ),

                "Confirmation":
                    child.get(
                        "confirmation_status"
                    ),
            }

            for (
                sacrament,
                status,
            ) in sacrament_statuses.items():

                if status == "Yes":

                    conn.execute(
                        """
                        INSERT INTO child_sacraments (
                            child_id,
                            sacrament,
                            received
                        )
                        VALUES (
                            %s,
                            %s,
                            TRUE
                        )
                        ON CONFLICT (
                            child_id,
                            sacrament
                        )
                        DO UPDATE
                        SET received = TRUE;
                        """,
                        (
                            child_id,
                            sacrament,
                        ),
                    )

            # ---------------------------------------------
            # Determine class from grade
            # ---------------------------------------------

            grade = child[
                "grade"
            ]

            if grade in (
                "Pre-K",
                "K",
            ):
                group_key = (
                    "kindergarten"
                )

            elif grade in (
                "1",
                "2",
                "3",
                "4",
                "5",
            ):
                group_key = (
                    f"grade_{grade}"
                )

            elif grade in (
                "6",
                "7",
                "8",
            ):
                group_key = (
                    "edge"
                )

            elif grade in (
                "9",
                "10",
                "11",
                "12",
            ):
                group_key = (
                    "life_teen"
                )

            else:
                raise ValueError(
                    f"Invalid grade: {grade}"
                )

            class_row = conn.execute(
                """
                SELECT class_id
                FROM classes
                WHERE year_id = %s
                  AND group_key = %s;
                """,
                (
                    active_year_id,
                    group_key,
                ),
            ).fetchone()

            if class_row is None:
                raise ValueError(
                    "The class for this child's grade "
                    "could not be found."
                )

            class_id = class_row[
                "class_id"
            ]

            # ---------------------------------------------
            # Create active-year enrollment
            # ---------------------------------------------

            conn.execute(
                """
                INSERT INTO yearly_enrollments (
                    child_id,
                    year_id,
                    class_id,

                    grade,
                    school,
                    school_verified,
                    enrollment_status,

                    receiving_first_communion_reconciliation,
                    receiving_confirmation
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    TRUE,
                    'enrolled',
                    %s,
                    %s
                );
                """,
                (
                    child_id,
                    active_year_id,
                    class_id,

                    grade,

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
    Load a household and its children using the public
    Household ID.

    Annual registration fields are loaded from the
    child's enrollment in the active catechetical year.

    app.py should only call this after the household
    has passed email verification.
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
            SELECT
                c.child_id,
                c.household_id,

                c.first_name,
                c.middle_name,
                c.last_name,
                c.date_of_birth,

                ye.grade,
                ye.school,
                ye.receiving_first_communion_reconciliation,
                ye.receiving_confirmation,

                CASE
                    WHEN EXISTS (
                        SELECT 1
                        FROM child_sacraments AS cs
                        WHERE cs.child_id = c.child_id
                          AND cs.sacrament = 'Baptism'
                          AND cs.received = TRUE
                    )
                    THEN 'Yes'
                    ELSE NULL
                END AS baptism_status,

                CASE
                    WHEN EXISTS (
                        SELECT 1
                        FROM child_sacraments AS cs
                        WHERE cs.child_id = c.child_id
                          AND cs.sacrament = 'First Reconciliation'
                          AND cs.received = TRUE
                    )
                    THEN 'Yes'
                    ELSE NULL
                END AS first_reconciliation_status,

                CASE
                    WHEN EXISTS (
                        SELECT 1
                        FROM child_sacraments AS cs
                        WHERE cs.child_id = c.child_id
                          AND cs.sacrament = 'First Communion'
                          AND cs.received = TRUE
                    )
                    THEN 'Yes'
                    ELSE NULL
                END AS first_communion_status,

                CASE
                    WHEN EXISTS (
                        SELECT 1
                        FROM child_sacraments AS cs
                        WHERE cs.child_id = c.child_id
                          AND cs.sacrament = 'Confirmation'
                          AND cs.received = TRUE
                    )
                    THEN 'Yes'
                    ELSE NULL
                END AS confirmation_status

            FROM children AS c

            INNER JOIN yearly_enrollments AS ye
                ON ye.child_id = c.child_id

            INNER JOIN catechetical_years AS cy
                ON cy.year_id = ye.year_id

            WHERE c.household_id = %s
              AND cy.status = 'active'
              AND ye.enrollment_status = 'enrolled'

            ORDER BY c.child_id;
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
        # Active catechetical year
        # -------------------------------------------------

        active_year = conn.execute(
            """
            SELECT year_id
            FROM catechetical_years
            WHERE status = 'active';
            """
        ).fetchone()

        if active_year is None:
            raise ValueError(
                "No active catechetical year was found."
            )

        active_year_id = active_year[
            "year_id"
        ]

        # -------------------------------------------------
        # Children enrolled for the active year
        # -------------------------------------------------

        existing_rows = conn.execute(
            """
            SELECT ye.child_id
            FROM yearly_enrollments AS ye
            INNER JOIN children AS c
                ON c.child_id = ye.child_id
            WHERE c.household_id = %s
              AND ye.year_id = %s
              AND ye.enrollment_status = 'enrolled';
            """,
            (
                household_id,
                active_year_id,
            ),
        ).fetchall()

        existing_child_ids = {
            row["child_id"]
            for row in existing_rows
        }

        # -------------------------------------------------
        # Submitted existing child IDs
        # -------------------------------------------------

        submitted_child_ids = {
            child["child_id"]
            for child in children
            if child.get("child_id") is not None
        }

        # -------------------------------------------------
        # Withdraw removed children from active year
        # -------------------------------------------------

        children_to_withdraw = (
            existing_child_ids
            - submitted_child_ids
        )

        for child_id in children_to_withdraw:

            conn.execute(
                """
                UPDATE yearly_enrollments
                SET enrollment_status = 'withdrawn'
                WHERE child_id = %s
                  AND year_id = %s;
                """,
                (
                    child_id,
                    active_year_id,
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

                # -----------------------------------------
                # Update permanent child information
                # -----------------------------------------

                result = conn.execute(
                    """
                    UPDATE children
                    SET
                        first_name = %s,
                        middle_name = %s,
                        last_name = %s,
                        date_of_birth = %s

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

                        child_id,
                        household_id,
                    ),
                )

                if result.rowcount != 1:
                    raise ValueError(
                        "The child could not be found "
                        "in this household."
                    )

                # -----------------------------------------
                # Update permanent sacramental history
                # -----------------------------------------

                sacrament_statuses = {
                    "Baptism":
                        child.get(
                            "baptism_status"
                        ),

                    "First Reconciliation":
                        child.get(
                            "first_reconciliation_status"
                        ),

                    "First Communion":
                        child.get(
                            "first_communion_status"
                        ),

                    "Confirmation":
                        child.get(
                            "confirmation_status"
                        ),
                }

                for (
                    sacrament,
                    status,
                ) in sacrament_statuses.items():

                    if status == "Yes":

                        conn.execute(
                            """
                            INSERT INTO child_sacraments (
                                child_id,
                                sacrament,
                                received
                            )
                            VALUES (
                                %s,
                                %s,
                                TRUE
                            )
                            ON CONFLICT (
                                child_id,
                                sacrament
                            )
                            DO UPDATE
                            SET received = TRUE;
                            """,
                            (
                                child_id,
                                sacrament,
                            ),
                        )

                # -----------------------------------------
                # Determine class from grade
                # -----------------------------------------

                grade = child[
                    "grade"
                ]

                if grade in (
                    "Pre-K",
                    "K",
                ):
                    group_key = (
                        "kindergarten"
                    )

                elif grade in (
                    "1",
                    "2",
                    "3",
                    "4",
                    "5",
                ):
                    group_key = (
                        f"grade_{grade}"
                    )

                elif grade in (
                    "6",
                    "7",
                    "8",
                ):
                    group_key = (
                        "edge"
                    )

                elif grade in (
                    "9",
                    "10",
                    "11",
                    "12",
                ):
                    group_key = (
                        "life_teen"
                    )

                else:
                    raise ValueError(
                        f"Invalid grade: {grade}"
                    )

                class_row = conn.execute(
                    """
                    SELECT class_id
                    FROM classes
                    WHERE year_id = %s
                      AND group_key = %s;
                    """,
                    (
                        active_year_id,
                        group_key,
                    ),
                ).fetchone()

                if class_row is None:
                    raise ValueError(
                        "The class for this child's grade "
                        "could not be found."
                    )

                class_id = class_row[
                    "class_id"
                ]

                # -----------------------------------------
                # Update active-year enrollment
                # -----------------------------------------

                result = conn.execute(
                    """
                    UPDATE yearly_enrollments
                    SET
                        grade = %s,
                        school = %s,
                        class_id = %s,

                        receiving_first_communion_reconciliation = %s,
                        receiving_confirmation = %s

                    WHERE child_id = %s
                      AND year_id = %s;
                    """,
                    (
                        grade,

                        child[
                            "school"
                        ],

                        class_id,

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

                        child_id,
                        active_year_id,
                    ),
                )

                if result.rowcount != 1:
                    raise ValueError(
                        "The active-year enrollment for "
                        "this child could not be found."
                    )

            # ---------------------------------------------
            # New child
            # ---------------------------------------------

            else:
                # -----------------------------------------
                # Create permanent child record
                # -----------------------------------------

                child_row = conn.execute(
                    """
                    INSERT INTO children (
                        household_id,
                        first_name,
                        middle_name,
                        last_name,
                        date_of_birth
                    )
                    VALUES (
                        %s,
                        %s,
                        %s,
                        %s,
                        %s
                    )
                    RETURNING child_id;
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
                    ),
                ).fetchone()

                child_id = child_row[
                    "child_id"
                ]

                # -----------------------------------------
                # Create permanent sacramental history
                # -----------------------------------------

                sacrament_statuses = {
                    "Baptism":
                        child.get(
                            "baptism_status"
                        ),

                    "First Reconciliation":
                        child.get(
                            "first_reconciliation_status"
                        ),

                    "First Communion":
                        child.get(
                            "first_communion_status"
                        ),

                    "Confirmation":
                        child.get(
                            "confirmation_status"
                        ),
                }

                for (
                    sacrament,
                    status,
                ) in sacrament_statuses.items():

                    if status == "Yes":

                        conn.execute(
                            """
                            INSERT INTO child_sacraments (
                                child_id,
                                sacrament,
                                received
                            )
                            VALUES (
                                %s,
                                %s,
                                TRUE
                            )
                            ON CONFLICT (
                                child_id,
                                sacrament
                            )
                            DO UPDATE
                            SET received = TRUE;
                            """,
                            (
                                child_id,
                                sacrament,
                            ),
                        )

                # -----------------------------------------
                # Determine class from grade
                # -----------------------------------------

                grade = child[
                    "grade"
                ]

                if grade in (
                    "Pre-K",
                    "K",
                ):
                    group_key = (
                        "kindergarten"
                    )

                elif grade in (
                    "1",
                    "2",
                    "3",
                    "4",
                    "5",
                ):
                    group_key = (
                        f"grade_{grade}"
                    )

                elif grade in (
                    "6",
                    "7",
                    "8",
                ):
                    group_key = (
                        "edge"
                    )

                elif grade in (
                    "9",
                    "10",
                    "11",
                    "12",
                ):
                    group_key = (
                        "life_teen"
                    )

                else:
                    raise ValueError(
                        f"Invalid grade: {grade}"
                    )

                class_row = conn.execute(
                    """
                    SELECT class_id
                    FROM classes
                    WHERE year_id = %s
                      AND group_key = %s;
                    """,
                    (
                        active_year_id,
                        group_key,
                    ),
                ).fetchone()

                if class_row is None:
                    raise ValueError(
                        "The class for this child's grade "
                        "could not be found."
                    )

                class_id = class_row[
                    "class_id"
                ]

                # -----------------------------------------
                # Create active-year enrollment
                # -----------------------------------------

                conn.execute(
                    """
                    INSERT INTO yearly_enrollments (
                        child_id,
                        year_id,
                        class_id,

                        grade,
                        school,
                        school_verified,
                        enrollment_status,

                        receiving_first_communion_reconciliation,
                        receiving_confirmation
                    )
                    VALUES (
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        TRUE,
                        'enrolled',
                        %s,
                        %s
                    );
                    """,
                    (
                        child_id,
                        active_year_id,
                        class_id,

                        grade,

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
                    ),
                )


# ---------------------------------------------------------
# Admin roster
# ---------------------------------------------------------

def get_admin_roster() -> list[dict]:
    """
    Return children enrolled in the active catechetical
    year with their yearly enrollment, class, and
    household information for the administrative dashboard.
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

                ye.enrollment_id,
                ye.year_id,
                ye.grade,
                ye.school,
                ye.school_verified,
                ye.enrollment_status,

                ye.receiving_first_communion_reconciliation,
                ye.receiving_confirmation,

                cl.class_id,
                cl.group_key,
                cl.display_name AS class_display_name,
                cl.category AS class_category,
                cl.catechists,
                cl.classroom,

                cy.name AS catechetical_year,

                CASE
                    WHEN EXISTS (
                        SELECT 1
                        FROM child_sacraments AS cs
                        WHERE cs.child_id = c.child_id
                          AND cs.sacrament = 'Baptism'
                          AND cs.received = TRUE
                    )
                    THEN 'Yes'
                    ELSE NULL
                END AS baptism_status,

                CASE
                    WHEN EXISTS (
                        SELECT 1
                        FROM child_sacraments AS cs
                        WHERE cs.child_id = c.child_id
                          AND cs.sacrament = 'First Reconciliation'
                          AND cs.received = TRUE
                    )
                    THEN 'Yes'
                    ELSE NULL
                END AS first_reconciliation_status,

                CASE
                    WHEN EXISTS (
                        SELECT 1
                        FROM child_sacraments AS cs
                        WHERE cs.child_id = c.child_id
                          AND cs.sacrament = 'First Communion'
                          AND cs.received = TRUE
                    )
                    THEN 'Yes'
                    ELSE NULL
                END AS first_communion_status,

                CASE
                    WHEN EXISTS (
                        SELECT 1
                        FROM child_sacraments AS cs
                        WHERE cs.child_id = c.child_id
                          AND cs.sacrament = 'Confirmation'
                          AND cs.received = TRUE
                    )
                    THEN 'Yes'
                    ELSE NULL
                END AS confirmation_status,

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

            FROM yearly_enrollments AS ye

            INNER JOIN catechetical_years AS cy
                ON ye.year_id = cy.year_id

            INNER JOIN children AS c
                ON ye.child_id = c.child_id

            INNER JOIN households AS h
                ON c.household_id = h.household_id

            INNER JOIN classes AS cl
                ON ye.class_id = cl.class_id
               AND cl.year_id = ye.year_id

            WHERE cy.status = 'active'
              AND ye.enrollment_status = 'enrolled'

            ORDER BY
                CASE ye.grade
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
    Return the roster groups for the active catechetical
    year, including catechists and classroom assignments.
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
                cl.class_id,
                cl.year_id,
                cl.group_key,
                cl.display_name,
                cl.category,
                cl.catechists,
                cl.classroom,
                cy.name AS catechetical_year

            FROM classes AS cl

            INNER JOIN catechetical_years AS cy
                ON cl.year_id = cy.year_id

            WHERE cy.status = 'active';
            """
        ).fetchall()

    groups = [
        dict(row)
        for row in rows
    ]

    order_lookup = {
        group_key: index
        for index, group_key in enumerate(
            group_order
        )
    }

    groups.sort(
        key=lambda group: order_lookup.get(
            group["group_key"],
            999,
        )
    )

    return groups



# ---------------------------------------------------------
# Renewal invitation state
# ---------------------------------------------------------

def get_renewal_invitation_state() -> dict:
    """
    Return the current renewal-invitation state.

    Eligible households are households with at least one
    enrolled child in the catechetical year immediately
    preceding the active year who can progress to another
    grade.

    This function is read-only.
    """

    with _connect() as conn:

        # -------------------------------------------------
        # Active catechetical year
        # -------------------------------------------------

        active_year = conn.execute(
            """
            SELECT
                year_id,
                name,
                start_year,
                end_year,
                renewal_open
            FROM catechetical_years
            WHERE status = 'active';
            """
        ).fetchone()

        if active_year is None:
            raise ValueError(
                "No active catechetical year was found."
            )

        # -------------------------------------------------
        # Immediately preceding catechetical year
        # -------------------------------------------------

        previous_year = conn.execute(
            """
            SELECT
                year_id,
                name,
                start_year,
                end_year
            FROM catechetical_years
            WHERE end_year = %s;
            """,
            (
                active_year["start_year"],
            ),
        ).fetchone()

        # -------------------------------------------------
        # Existing invitation batch, if any
        # -------------------------------------------------

        batch = conn.execute(
            """
            SELECT
                batch_id,
                year_id,
                created_at,
                created_by,
                household_count
            FROM renewal_invitation_batches
            WHERE year_id = %s;
            """,
            (
                active_year["year_id"],
            ),
        ).fetchone()

        # A brand-new installation or first catechetical
        # year may legitimately have no preceding year.
        if previous_year is None:
            return {
                "active_year":
                    dict(active_year),

                "previous_year":
                    None,

                "eligible_households":
                    [],

                "eligible_household_count":
                    0,

                "batch":
                    dict(batch)
                    if batch is not None
                    else None,

                "already_sent":
                    batch is not None,
            }

        # -------------------------------------------------
        # Prior-year enrolled children
        # -------------------------------------------------

        rows = conn.execute(
            """
            SELECT
                h.household_id,
                h.household_reference,
                h.parent_a_first_name,
                h.parent_a_last_name,
                h.parent_a_email,

                c.child_id,
                c.first_name AS child_first_name,
                c.last_name AS child_last_name,

                ye.grade AS previous_grade

            FROM households AS h

            INNER JOIN children AS c
                ON c.household_id = h.household_id

            INNER JOIN yearly_enrollments AS ye
                ON ye.child_id = c.child_id

            WHERE ye.year_id = %s
              AND ye.enrollment_status = 'enrolled'

            ORDER BY
                h.household_id,
                c.child_id;
            """,
            (
                previous_year["year_id"],
            ),
        ).fetchall()

    # -----------------------------------------------------
    # Group eligible children by household
    # -----------------------------------------------------

    households = {}

    for row in rows:

        proposed_grade = get_next_grade(
            row["previous_grade"]
        )

        # 12th graders have no proposed next grade and
        # therefore do not make a household renewal-eligible.
        if proposed_grade is None:
            continue

        household_id = row["household_id"]

        if household_id not in households:
            households[household_id] = {
                "household_id":
                    household_id,

                "household_reference":
                    row["household_reference"],

                "parent_a_first_name":
                    row["parent_a_first_name"],

                "parent_a_last_name":
                    row["parent_a_last_name"],

                "parent_a_email":
                    row["parent_a_email"],

                "children":
                    [],
            }

        households[household_id]["children"].append(
            {
                "child_id":
                    row["child_id"],

                "first_name":
                    row["child_first_name"],

                "last_name":
                    row["child_last_name"],

                "previous_grade":
                    row["previous_grade"],

                "proposed_grade":
                    proposed_grade,
            }
        )

    eligible_households = list(
        households.values()
    )

    return {
        "active_year":
            dict(active_year),

        "previous_year":
            dict(previous_year),

        "eligible_households":
            eligible_households,

        "eligible_household_count":
            len(eligible_households),

        "batch":
            dict(batch)
            if batch is not None
            else None,

        "already_sent":
            batch is not None,
    }


# ---------------------------------------------------------
# Catechetical year rollover state
# ---------------------------------------------------------

def get_rollover_state() -> dict:
    """
    Return the current catechetical-year state and the
    proposed next catechetical year.

    This function is read-only. It does not perform
    a rollover or modify database data.
    """

    with _connect() as conn:

        active_year = conn.execute(
            """
            SELECT
                year_id,
                name,
                start_year,
                end_year,
                status,
                renewal_open,
                started_at,
                started_by
            FROM catechetical_years
            WHERE status = 'active';
            """
        ).fetchone()

    if active_year is None:
        raise ValueError(
            "No active catechetical year was found."
        )

    next_start_year = (
        active_year["end_year"]
    )

    next_end_year = (
        next_start_year + 1
    )

    return {
        "current_year_id":
            active_year["year_id"],

        "current_name":
            active_year["name"],

        "current_start_year":
            active_year["start_year"],

        "current_end_year":
            active_year["end_year"],

        "current_status":
            active_year["status"],

        "renewal_open":
            active_year["renewal_open"],

        "started_at":
            active_year["started_at"],

        "started_by":
            active_year["started_by"],

        "next_name":
            f"{next_start_year}-{next_end_year}",

        "next_start_year":
            next_start_year,

        "next_end_year":
            next_end_year,
    }


# ---------------------------------------------------------
# Check proposed rollover year
# ---------------------------------------------------------

def get_existing_catechetical_year(
    start_year: int,
) -> dict | None:
    """
    Return a catechetical year with the supplied start year,
    if one already exists.

    This function is read-only.
    """

    with _connect() as conn:

        year = conn.execute(
            """
            SELECT
                year_id,
                name,
                start_year,
                end_year,
                status,
                renewal_open,
                started_at,
                started_by
            FROM catechetical_years
            WHERE start_year = %s;
            """,
            (
                start_year,
            ),
        ).fetchone()

    if year is None:
        return None

    return dict(year)


# ---------------------------------------------------------
# Proposed grade for yearly renewal
# ---------------------------------------------------------

def get_next_grade(
    current_grade: str,
) -> str | None:
    """
    Return the proposed grade for a student's next
    catechetical-year registration.

    A return value of None means the student has
    completed 12th grade and should not automatically
    be proposed for renewal.
    """

    grade_progression = {
        "Pre-K": "K",
        "K": "1",
        "1": "2",
        "2": "3",
        "3": "4",
        "4": "5",
        "5": "6",
        "6": "7",
        "7": "8",
        "8": "9",
        "9": "10",
        "10": "11",
        "11": "12",
        "12": None,
    }

    current_grade = (
        current_grade
        or ""
    ).strip()

    if current_grade not in grade_progression:
        raise ValueError(
            f"Invalid grade: {current_grade}"
        )

    return grade_progression[
        current_grade
    ]


# ---------------------------------------------------------
# Load household for yearly renewal
# ---------------------------------------------------------

def get_household_for_renewal(
    household_reference: str,
) -> dict | None:
    """
    Load a household and its most recent prior-year
    enrollments for yearly renewal.

    This function is read-only. It does not create
    active-year enrollments.
    """

    household_reference = (
        household_reference
        or ""
    ).strip().upper()

    if not household_reference:
        return None

    with _connect() as conn:

        # -------------------------------------------------
        # Active catechetical year
        # -------------------------------------------------

        active_year = conn.execute(
            """
            SELECT
                year_id,
                name,
                start_year,
                end_year,
                renewal_open
            FROM catechetical_years
            WHERE status = 'active';
            """
        ).fetchone()

        if active_year is None:
            raise ValueError(
                "No active catechetical year was found."
            )

        # -------------------------------------------------
        # Household
        # -------------------------------------------------

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

        # -------------------------------------------------
        # Enrollment from immediately preceding year
        # -------------------------------------------------

        child_rows = conn.execute(
            """
            SELECT
                c.child_id,
                c.first_name,
                c.middle_name,
                c.last_name,
                c.date_of_birth,

                ye.enrollment_id,
                ye.year_id AS previous_year_id,
                cy.name AS previous_year_name,
                ye.grade AS previous_grade,
                ye.school AS previous_school,
                ye.receiving_first_communion_reconciliation,
                ye.receiving_confirmation

            FROM children AS c

            INNER JOIN yearly_enrollments AS ye
                ON ye.child_id = c.child_id

            INNER JOIN catechetical_years AS cy
                ON cy.year_id = ye.year_id

            WHERE c.household_id = %s
              AND cy.end_year = %s
              AND ye.enrollment_status = 'enrolled'

            ORDER BY
                c.child_id;
            """,
            (
                household["household_id"],
                active_year["start_year"],
            ),
        ).fetchall()

        # -------------------------------------------------
        # Children already enrolled in active year
        # -------------------------------------------------

        active_enrollment_rows = conn.execute(
            """
            SELECT
                ye.child_id,
                ye.enrollment_id,
                ye.grade,
                ye.school,
                ye.enrollment_status
            FROM yearly_enrollments AS ye

            INNER JOIN children AS c
                ON c.child_id = ye.child_id

            WHERE c.household_id = %s
              AND ye.year_id = %s
              AND ye.enrollment_status = 'enrolled';
            """,
            (
                household["household_id"],
                active_year["year_id"],
            ),
        ).fetchall()

        # -------------------------------------------------
        # Permanent sacramental history
        # -------------------------------------------------

        sacrament_rows = conn.execute(
            """
            SELECT
                cs.child_id,
                cs.sacrament,
                cs.received,
                cs.received_date,
                cs.parish,
                cs.notes
            FROM child_sacraments AS cs

            INNER JOIN children AS c
                ON c.child_id = cs.child_id

            WHERE c.household_id = %s
              AND cs.received = TRUE

            ORDER BY
                cs.child_id,
                cs.sacrament;
            """,
            (
                household["household_id"],
            ),
        ).fetchall()

    active_enrollments = {
        row["child_id"]: dict(row)
        for row in active_enrollment_rows
    }

    sacraments_by_child = {}

    for row in sacrament_rows:

        child_id = row["child_id"]

        if child_id not in sacraments_by_child:
            sacraments_by_child[child_id] = []

        sacraments_by_child[child_id].append(
            {
                "sacrament":
                    row["sacrament"],

                "received":
                    row["received"],

                "received_date":
                    row["received_date"],

                "parish":
                    row["parish"],

                "notes":
                    row["notes"],
            }
        )

    children = []

    for row in child_rows:

        child = dict(row)

        child["proposed_grade"] = (
            get_next_grade(
                child["previous_grade"]
            )
        )

        active_enrollment = (
            active_enrollments.get(
                child["child_id"]
            )
        )

        child["already_enrolled"] = (
            active_enrollment is not None
        )

        child["active_enrollment"] = (
            active_enrollment
        )

        child["sacraments"] = (
            sacraments_by_child.get(
                child["child_id"],
                [],
            )
        )

        # -------------------------------------------------
        # Determine sacramental review needs
        # -------------------------------------------------

        recorded_sacraments = {
            sacrament["sacrament"]
            for sacrament in child["sacraments"]
            if sacrament["received"]
        }

        prior_first_communion_prep = bool(
            child.get(
                "receiving_first_communion_reconciliation"
            )
        )

        prior_confirmation_prep = bool(
            child.get(
                "receiving_confirmation"
            )
        )

        child["sacrament_review"] = {
            "baptism": {
                "recorded":
                    "Baptism" in recorded_sacraments,

                "needs_history_review":
                    "Baptism" not in recorded_sacraments,
            },

            "first_reconciliation": {
                "recorded":
                    "First Reconciliation"
                    in recorded_sacraments,

                "prior_year_prep":
                    prior_first_communion_prep,

                "needs_completion_confirmation":
                    (
                        prior_first_communion_prep
                        and
                        "First Reconciliation"
                        not in recorded_sacraments
                    ),
            },

            "first_communion": {
                "recorded":
                    "First Communion"
                    in recorded_sacraments,

                "prior_year_prep":
                    prior_first_communion_prep,

                "needs_completion_confirmation":
                    (
                        prior_first_communion_prep
                        and
                        "First Communion"
                        not in recorded_sacraments
                    ),
            },

            "confirmation": {
                "recorded":
                    "Confirmation"
                    in recorded_sacraments,

                "prior_year_prep":
                    prior_confirmation_prep,

                "needs_completion_confirmation":
                    (
                        prior_confirmation_prep
                        and
                        "Confirmation"
                        not in recorded_sacraments
                    ),
            },
        }

        child["eligible_for_renewal"] = (
            child["proposed_grade"] is not None
            and not child["already_enrolled"]
        )

        children.append(
            child
        )

    return {
        "household":
            dict(household),

        "active_year":
            dict(active_year),

        "children":
            children,
    }


# ---------------------------------------------------------
# Renew existing child into active year
# ---------------------------------------------------------

def renew_existing_child(
    child_id: int,
    grade: str,
    school: str,
    receiving_first_communion_reconciliation: bool = False,
    receiving_confirmation: bool = False,
) -> dict:
    """
    Create an active-year enrollment for an existing child.

    This does not modify the child's prior-year enrollment.
    """

    grade = (
        grade
        or ""
    ).strip()

    school = (
        school
        or ""
    ).strip()

    if not grade:
        raise ValueError(
            "Grade is required."
        )

    if not school:
        raise ValueError(
            "School is required."
        )

    with _connect() as conn:

        # -------------------------------------------------
        # Active catechetical year
        # -------------------------------------------------

        active_year = conn.execute(
            """
            SELECT
                year_id,
                name,
                renewal_open
            FROM catechetical_years
            WHERE status = 'active'
            FOR UPDATE;
            """
        ).fetchone()

        if active_year is None:
            raise ValueError(
                "No active catechetical year was found."
            )

        if not active_year["renewal_open"]:
            raise ValueError(
                "Registration renewal is not currently open."
            )

        active_year_id = (
            active_year["year_id"]
        )

        # -------------------------------------------------
        # Existing child
        # -------------------------------------------------

        child = conn.execute(
            """
            SELECT
                child_id,
                first_name,
                last_name
            FROM children
            WHERE child_id = %s;
            """,
            (
                child_id,
            ),
        ).fetchone()

        if child is None:
            raise ValueError(
                "The child could not be found."
            )

        # -------------------------------------------------
        # Prevent duplicate active-year enrollment
        # -------------------------------------------------

        existing_enrollment = conn.execute(
            """
            SELECT enrollment_id
            FROM yearly_enrollments
            WHERE child_id = %s
              AND year_id = %s;
            """,
            (
                child_id,
                active_year_id,
            ),
        ).fetchone()

        if existing_enrollment is not None:
            raise ValueError(
                "This child already has a registration "
                "for the active catechetical year."
            )

        # -------------------------------------------------
        # Determine active-year class from grade
        # -------------------------------------------------

        if grade in (
            "Pre-K",
            "K",
        ):
            group_key = "kindergarten"

        elif grade in (
            "1",
            "2",
            "3",
            "4",
            "5",
        ):
            group_key = (
                f"grade_{grade}"
            )

        elif grade in (
            "6",
            "7",
            "8",
        ):
            group_key = "edge"

        elif grade in (
            "9",
            "10",
            "11",
            "12",
        ):
            group_key = "life_teen"

        else:
            raise ValueError(
                f"Invalid grade: {grade}"
            )

        class_row = conn.execute(
            """
            SELECT class_id
            FROM classes
            WHERE year_id = %s
              AND group_key = %s;
            """,
            (
                active_year_id,
                group_key,
            ),
        ).fetchone()

        if class_row is None:
            raise ValueError(
                "The class for this grade could not be found."
            )

        # -------------------------------------------------
        # Create new yearly enrollment
        # -------------------------------------------------

        enrollment = conn.execute(
            """
            INSERT INTO yearly_enrollments (
                child_id,
                year_id,
                class_id,
                grade,
                school,
                school_verified,
                enrollment_status,
                receiving_first_communion_reconciliation,
                receiving_confirmation
            )
            VALUES (
                %s,
                %s,
                %s,
                %s,
                %s,
                TRUE,
                'enrolled',
                %s,
                %s
            )
            RETURNING enrollment_id;
            """,
            (
                child_id,
                active_year_id,
                class_row["class_id"],
                grade,
                school,
                bool(
                    receiving_first_communion_reconciliation
                ),
                bool(
                    receiving_confirmation
                ),
            ),
        ).fetchone()

    return {
        "enrollment_id":
            enrollment["enrollment_id"],

        "child_id":
            child_id,

        "child_name":
            (
                f"{child['first_name']} "
                f"{child['last_name']}"
            ),

        "year_id":
            active_year_id,

        "year_name":
            active_year["name"],

        "grade":
            grade,

        "school":
            school,

        "group_key":
            group_key,
    }


# ---------------------------------------------------------
# Update household information during renewal
# ---------------------------------------------------------

def update_household_for_renewal(
    household_reference: str,
    parent_a_first_name: str,
    parent_a_last_name: str,
    parent_a_phone: str,
    parent_a_email: str,
    parent_b_first_name: str = "",
    parent_b_last_name: str = "",
    parent_b_phone: str = "",
    parent_b_email: str = "",
    address_line_1: str = "",
    address_line_2: str = "",
    city: str = "",
    state: str = "",
    zip_code: str = "",
    emergency_contact_name: str = "",
    emergency_contact_phone: str = "",
    emergency_contact_relationship: str = "",
) -> dict:
    """
    Update an existing household's contact information
    during yearly renewal.

    This function does not create or modify enrollments.
    """

    household_reference = (
        household_reference
        or ""
    ).strip().upper()

    if not household_reference:
        raise ValueError(
            "Household reference is required."
        )

    # -------------------------------------------------
    # Normalize values
    # -------------------------------------------------

    values = {
        "parent_a_first_name":
            (parent_a_first_name or "").strip(),

        "parent_a_last_name":
            (parent_a_last_name or "").strip(),

        "parent_a_phone":
            (parent_a_phone or "").strip(),

        "parent_a_email":
            (parent_a_email or "").strip(),

        "parent_b_first_name":
            (parent_b_first_name or "").strip(),

        "parent_b_last_name":
            (parent_b_last_name or "").strip(),

        "parent_b_phone":
            (parent_b_phone or "").strip(),

        "parent_b_email":
            (parent_b_email or "").strip(),

        "address_line_1":
            (address_line_1 or "").strip(),

        "address_line_2":
            (address_line_2 or "").strip(),

        "city":
            (city or "").strip(),

        "state":
            (state or "").strip().upper(),

        "zip_code":
            (zip_code or "").strip(),

        "emergency_contact_name":
            (emergency_contact_name or "").strip(),

        "emergency_contact_phone":
            (emergency_contact_phone or "").strip(),

        "emergency_contact_relationship":
            (
                emergency_contact_relationship
                or ""
            ).strip(),
    }

    # -------------------------------------------------
    # Required household fields
    # -------------------------------------------------

    required_fields = {
        "Parent/Guardian first name":
            values["parent_a_first_name"],

        "Parent/Guardian last name":
            values["parent_a_last_name"],

        "Parent/Guardian phone":
            values["parent_a_phone"],

        "Parent/Guardian email":
            values["parent_a_email"],

        "Address":
            values["address_line_1"],

        "City":
            values["city"],

        "State":
            values["state"],

        "ZIP code":
            values["zip_code"],

        "Emergency contact name":
            values["emergency_contact_name"],

        "Emergency contact phone":
            values["emergency_contact_phone"],

        "Emergency contact relationship":
            values["emergency_contact_relationship"],
    }

    for label, value in required_fields.items():

        if not value:
            raise ValueError(
                f"{label} is required."
            )

    # -------------------------------------------------
    # Update household
    # -------------------------------------------------

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
            raise ValueError(
                "The household could not be found."
            )

        conn.execute(
            """
            UPDATE households
            SET
                parent_a_first_name = %s,
                parent_a_last_name = %s,
                parent_a_phone = %s,
                parent_a_email = %s,

                parent_b_first_name = %s,
                parent_b_last_name = %s,
                parent_b_phone = %s,
                parent_b_email = %s,

                address_line_1 = %s,
                address_line_2 = %s,
                city = %s,
                state = %s,
                zip_code = %s,

                emergency_contact_name = %s,
                emergency_contact_phone = %s,
                emergency_contact_relationship = %s

            WHERE household_id = %s;
            """,
            (
                values["parent_a_first_name"],
                values["parent_a_last_name"],
                values["parent_a_phone"],
                values["parent_a_email"],

                values["parent_b_first_name"],
                values["parent_b_last_name"],
                values["parent_b_phone"],
                values["parent_b_email"],

                values["address_line_1"],
                values["address_line_2"],
                values["city"],
                values["state"],
                values["zip_code"],

                values["emergency_contact_name"],
                values["emergency_contact_phone"],
                values[
                    "emergency_contact_relationship"
                ],

                household["household_id"],
            ),
        )

    return {
        "household_reference":
            household_reference,

        "household_id":
            household["household_id"],

        "updated":
            True,
    }


# ---------------------------------------------------------
# Update child information during renewal
# ---------------------------------------------------------

def update_child_for_renewal(
    household_reference: str,
    child_id: int,
    first_name: str,
    middle_name: str,
    last_name: str,
    date_of_birth,
) -> dict:
    """
    Update permanent identity information for an existing
    child during yearly renewal.

    This function does not modify yearly enrollment data.
    """

    household_reference = (
        household_reference
        or ""
    ).strip().upper()

    first_name = (
        first_name
        or ""
    ).strip()

    middle_name = (
        middle_name
        or ""
    ).strip()

    last_name = (
        last_name
        or ""
    ).strip()

    if not household_reference:
        raise ValueError(
            "Household reference is required."
        )

    if not first_name:
        raise ValueError(
            "Child first name is required."
        )

    if not last_name:
        raise ValueError(
            "Child last name is required."
        )

    if date_of_birth is None:
        raise ValueError(
            "Child date of birth is required."
        )

    with _connect() as conn:

        # -------------------------------------------------
        # Confirm household
        # -------------------------------------------------

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
            raise ValueError(
                "The household could not be found."
            )

        # -------------------------------------------------
        # Confirm child belongs to household
        # -------------------------------------------------

        child = conn.execute(
            """
            SELECT child_id
            FROM children
            WHERE child_id = %s
              AND household_id = %s;
            """,
            (
                child_id,
                household["household_id"],
            ),
        ).fetchone()

        if child is None:
            raise ValueError(
                "The child could not be found "
                "in this household."
            )

        # -------------------------------------------------
        # Update permanent child information
        # -------------------------------------------------

        conn.execute(
            """
            UPDATE children
            SET
                first_name = %s,
                middle_name = %s,
                last_name = %s,
                date_of_birth = %s
            WHERE child_id = %s;
            """,
            (
                first_name,
                middle_name,
                last_name,
                date_of_birth,
                child_id,
            ),
        )

    return {
        "household_reference":
            household_reference,

        "child_id":
            child_id,

        "first_name":
            first_name,

        "middle_name":
            middle_name,

        "last_name":
            last_name,

        "date_of_birth":
            date_of_birth,

        "updated":
            True,
    }


# ---------------------------------------------------------
# Record sacrament during renewal
# ---------------------------------------------------------

def record_sacrament_for_renewal(
    household_reference: str,
    child_id: int,
    sacrament: str,
    received_date=None,
    parish: str = "",
    notes: str = "",
) -> dict:
    """
    Record a sacrament as received for an existing child
    during yearly renewal.

    This function is additive only. It does not remove
    existing sacramental history.
    """

    household_reference = (
        household_reference
        or ""
    ).strip().upper()

    sacrament = (
        sacrament
        or ""
    ).strip()

    parish = (
        parish
        or ""
    ).strip()

    notes = (
        notes
        or ""
    ).strip()

    if not household_reference:
        raise ValueError(
            "Household reference is required."
        )

    allowed_sacraments = {
        "Baptism",
        "First Reconciliation",
        "First Communion",
        "Confirmation",
    }

    if sacrament not in allowed_sacraments:
        raise ValueError(
            f"Invalid sacrament: {sacrament}"
        )

    with _connect() as conn:

        # -------------------------------------------------
        # Confirm household
        # -------------------------------------------------

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
            raise ValueError(
                "The household could not be found."
            )

        # -------------------------------------------------
        # Confirm child belongs to household
        # -------------------------------------------------

        child = conn.execute(
            """
            SELECT
                child_id,
                first_name,
                last_name
            FROM children
            WHERE child_id = %s
              AND household_id = %s;
            """,
            (
                child_id,
                household["household_id"],
            ),
        ).fetchone()

        if child is None:
            raise ValueError(
                "The child could not be found "
                "in this household."
            )

        # -------------------------------------------------
        # Record permanent sacramental history
        # -------------------------------------------------

        conn.execute(
            """
            INSERT INTO child_sacraments (
                child_id,
                sacrament,
                received,
                received_date,
                parish,
                notes
            )
            VALUES (
                %s,
                %s,
                TRUE,
                %s,
                %s,
                %s
            )

            ON CONFLICT (
                child_id,
                sacrament
            )
            DO UPDATE
            SET
                received = TRUE,

                received_date = COALESCE(
                    EXCLUDED.received_date,
                    child_sacraments.received_date
                ),

                parish = CASE
                    WHEN EXCLUDED.parish <> ''
                    THEN EXCLUDED.parish
                    ELSE child_sacraments.parish
                END,

                notes = CASE
                    WHEN EXCLUDED.notes <> ''
                    THEN EXCLUDED.notes
                    ELSE child_sacraments.notes
                END;
            """,
            (
                child_id,
                sacrament,
                received_date,
                parish,
                notes,
            ),
        )

    return {
        "household_reference":
            household_reference,

        "child_id":
            child_id,

        "child_name":
            (
                f"{child['first_name']} "
                f"{child['last_name']}"
            ),

        "sacrament":
            sacrament,

        "received":
            True,

        "received_date":
            received_date,

        "parish":
            parish,

        "notes":
            notes,
    }

# ---------------------------------------------------------
# Submit complete household renewal
# ---------------------------------------------------------

def submit_household_renewal(
    household_reference: str,
    household: dict,
    children: list[dict],
) -> dict:
    """
    Submit a complete yearly household renewal.

    The final implementation will update household information,
    child information, sacramental history, and active-year
    enrollments in one database transaction.

    This initial step validates the submission only.
    """

    household_reference = (
        household_reference
        or ""
    ).strip().upper()

    if not household_reference:
        raise ValueError(
            "Household reference is required."
        )

    if not household:
        raise ValueError(
            "Household information is required."
        )

    if not children:
        raise ValueError(
            "At least one child must be included "
            "in the renewal submission."
        )

    for child in children:

        child_id = child.get(
            "child_id"
        )

        if child_id is None:
            raise ValueError(
                "Each existing child must have a child_id."
            )

    with _connect() as conn:

        # ---------------------------------------------
        # Lock and validate the active catechetical year
        # ---------------------------------------------

        active_year = conn.execute(
            """
            SELECT
                year_id,
                name,
                start_year,
                end_year,
                renewal_open
            FROM catechetical_years
            WHERE status = 'active'
            FOR UPDATE;
            """
        ).fetchone()

        if active_year is None:
            raise ValueError(
                "No active catechetical year exists."
            )

        if not active_year["renewal_open"]:
            raise ValueError(
                "Renewal is not currently open."
            )

        # ---------------------------------------------
        # Lock and validate the household
        # ---------------------------------------------

        household_row = conn.execute(
            """
            SELECT
                household_id,
                household_reference
            FROM households
            WHERE UPPER(household_reference) = %s
            FOR UPDATE;
            """,
            (
                household_reference,
            ),
        ).fetchone()

        if household_row is None:
            raise ValueError(
                "Household not found."
            )

        household_id = household_row[
            "household_id"
        ]

        # ---------------------------------------------
        # Normalize submitted household information
        # ---------------------------------------------

        household_values = {
            "parent_a_first_name":
                (
                    household.get(
                        "parent_a_first_name"
                    )
                    or ""
                ).strip(),

            "parent_a_last_name":
                (
                    household.get(
                        "parent_a_last_name"
                    )
                    or ""
                ).strip(),

            "parent_a_phone":
                (
                    household.get(
                        "parent_a_phone"
                    )
                    or ""
                ).strip(),

            "parent_a_email":
                (
                    household.get(
                        "parent_a_email"
                    )
                    or ""
                ).strip(),

            "parent_b_first_name":
                (
                    household.get(
                        "parent_b_first_name"
                    )
                    or ""
                ).strip(),

            "parent_b_last_name":
                (
                    household.get(
                        "parent_b_last_name"
                    )
                    or ""
                ).strip(),

            "parent_b_phone":
                (
                    household.get(
                        "parent_b_phone"
                    )
                    or ""
                ).strip(),

            "parent_b_email":
                (
                    household.get(
                        "parent_b_email"
                    )
                    or ""
                ).strip(),

            "address_line_1":
                (
                    household.get(
                        "address_line_1"
                    )
                    or ""
                ).strip(),

            "address_line_2":
                (
                    household.get(
                        "address_line_2"
                    )
                    or ""
                ).strip(),

            "city":
                (
                    household.get(
                        "city"
                    )
                    or ""
                ).strip(),

            "state":
                (
                    household.get(
                        "state"
                    )
                    or ""
                ).strip().upper(),

            "zip_code":
                (
                    household.get(
                        "zip_code"
                    )
                    or ""
                ).strip(),

            "emergency_contact_name":
                (
                    household.get(
                        "emergency_contact_name"
                    )
                    or ""
                ).strip(),

            "emergency_contact_phone":
                (
                    household.get(
                        "emergency_contact_phone"
                    )
                    or ""
                ).strip(),

            "emergency_contact_relationship":
                (
                    household.get(
                        "emergency_contact_relationship"
                    )
                    or ""
                ).strip(),
        }

        # ---------------------------------------------
        # Validate required household information
        # ---------------------------------------------

        required_household_fields = {
            "Parent/Guardian first name":
                household_values[
                    "parent_a_first_name"
                ],

            "Parent/Guardian last name":
                household_values[
                    "parent_a_last_name"
                ],

            "Parent/Guardian phone":
                household_values[
                    "parent_a_phone"
                ],

            "Parent/Guardian email":
                household_values[
                    "parent_a_email"
                ],

            "Address":
                household_values[
                    "address_line_1"
                ],

            "City":
                household_values[
                    "city"
                ],

            "State":
                household_values[
                    "state"
                ],

            "ZIP code":
                household_values[
                    "zip_code"
                ],

            "Emergency contact name":
                household_values[
                    "emergency_contact_name"
                ],

            "Emergency contact phone":
                household_values[
                    "emergency_contact_phone"
                ],

            "Emergency contact relationship":
                household_values[
                    "emergency_contact_relationship"
                ],
        }

        for (
            label,
            value,
        ) in required_household_fields.items():

            if not value:
                raise ValueError(
                    f"{label} is required."
                )

        # ---------------------------------------------
        # Update household information
        # ---------------------------------------------

        conn.execute(
            """
            UPDATE households
            SET
                parent_a_first_name = %s,
                parent_a_last_name = %s,
                parent_a_phone = %s,
                parent_a_email = %s,

                parent_b_first_name = %s,
                parent_b_last_name = %s,
                parent_b_phone = %s,
                parent_b_email = %s,

                address_line_1 = %s,
                address_line_2 = %s,
                city = %s,
                state = %s,
                zip_code = %s,

                emergency_contact_name = %s,
                emergency_contact_phone = %s,
                emergency_contact_relationship = %s

            WHERE household_id = %s;
            """,
            (
                household_values[
                    "parent_a_first_name"
                ],

                household_values[
                    "parent_a_last_name"
                ],

                household_values[
                    "parent_a_phone"
                ],

                household_values[
                    "parent_a_email"
                ],

                household_values[
                    "parent_b_first_name"
                ],

                household_values[
                    "parent_b_last_name"
                ],

                household_values[
                    "parent_b_phone"
                ],

                household_values[
                    "parent_b_email"
                ],

                household_values[
                    "address_line_1"
                ],

                household_values[
                    "address_line_2"
                ],

                household_values[
                    "city"
                ],

                household_values[
                    "state"
                ],

                household_values[
                    "zip_code"
                ],

                household_values[
                    "emergency_contact_name"
                ],

                household_values[
                    "emergency_contact_phone"
                ],

                household_values[
                    "emergency_contact_relationship"
                ],

                household_id,
            ),
        )

        # ---------------------------------------------
        # Confirm every submitted child belongs
        # to this household
        # ---------------------------------------------

        for child in children:

            child_id = int(
                child["child_id"]
            )

            # -----------------------------------------
            # Confirm child belongs to household
            # -----------------------------------------

            child_row = conn.execute(
                """
                SELECT
                    child_id,
                    first_name,
                    middle_name,
                    last_name,
                    date_of_birth
                FROM children
                WHERE child_id = %s
                  AND household_id = %s
                FOR UPDATE;
                """,
                (
                    child_id,
                    household_id,
                ),
            ).fetchone()

            if child_row is None:
                raise ValueError(
                    f"Child {child_id} does not belong "
                    "to this household."
                )

            # -----------------------------------------
            # Normalize permanent child information
            # -----------------------------------------

            first_name = (
                child.get(
                    "first_name"
                )
                or ""
            ).strip()

            middle_name = (
                child.get(
                    "middle_name"
                )
                or ""
            ).strip()

            last_name = (
                child.get(
                    "last_name"
                )
                or ""
            ).strip()

            date_of_birth = child.get(
                "date_of_birth"
            )

            # -----------------------------------------
            # Validate permanent child information
            # -----------------------------------------

            if not first_name:
                raise ValueError(
                    f"First name is required "
                    f"for child {child_id}."
                )

            if not last_name:
                raise ValueError(
                    f"Last name is required "
                    f"for child {child_id}."
                )

            if date_of_birth is None:
                raise ValueError(
                    f"Date of birth is required "
                    f"for child {child_id}."
                )

            # -----------------------------------------
            # Update permanent child information
            # -----------------------------------------

            result = conn.execute(
                """
                UPDATE children
                SET
                    first_name = %s,
                    middle_name = %s,
                    last_name = %s,
                    date_of_birth = %s
                WHERE child_id = %s
                  AND household_id = %s;
                """,
                (
                    first_name,
                    middle_name,
                    last_name,
                    date_of_birth,
                    child_id,
                    household_id,
                ),
            )

            if result.rowcount != 1:
                raise ValueError(
                    f"Child {child_id} could not be updated."
                )

            # -----------------------------------------
            # Record newly confirmed sacramental history
            # -----------------------------------------

            sacraments_to_record = child.get(
                "sacraments_to_record",
                [],
            )

            if sacraments_to_record is None:
                sacraments_to_record = []

            if not isinstance(
                sacraments_to_record,
                list,
            ):
                raise ValueError(
                    f"Sacramental history for child "
                    f"{child_id} must be a list."
                )

            allowed_sacraments = {
                "Baptism",
                "First Reconciliation",
                "First Communion",
                "Confirmation",
            }

            for sacrament_data in sacraments_to_record:

                if not isinstance(
                    sacrament_data,
                    dict,
                ):
                    raise ValueError(
                        f"Each sacrament for child "
                        f"{child_id} must be submitted "
                        "as a dictionary."
                    )

                sacrament = (
                    sacrament_data.get(
                        "sacrament"
                    )
                    or ""
                ).strip()

                received_date = (
                    sacrament_data.get(
                        "received_date"
                    )
                )

                parish = (
                    sacrament_data.get(
                        "parish"
                    )
                    or ""
                ).strip()

                notes = (
                    sacrament_data.get(
                        "notes"
                    )
                    or ""
                ).strip()

                if sacrament not in allowed_sacraments:
                    raise ValueError(
                        f"Invalid sacrament for child "
                        f"{child_id}: {sacrament}"
                    )

                conn.execute(
                    """
                    INSERT INTO child_sacraments (
                        child_id,
                        sacrament,
                        received,
                        received_date,
                        parish,
                        notes
                    )
                    VALUES (
                        %s,
                        %s,
                        TRUE,
                        %s,
                        %s,
                        %s
                    )

                    ON CONFLICT (
                        child_id,
                        sacrament
                    )
                    DO UPDATE
                    SET
                        received = TRUE,

                        received_date = COALESCE(
                            EXCLUDED.received_date,
                            child_sacraments.received_date
                        ),

                        parish = CASE
                            WHEN EXCLUDED.parish <> ''
                            THEN EXCLUDED.parish
                            ELSE child_sacraments.parish
                        END,

                        notes = CASE
                            WHEN EXCLUDED.notes <> ''
                            THEN EXCLUDED.notes
                            ELSE child_sacraments.notes
                        END;
                    """,
                    (
                        child_id,
                        sacrament,
                        received_date,
                        parish,
                        notes,
                    ),
                )

            # -----------------------------------------
            # Validate annual enrollment information
            # -----------------------------------------

            grade = (
                child.get(
                    "grade"
                )
                or ""
            ).strip()

            school = (
                child.get(
                    "school"
                )
                or ""
            ).strip()

            receiving_first_communion_reconciliation = bool(
                child.get(
                    "receiving_first_communion_reconciliation",
                    False,
                )
            )

            receiving_confirmation = bool(
                child.get(
                    "receiving_confirmation",
                    False,
                )
            )

            if not grade:
                raise ValueError(
                    f"Grade is required "
                    f"for child {child_id}."
                )

            if not school:
                raise ValueError(
                    f"School is required "
                    f"for child {child_id}."
                )

            # -----------------------------------------
            # Check for existing active-year enrollment
            # -----------------------------------------

            existing_enrollment = conn.execute(
                """
                SELECT
                    enrollment_id,
                    grade,
                    school
                FROM yearly_enrollments
                WHERE child_id = %s
                  AND year_id = %s;
                """,
                (
                    child_id,
                    active_year["year_id"],
                ),
            ).fetchone()

            if existing_enrollment is not None:
                continue

            # -----------------------------------------
            # Determine class from grade
            # -----------------------------------------

            if grade in (
                "Pre-K",
                "K",
            ):
                group_key = "kindergarten"

            elif grade in (
                "1",
                "2",
                "3",
                "4",
                "5",
            ):
                group_key = (
                    f"grade_{grade}"
                )

            elif grade in (
                "6",
                "7",
                "8",
            ):
                group_key = "edge"

            elif grade in (
                "9",
                "10",
                "11",
                "12",
            ):
                group_key = "life_teen"

            else:
                raise ValueError(
                    f"Invalid grade: {grade}"
                )

            # -----------------------------------------
            # Find active-year class
            # -----------------------------------------

            class_row = conn.execute(
                """
                SELECT class_id
                FROM classes
                WHERE year_id = %s
                  AND group_key = %s;
                """,
                (
                    active_year["year_id"],
                    group_key,
                ),
            ).fetchone()

            if class_row is None:
                raise ValueError(
                    f"The class for grade {grade} "
                    "could not be found."
                )

            # -----------------------------------------
            # Create active-year enrollment
            # -----------------------------------------

            conn.execute(
                """
                INSERT INTO yearly_enrollments (
                    child_id,
                    year_id,
                    class_id,
                    grade,
                    school,
                    school_verified,
                    enrollment_status,
                    receiving_first_communion_reconciliation,
                    receiving_confirmation
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    TRUE,
                    'enrolled',
                    %s,
                    %s
                );
                """,
                (
                    child_id,
                    active_year["year_id"],
                    class_row["class_id"],
                    grade,
                    school,
                    receiving_first_communion_reconciliation,
                    receiving_confirmation,
                ),
            )

    return {
        "household_reference":
            household_reference,

        "year_id":
            active_year["year_id"],

        "year":
            active_year["name"],

        "validated":
            True,

        "children_received":
            len(children),
    }

# ---------------------------------------------------------
# Renew household into active catechetical year
# ---------------------------------------------------------

def renew_household(
    household_reference: str,
    children: list[dict],
) -> dict:
    """
    Renew selected existing children in a household into
    the active catechetical year.

    Existing active-year enrollments are left unchanged.
    New enrollments are created in one transaction.
    """

    household_reference = (
        household_reference
        or ""
    ).strip().upper()

    if not household_reference:
        raise ValueError(
            "Household reference is required."
        )

    if not children:
        raise ValueError(
            "At least one child must be selected for renewal."
        )

    with _connect() as conn:

        # -------------------------------------------------
        # Active catechetical year
        # -------------------------------------------------

        active_year = conn.execute(
            """
            SELECT
                year_id,
                name,
                renewal_open
            FROM catechetical_years
            WHERE status = 'active'
            FOR UPDATE;
            """
        ).fetchone()

        if active_year is None:
            raise ValueError(
                "No active catechetical year was found."
            )

        if not active_year["renewal_open"]:
            raise ValueError(
                "Registration renewal is not currently open."
            )

        active_year_id = (
            active_year["year_id"]
        )

        # -------------------------------------------------
        # Household
        # -------------------------------------------------

        household = conn.execute(
            """
            SELECT
                household_id,
                household_reference
            FROM households
            WHERE household_reference = %s;
            """,
            (
                household_reference,
            ),
        ).fetchone()

        if household is None:
            raise ValueError(
                "The household could not be found."
            )

        household_id = (
            household["household_id"]
        )

        results = []

        # -------------------------------------------------
        # Process selected children
        # -------------------------------------------------

        for child_data in children:

            child_id = child_data.get(
                "child_id"
            )

            grade = (
                child_data.get(
                    "grade"
                )
                or ""
            ).strip()

            school = (
                child_data.get(
                    "school"
                )
                or ""
            ).strip()

            receiving_first_communion_reconciliation = bool(
                child_data.get(
                    "receiving_first_communion_reconciliation",
                    False,
                )
            )

            receiving_confirmation = bool(
                child_data.get(
                    "receiving_confirmation",
                    False,
                )
            )

            if child_id is None:
                raise ValueError(
                    "Each child must have a child_id."
                )

            if not grade:
                raise ValueError(
                    "Grade is required for each child."
                )

            if not school:
                raise ValueError(
                    "School is required for each child."
                )

            # ---------------------------------------------
            # Confirm child belongs to this household
            # ---------------------------------------------

            child = conn.execute(
                """
                SELECT
                    child_id,
                    first_name,
                    last_name
                FROM children
                WHERE child_id = %s
                  AND household_id = %s;
                """,
                (
                    child_id,
                    household_id,
                ),
            ).fetchone()

            if child is None:
                raise ValueError(
                    "A selected child does not belong "
                    "to this household."
                )

            # ---------------------------------------------
            # Check for existing active-year enrollment
            # ---------------------------------------------

            existing_enrollment = conn.execute(
                """
                SELECT
                    enrollment_id,
                    grade,
                    school
                FROM yearly_enrollments
                WHERE child_id = %s
                  AND year_id = %s;
                """,
                (
                    child_id,
                    active_year_id,
                ),
            ).fetchone()

            if existing_enrollment is not None:

                results.append(
                    {
                        "child_id":
                            child_id,

                        "child_name":
                            (
                                f"{child['first_name']} "
                                f"{child['last_name']}"
                            ),

                        "status":
                            "already_enrolled",

                        "enrollment_id":
                            existing_enrollment[
                                "enrollment_id"
                            ],

                        "grade":
                            existing_enrollment[
                                "grade"
                            ],

                        "school":
                            existing_enrollment[
                                "school"
                            ],
                    }
                )

                continue

            # ---------------------------------------------
            # Determine class from grade
            # ---------------------------------------------

            if grade in (
                "Pre-K",
                "K",
            ):
                group_key = "kindergarten"

            elif grade in (
                "1",
                "2",
                "3",
                "4",
                "5",
            ):
                group_key = (
                    f"grade_{grade}"
                )

            elif grade in (
                "6",
                "7",
                "8",
            ):
                group_key = "edge"

            elif grade in (
                "9",
                "10",
                "11",
                "12",
            ):
                group_key = "life_teen"

            else:
                raise ValueError(
                    f"Invalid grade: {grade}"
                )

            class_row = conn.execute(
                """
                SELECT class_id
                FROM classes
                WHERE year_id = %s
                  AND group_key = %s;
                """,
                (
                    active_year_id,
                    group_key,
                ),
            ).fetchone()

            if class_row is None:
                raise ValueError(
                    "The class for this grade "
                    "could not be found."
                )

            # ---------------------------------------------
            # Create active-year enrollment
            # ---------------------------------------------

            enrollment = conn.execute(
                """
                INSERT INTO yearly_enrollments (
                    child_id,
                    year_id,
                    class_id,
                    grade,
                    school,
                    school_verified,
                    enrollment_status,
                    receiving_first_communion_reconciliation,
                    receiving_confirmation
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    TRUE,
                    'enrolled',
                    %s,
                    %s
                )
                RETURNING enrollment_id;
                """,
                (
                    child_id,
                    active_year_id,
                    class_row["class_id"],
                    grade,
                    school,
                    receiving_first_communion_reconciliation,
                    receiving_confirmation,
                ),
            ).fetchone()

            results.append(
                {
                    "child_id":
                        child_id,

                    "child_name":
                        (
                            f"{child['first_name']} "
                            f"{child['last_name']}"
                        ),

                    "status":
                        "renewed",

                    "enrollment_id":
                        enrollment["enrollment_id"],

                    "grade":
                        grade,

                    "school":
                        school,

                    "group_key":
                        group_key,
                }
            )

    return {
        "household_reference":
            household_reference,

        "year_id":
            active_year_id,

        "year_name":
            active_year["name"],

        "children":
            results,
    }


# ---------------------------------------------------------
# Create renewal invitation batch
# ---------------------------------------------------------

def create_renewal_invitation_batch(
    created_by: str,
) -> dict:
    """
    Create the renewal invitation batch for the active
    catechetical year.

    This function:
        - requires renewal to be open
        - uses only the immediately preceding year
        - excludes children who have completed 12th grade
        - creates one recipient per eligible household
        - creates the batch and recipients atomically
        - does not send any email

    Only one invitation batch may exist per
    catechetical year.
    """

    created_by = (
        created_by
        or ""
    ).strip()

    if not created_by:
        raise ValueError(
            "The administrator creating the invitation "
            "batch could not be identified."
        )

    with _connect() as conn:

        # -------------------------------------------------
        # Active catechetical year
        # -------------------------------------------------

        active_year = conn.execute(
            """
            SELECT
                year_id,
                name,
                start_year,
                end_year,
                renewal_open
            FROM catechetical_years
            WHERE status = 'active'
            FOR UPDATE;
            """
        ).fetchone()

        if active_year is None:
            raise ValueError(
                "No active catechetical year was found."
            )

        if not active_year["renewal_open"]:
            raise ValueError(
                "Registration renewal is not currently open."
            )

        # -------------------------------------------------
        # Prevent a second batch for this year
        # -------------------------------------------------

        existing_batch = conn.execute(
            """
            SELECT
                batch_id,
                created_at,
                created_by,
                household_count
            FROM renewal_invitation_batches
            WHERE year_id = %s;
            """,
            (
                active_year["year_id"],
            ),
        ).fetchone()

        if existing_batch is not None:
            raise ValueError(
                "A renewal invitation batch already exists "
                f"for {active_year['name']}."
            )

        # -------------------------------------------------
        # Immediately preceding catechetical year
        # -------------------------------------------------

        previous_year = conn.execute(
            """
            SELECT
                year_id,
                name,
                start_year,
                end_year
            FROM catechetical_years
            WHERE end_year = %s;
            """,
            (
                active_year["start_year"],
            ),
        ).fetchone()

        if previous_year is None:
            raise ValueError(
                "The immediately preceding catechetical "
                "year could not be found."
            )

        # -------------------------------------------------
        # Prior-year enrolled children
        # -------------------------------------------------

        rows = conn.execute(
            """
            SELECT
                h.household_id,
                h.household_reference,
                h.parent_a_email,

                c.child_id,

                ye.grade AS previous_grade

            FROM households AS h

            INNER JOIN children AS c
                ON c.household_id = h.household_id

            INNER JOIN yearly_enrollments AS ye
                ON ye.child_id = c.child_id

            WHERE ye.year_id = %s
              AND ye.enrollment_status = 'enrolled'

            ORDER BY
                h.household_id,
                c.child_id;
            """,
            (
                previous_year["year_id"],
            ),
        ).fetchall()

        # -------------------------------------------------
        # Determine eligible households
        # -------------------------------------------------

        eligible_households = {}

        for row in rows:

            proposed_grade = get_next_grade(
                row["previous_grade"]
            )

            if proposed_grade is None:
                continue

            household_id = row["household_id"]

            if household_id not in eligible_households:
                eligible_households[household_id] = {
                    "household_id":
                        household_id,

                    "household_reference":
                        row["household_reference"],

                    "email_address":
                        (
                            row["parent_a_email"]
                            or ""
                        ).strip(),
                }

        if not eligible_households:
            raise ValueError(
                "No households are eligible for renewal "
                "invitations."
            )

        # -------------------------------------------------
        # Validate recipient email addresses
        # -------------------------------------------------

        missing_email_households = [
            household["household_reference"]
            for household
            in eligible_households.values()
            if not household["email_address"]
        ]

        if missing_email_households:
            raise ValueError(
                "Renewal invitation batch was not created "
                "because one or more eligible households "
                "do not have a primary email address."
            )

        # -------------------------------------------------
        # Create batch
        # -------------------------------------------------

        batch = conn.execute(
            """
            INSERT INTO renewal_invitation_batches (
                year_id,
                created_by,
                household_count
            )
            VALUES (
                %s,
                %s,
                %s
            )
            RETURNING
                batch_id,
                year_id,
                created_at,
                created_by,
                household_count;
            """,
            (
                active_year["year_id"],
                created_by,
                len(eligible_households),
            ),
        ).fetchone()

        # -------------------------------------------------
        # Create pending recipients
        # -------------------------------------------------

        for household in eligible_households.values():

            conn.execute(
                """
                INSERT INTO renewal_invitation_recipients (
                    batch_id,
                    household_id,
                    email_address,
                    status
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    'pending'
                );
                """,
                (
                    batch["batch_id"],
                    household["household_id"],
                    household["email_address"],
                ),
            )

    return {
        "batch_id":
            batch["batch_id"],

        "year_id":
            active_year["year_id"],

        "year_name":
            active_year["name"],

        "previous_year_id":
            previous_year["year_id"],

        "previous_year_name":
            previous_year["name"],

        "household_count":
            len(eligible_households),

        "created_by":
            created_by,
    }


# ---------------------------------------------------------
# Renewal invitation batch status
# ---------------------------------------------------------

def get_renewal_invitation_batch_status(
    batch_id: int,
) -> dict:
    """
    Return delivery status counts for a renewal invitation
    batch.
    """

    with _connect() as conn:

        batch = conn.execute(
            """
            SELECT
                rib.batch_id,
                rib.year_id,
                rib.created_at,
                rib.created_by,
                rib.household_count,
                cy.name AS year_name
            FROM renewal_invitation_batches AS rib
            INNER JOIN catechetical_years AS cy
                ON cy.year_id = rib.year_id
            WHERE rib.batch_id = %s;
            """,
            (
                batch_id,
            ),
        ).fetchone()

        if batch is None:
            raise ValueError(
                "Renewal invitation batch was not found."
            )

        counts = conn.execute(
            """
            SELECT
                COUNT(*) AS total,
                COUNT(*) FILTER (
                    WHERE status = 'pending'
                ) AS pending,
                COUNT(*) FILTER (
                    WHERE status = 'sending'
                ) AS sending,
                COUNT(*) FILTER (
                    WHERE status = 'sent'
                ) AS sent,
                COUNT(*) FILTER (
                    WHERE status = 'failed'
                ) AS failed
            FROM renewal_invitation_recipients
            WHERE batch_id = %s;
            """,
            (
                batch_id,
            ),
        ).fetchone()

    return {
        "batch_id":
            batch["batch_id"],

        "year_id":
            batch["year_id"],

        "year_name":
            batch["year_name"],

        "created_at":
            batch["created_at"],

        "created_by":
            batch["created_by"],

        "household_count":
            batch["household_count"],

        "total":
            counts["total"],

        "pending":
            counts["pending"],

        "sending":
            counts["sending"],

        "sent":
            counts["sent"],

        "failed":
            counts["failed"],
    }


# ---------------------------------------------------------
# Failed renewal invitation recipients
# ---------------------------------------------------------

def get_failed_renewal_invitation_recipients(
    batch_id: int,
) -> list[dict]:
    """
    Return failed recipients for a renewal invitation batch
    with household and delivery-attempt details.
    """

    with _connect() as conn:

        rows = conn.execute(
            """
            SELECT
                rir.recipient_id,
                rir.household_id,
                rir.email_address,
                rir.attempt_count,
                rir.last_attempt_at,
                rir.error_message,
                h.household_reference,
                h.parent_a_first_name,
                h.parent_a_last_name
            FROM renewal_invitation_recipients AS rir
            INNER JOIN households AS h
                ON h.household_id = rir.household_id
            WHERE rir.batch_id = %s
              AND rir.status = 'failed'
            ORDER BY
                h.parent_a_last_name,
                h.parent_a_first_name,
                rir.recipient_id;
            """,
            (
                batch_id,
            ),
        ).fetchall()

    return [
        {
            "recipient_id":
                row["recipient_id"],

            "household_id":
                row["household_id"],

            "household_reference":
                row["household_reference"],

            "parent_first_name":
                row["parent_a_first_name"],

            "parent_last_name":
                row["parent_a_last_name"],

            "email_address":
                row["email_address"],

            "attempt_count":
                row["attempt_count"],

            "last_attempt_at":
                row["last_attempt_at"],

            "error_message":
                row["error_message"],
        }
        for row in rows
    ]


# ---------------------------------------------------------
# Sending renewal invitation recipients
# ---------------------------------------------------------

def get_sending_renewal_invitation_recipients(
    batch_id: int,
) -> list[dict]:
    """
    Return recipients currently marked as sending for a
    renewal invitation batch, including household and
    delivery-attempt details.
    """

    with _connect() as conn:

        rows = conn.execute(
            """
            SELECT
                rir.recipient_id,
                rir.household_id,
                rir.email_address,
                rir.attempt_count,
                rir.last_attempt_at,
                h.household_reference,
                h.parent_a_first_name,
                h.parent_a_last_name
            FROM renewal_invitation_recipients AS rir
            INNER JOIN households AS h
                ON h.household_id = rir.household_id
            WHERE rir.batch_id = %s
              AND rir.status = 'sending'
            ORDER BY
                h.parent_a_last_name,
                h.parent_a_first_name,
                rir.recipient_id;
            """,
            (
                batch_id,
            ),
        ).fetchall()

    return [
        {
            "recipient_id":
                row["recipient_id"],

            "household_id":
                row["household_id"],

            "household_reference":
                row["household_reference"],

            "parent_first_name":
                row["parent_a_first_name"],

            "parent_last_name":
                row["parent_a_last_name"],

            "email_address":
                row["email_address"],

            "attempt_count":
                row["attempt_count"],

            "last_attempt_at":
                row["last_attempt_at"],
        }
        for row in rows
    ]


# ---------------------------------------------------------
# Resolve sending renewal invitation as sent
# ---------------------------------------------------------

def resolve_sending_renewal_invitation_as_sent(
    recipient_id: int,
    resolved_by: str,
) -> dict:
    """
    Manually resolve an ambiguous sending recipient as sent.

    The recipient status change and recovery audit event are
    committed together in one transaction.
    """

    resolved_by = (resolved_by or "").strip()

    if not resolved_by:
        raise ValueError(
            "The administrator resolving this invitation "
            "could not be identified."
        )

    with _connect() as conn:

        recipient = conn.execute(
            """
            SELECT
                recipient_id,
                attempt_count,
                last_attempt_at
            FROM renewal_invitation_recipients
            WHERE recipient_id = %s
              AND status = 'sending'
            FOR UPDATE;
            """,
            (
                recipient_id,
            ),
        ).fetchone()

        if recipient is None:
            raise ValueError(
                "This invitation is no longer marked as "
                "sending and cannot be resolved as sent."
            )

        updated = conn.execute(
            """
            UPDATE renewal_invitation_recipients
            SET
                status = 'sent',
                sent_at = COALESCE(
                    last_attempt_at,
                    CURRENT_TIMESTAMP
                ),
                error_message = NULL
            WHERE recipient_id = %s
              AND status = 'sending'
            RETURNING
                recipient_id,
                batch_id,
                household_id,
                status,
                attempt_count,
                sent_at,
                last_attempt_at;
            """,
            (
                recipient_id,
            ),
        ).fetchone()

        if updated is None:
            raise ValueError(
                "This invitation could not be resolved as "
                "sent because its status changed during "
                "recovery."
            )

        recovery_event = conn.execute(
            """
            INSERT INTO renewal_invitation_recovery_events (
                recipient_id,
                action,
                attempt_count,
                resolved_by
            )
            VALUES (
                %s,
                'mark_sent',
                %s,
                %s
            )
            RETURNING
                recovery_event_id,
                resolved_at;
            """,
            (
                recipient_id,
                recipient["attempt_count"],
                resolved_by,
            ),
        ).fetchone()

    return {
        "recipient_id":
            updated["recipient_id"],

        "batch_id":
            updated["batch_id"],

        "household_id":
            updated["household_id"],

        "status":
            updated["status"],

        "attempt_count":
            updated["attempt_count"],

        "sent_at":
            updated["sent_at"],

        "last_attempt_at":
            updated["last_attempt_at"],

        "recovery_event_id":
            recovery_event["recovery_event_id"],

        "resolved_at":
            recovery_event["resolved_at"],

        "resolved_by":
            resolved_by,
    }


# ---------------------------------------------------------
# Return sending renewal invitation to pending
# ---------------------------------------------------------

def return_sending_renewal_invitation_to_pending(
    recipient_id: int,
    resolved_by: str,
) -> dict:
    """
    Return an ambiguous sending recipient to the pending
    queue so it may be attempted again.

    The previous attempt count and last-attempt timestamp
    are preserved. The status change and recovery audit
    event are committed together in one transaction.
    """

    resolved_by = (resolved_by or "").strip()

    if not resolved_by:
        raise ValueError(
            "The administrator resolving this invitation "
            "could not be identified."
        )

    with _connect() as conn:

        recipient = conn.execute(
            """
            SELECT
                recipient_id,
                attempt_count,
                last_attempt_at
            FROM renewal_invitation_recipients
            WHERE recipient_id = %s
              AND status = 'sending'
            FOR UPDATE;
            """,
            (
                recipient_id,
            ),
        ).fetchone()

        if recipient is None:
            raise ValueError(
                "This invitation is no longer marked as "
                "sending and cannot be returned to pending."
            )

        updated = conn.execute(
            """
            UPDATE renewal_invitation_recipients
            SET
                status = 'pending',
                error_message = NULL
            WHERE recipient_id = %s
              AND status = 'sending'
            RETURNING
                recipient_id,
                batch_id,
                household_id,
                status,
                attempt_count,
                sent_at,
                last_attempt_at;
            """,
            (
                recipient_id,
            ),
        ).fetchone()

        if updated is None:
            raise ValueError(
                "This invitation could not be returned to "
                "pending because its status changed during "
                "recovery."
            )

        recovery_event = conn.execute(
            """
            INSERT INTO renewal_invitation_recovery_events (
                recipient_id,
                action,
                attempt_count,
                resolved_by
            )
            VALUES (
                %s,
                'return_pending',
                %s,
                %s
            )
            RETURNING
                recovery_event_id,
                resolved_at;
            """,
            (
                recipient_id,
                recipient["attempt_count"],
                resolved_by,
            ),
        ).fetchone()

    return {
        "recipient_id":
            updated["recipient_id"],

        "batch_id":
            updated["batch_id"],

        "household_id":
            updated["household_id"],

        "status":
            updated["status"],

        "attempt_count":
            updated["attempt_count"],

        "sent_at":
            updated["sent_at"],

        "last_attempt_at":
            updated["last_attempt_at"],

        "recovery_event_id":
            recovery_event["recovery_event_id"],

        "resolved_at":
            recovery_event["resolved_at"],

        "resolved_by":
            resolved_by,
    }


# ---------------------------------------------------------
# Claim next renewal invitation recipient
# ---------------------------------------------------------

def claim_next_renewal_invitation_recipient(
    batch_id: int,
    retry_failed: bool = False,
) -> dict | None:
    """
    Atomically claim the next renewal invitation recipient.

    Normal processing claims only pending recipients.

    When retry_failed is True, only previously failed
    recipients are eligible to be claimed.

    Claiming a recipient:
        - changes status to 'sending'
        - increments attempt_count
        - records last_attempt_at
        - clears the previous error message

    Returns None when no eligible recipient remains.
    """

    allowed_statuses = (
        ["failed"]
        if retry_failed
        else ["pending"]
    )

    with _connect() as conn:

        recipient = conn.execute(
            """
            SELECT
                rir.recipient_id,
                rir.batch_id,
                rir.household_id,
                rir.email_address,
                rir.status,
                rir.attempt_count,

                h.household_reference,
                h.parent_a_first_name,
                h.parent_a_last_name,

                rib.year_id,

                active_year.name AS active_year_name,
                previous_year.name AS previous_year_name

            FROM renewal_invitation_recipients AS rir

            INNER JOIN renewal_invitation_batches AS rib
                ON rib.batch_id = rir.batch_id

            INNER JOIN households AS h
                ON h.household_id = rir.household_id

            INNER JOIN catechetical_years AS active_year
                ON active_year.year_id = rib.year_id

            INNER JOIN catechetical_years AS previous_year
                ON previous_year.end_year =
                   active_year.start_year

            WHERE rir.batch_id = %s
              AND rir.status = ANY(%s)

            ORDER BY
                rir.recipient_id

            FOR UPDATE OF rir SKIP LOCKED

            LIMIT 1;
            """,
            (
                batch_id,
                allowed_statuses,
            ),
        ).fetchone()

        if recipient is None:
            return None

        updated = conn.execute(
            """
            UPDATE renewal_invitation_recipients
            SET
                status = 'sending',
                attempt_count = attempt_count + 1,
                last_attempt_at = CURRENT_TIMESTAMP,
                error_message = NULL
            WHERE recipient_id = %s
            RETURNING
                recipient_id,
                status,
                attempt_count,
                last_attempt_at;
            """,
            (
                recipient["recipient_id"],
            ),
        ).fetchone()

    return {
        "recipient_id":
            recipient["recipient_id"],

        "batch_id":
            recipient["batch_id"],

        "household_id":
            recipient["household_id"],

        "household_reference":
            recipient["household_reference"],

        "email_address":
            recipient["email_address"],

        "parent_first_name":
            recipient["parent_a_first_name"],

        "parent_last_name":
            recipient["parent_a_last_name"],

        "active_year_name":
            recipient["active_year_name"],

        "previous_year_name":
            recipient["previous_year_name"],

        "status":
            updated["status"],

        "attempt_count":
            updated["attempt_count"],

        "last_attempt_at":
            updated["last_attempt_at"],
    }


# ---------------------------------------------------------
# Mark renewal invitation sent
# ---------------------------------------------------------

def mark_renewal_invitation_sent(
    recipient_id: int,
) -> dict:
    """
    Mark a claimed renewal invitation recipient as sent.

    Only a recipient currently in 'sending' status may be
    marked as sent.
    """

    with _connect() as conn:

        recipient = conn.execute(
            """
            UPDATE renewal_invitation_recipients
            SET
                status = 'sent',
                sent_at = CURRENT_TIMESTAMP,
                error_message = NULL
            WHERE recipient_id = %s
              AND status = 'sending'
            RETURNING
                recipient_id,
                batch_id,
                household_id,
                status,
                attempt_count,
                sent_at,
                last_attempt_at;
            """,
            (
                recipient_id,
            ),
        ).fetchone()

        if recipient is None:
            raise ValueError(
                "The renewal invitation recipient could "
                "not be marked as sent because it is not "
                "currently in sending status."
            )

    return dict(recipient)


# ---------------------------------------------------------
# Mark renewal invitation failed
# ---------------------------------------------------------

def mark_renewal_invitation_failed(
    recipient_id: int,
    error_message: str,
) -> dict:
    """
    Mark a claimed renewal invitation recipient as failed.

    The error is stored for administrative troubleshooting.
    Only a recipient currently in 'sending' status may be
    marked as failed.
    """

    error_message = (
        error_message
        or "Unknown email delivery error."
    ).strip()

    # Keep an unexpectedly large SMTP/server error from
    # filling the database with excessive diagnostic text.
    error_message = error_message[:2000]

    with _connect() as conn:

        recipient = conn.execute(
            """
            UPDATE renewal_invitation_recipients
            SET
                status = 'failed',
                error_message = %s
            WHERE recipient_id = %s
              AND status = 'sending'
            RETURNING
                recipient_id,
                batch_id,
                household_id,
                status,
                attempt_count,
                sent_at,
                last_attempt_at,
                error_message;
            """,
            (
                error_message,
                recipient_id,
            ),
        ).fetchone()

        if recipient is None:
            raise ValueError(
                "The renewal invitation recipient could "
                "not be marked as failed because it is not "
                "currently in sending status."
            )

    return dict(recipient)


# ---------------------------------------------------------
# Start next catechetical year
# ---------------------------------------------------------

def rollover_catechetical_year(
    started_by: str,
) -> dict:
    """
    Close the current catechetical year and start the next.

    The rollover:
        - closes the current active year
        - creates the next active year
        - opens renewal for the new year
        - copies the previous year's class configuration

    It does NOT:
        - copy yearly enrollments
        - modify households
        - modify children
        - modify sacramental history

    The entire rollover occurs in one database transaction.
    """

    started_by = (
        started_by
        or ""
    ).strip().lower()

    if not started_by:
        raise ValueError(
            "The administrator starting the new year "
            "could not be identified."
        )

    with _connect() as conn:

        # -------------------------------------------------
        # Lock and load current active year
        # -------------------------------------------------

        active_year = conn.execute(
            """
            SELECT
                year_id,
                name,
                start_year,
                end_year
            FROM catechetical_years
            WHERE status = 'active'
            FOR UPDATE;
            """
        ).fetchone()

        if active_year is None:
            raise ValueError(
                "No active catechetical year was found."
            )

        current_year_id = (
            active_year["year_id"]
        )

        current_name = (
            active_year["name"]
        )

        next_start_year = (
            active_year["end_year"]
        )

        next_end_year = (
            next_start_year + 1
        )

        next_name = (
            f"{next_start_year}-{next_end_year}"
        )

        # -------------------------------------------------
        # Make sure the next year does not already exist
        # -------------------------------------------------

        existing_next_year = conn.execute(
            """
            SELECT year_id
            FROM catechetical_years
            WHERE start_year = %s
               OR name = %s;
            """,
            (
                next_start_year,
                next_name,
            ),
        ).fetchone()

        if existing_next_year is not None:
            raise ValueError(
                f"{next_name} already exists. "
                "The rollover was not performed."
            )

        # -------------------------------------------------
        # Load current class configuration
        # -------------------------------------------------

        current_classes = conn.execute(
            """
            SELECT
                group_key,
                display_name,
                category,
                catechists,
                classroom
            FROM classes
            WHERE year_id = %s
            ORDER BY class_id;
            """,
            (
                current_year_id,
            ),
        ).fetchall()

        if not current_classes:
            raise ValueError(
                "The active catechetical year has no "
                "class configuration to carry forward."
            )

        # -------------------------------------------------
        # Close current year
        # -------------------------------------------------

        result = conn.execute(
            """
            UPDATE catechetical_years
            SET
                status = 'closed',
                renewal_open = FALSE
            WHERE year_id = %s
              AND status = 'active';
            """,
            (
                current_year_id,
            ),
        )

        if result.rowcount != 1:
            raise ValueError(
                "The active catechetical year could not "
                "be closed."
            )

        # -------------------------------------------------
        # Create next active year
        # -------------------------------------------------

        new_year = conn.execute(
            """
            INSERT INTO catechetical_years (
                name,
                start_year,
                end_year,
                status,
                renewal_open,
                started_at,
                started_by
            )
            VALUES (
                %s,
                %s,
                %s,
                'active',
                TRUE,
                CURRENT_TIMESTAMP,
                %s
            )
            RETURNING year_id;
            """,
            (
                next_name,
                next_start_year,
                next_end_year,
                started_by,
            ),
        ).fetchone()

        new_year_id = (
            new_year["year_id"]
        )

        # -------------------------------------------------
        # Copy class configuration into new year
        # -------------------------------------------------

        for class_row in current_classes:

            conn.execute(
                """
                INSERT INTO classes (
                    year_id,
                    group_key,
                    display_name,
                    category,
                    catechists,
                    classroom
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s
                );
                """,
                (
                    new_year_id,
                    class_row["group_key"],
                    class_row["display_name"],
                    class_row["category"],
                    class_row["catechists"],
                    class_row["classroom"],
                ),
            )

    return {
        "previous_year_id":
            current_year_id,

        "previous_name":
            current_name,

        "new_year_id":
            new_year_id,

        "new_name":
            next_name,

        "renewal_open":
            True,

        "classes_copied":
            len(current_classes),
    }


# ---------------------------------------------------------
# Update roster group details
# ---------------------------------------------------------

def update_roster_group_details(
    group_key: str,
    catechists: str,
    classroom: str,
) -> None:
    """
    Update the catechists and classroom for a roster
    group in the active catechetical year.
    """

    group_key = (
        group_key
        or ""
    ).strip()

    catechists = (
        catechists
        or ""
    ).strip()

    classroom = (
        classroom
        or ""
    ).strip()

    if not group_key:
        raise ValueError(
            "Roster group is required."
        )

    with _connect() as conn:

        result = conn.execute(
            """
            UPDATE classes AS cl
            SET
                catechists = %s,
                classroom = %s

            FROM catechetical_years AS cy

            WHERE cl.year_id = cy.year_id
              AND cy.status = 'active'
              AND cl.group_key = %s;
            """,
            (
                catechists,
                classroom,
                group_key,
            ),
        )

        if result.rowcount != 1:
            raise ValueError(
                "The active roster group could not be found."
            )