from datetime import date
import re

import streamlit as st

from db import (
    create_household_verification,
    get_household_references_by_email,
    get_registration_by_reference,
    init_db,
    save_registration,
    update_registration,
    verify_household_code,
)

from email_service import (
    send_household_id_recovery,
    send_registration_confirmation,
    send_update_confirmation,
    send_verification_email,
)


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------

def calculate_age(date_of_birth: date) -> int:
    today = date.today()

    age = today.year - date_of_birth.year

    if (today.month, today.day) < (
        date_of_birth.month,
        date_of_birth.day,
    ):
        age -= 1

    return age


def is_valid_email(email: str) -> bool:
    """
    Practical email validation.

    Accepts:
        name@example.com
        first.last@example.com
        name+tag@example.com

    Rejects:
        name#example,com
        name@example
        name @example.com
    """

    email = email.strip()

    pattern = (
        r"^[A-Za-z0-9._%+-]+"
        r"@[A-Za-z0-9-]+"
        r"(?:\.[A-Za-z0-9-]+)+$"
    )

    return re.fullmatch(pattern, email) is not None


def normalize_phone(phone: str) -> str | None:
    """
    Validate and normalize a US phone number.

    Accepts:
        3045551234
        304-555-1234
        (304) 555-1234
        1-304-555-1234

    Returns:
        (304) 555-1234
    """

    digits = re.sub(r"\D", "", phone)

    # Allow optional US country code.
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]

    if len(digits) != 10:
        return None

    # US area codes and exchanges cannot begin with 0 or 1.
    if digits[0] in "01":
        return None

    if digits[3] in "01":
        return None

    return (
        f"({digits[:3]}) "
        f"{digits[3:6]}-"
        f"{digits[6:]}"
    )


def normalize_zip(zip_code: str) -> str | None:
    """
    Validate and normalize a US ZIP code.

    Accepts:
        25033
        250331234
        25033-1234

    Returns:
        25033
        25033-1234
    """

    zip_code = zip_code.strip()

    if re.fullmatch(r"\d{5}", zip_code):
        return zip_code

    if re.fullmatch(r"\d{9}", zip_code):
        return (
            f"{zip_code[:5]}-"
            f"{zip_code[5:]}"
        )

    if re.fullmatch(
        r"\d{5}-\d{4}",
        zip_code,
    ):
        return zip_code

    return None


def mask_email(email: str) -> str:
    """
    Mask an email address for display.

    Example:
        daniel@example.com
        d••••••@example.com
    """

    if "@" not in email:
        return email

    username, domain = email.split("@", 1)

    if len(username) <= 1:
        masked_username = "•"
    else:
        masked_username = (
            username[0]
            + "•" * (len(username) - 1)
        )

    return f"{masked_username}@{domain}"


def clear_verification_state() -> None:
    """
    Clear temporary returning-household
    verification information.
    """

    st.session_state.verification_reference = None
    st.session_state.verification_email = None
    st.session_state.show_existing_dialog = False


def clear_recovery_state() -> None:
    """
    Clear temporary Household ID recovery state.
    """

    st.session_state.show_recovery_dialog = False
    st.session_state.recovery_request_sent = False


# ---------------------------------------------------------
# App setup
# ---------------------------------------------------------

st.set_page_config(
    page_title="Ascension Registration",
    page_icon="⛪",
    layout="centered",
)

init_db()


# ---------------------------------------------------------
# Session state
# ---------------------------------------------------------

if "household" not in st.session_state:
    st.session_state.household = None

if "children" not in st.session_state:
    st.session_state.children = []

if "submitted_household_id" not in st.session_state:
    st.session_state.submitted_household_id = None

if "submitted_household_reference" not in st.session_state:
    st.session_state.submitted_household_reference = None

if "registration_mode" not in st.session_state:
    st.session_state.registration_mode = None

if "existing_household_id" not in st.session_state:
    st.session_state.existing_household_id = None

if "existing_household_reference" not in st.session_state:
    st.session_state.existing_household_reference = None


# ---------------------------------------------------------
# Verification session state
# ---------------------------------------------------------

if "verification_reference" not in st.session_state:
    st.session_state.verification_reference = None

if "verification_email" not in st.session_state:
    st.session_state.verification_email = None

if "show_existing_dialog" not in st.session_state:
    st.session_state.show_existing_dialog = False


# ---------------------------------------------------------
# Household ID recovery session state
# ---------------------------------------------------------

if "show_recovery_dialog" not in st.session_state:
    st.session_state.show_recovery_dialog = False

if "recovery_request_sent" not in st.session_state:
    st.session_state.recovery_request_sent = False


# ---------------------------------------------------------
# Confirmation email session state
# ---------------------------------------------------------

if "confirmation_email_sent" not in st.session_state:
    st.session_state.confirmation_email_sent = None

if "confirmation_email_address" not in st.session_state:
    st.session_state.confirmation_email_address = None

if "confirmation_email_error" not in st.session_state:
    st.session_state.confirmation_email_error = None


# ---------------------------------------------------------
# Household ID recovery dialog
# ---------------------------------------------------------

@st.dialog("Recover Household ID")
def recover_household_id_dialog():

    # -----------------------------------------------------
    # Recovery request already submitted
    # -----------------------------------------------------

    if st.session_state.recovery_request_sent:

        st.success(
            "Recovery request received."
        )

        st.write(
            "If that email address is associated with an "
            "Ascension registration, the Household ID has "
            "been sent to it."
        )

        st.caption(
            "Please check your inbox and spam folder."
        )

        st.divider()

        if st.button(
            "Return to Existing Household",
            type="primary",
            use_container_width=True,
        ):

            clear_recovery_state()

            st.session_state.show_existing_dialog = True

            st.rerun()

        if st.button(
            "Close",
            use_container_width=True,
        ):

            clear_recovery_state()

            st.rerun()

        return

    # -----------------------------------------------------
    # Email entry
    # -----------------------------------------------------

    st.write(
        "Enter the email address associated with your "
        "household registration."
    )

    st.caption(
        "You may use the email address listed for either "
        "parent or guardian."
    )

    email = st.text_input(
        "Email",
        placeholder="name@example.com",
    )

    if st.button(
        "Send Household ID",
        type="primary",
        use_container_width=True,
    ):

        email = email.strip()

        if not email:

            st.error(
                "Please enter your email address."
            )

            return

        if not is_valid_email(email):

            st.error(
                "Please enter a valid email address."
            )

            return

        try:

            references = (
                get_household_references_by_email(
                    email
                )
            )

            # Only send an email when the address
            # actually exists in the database.
            #
            # The user-facing response stays the same
            # whether or not a match exists.
            if references:

                send_household_id_recovery(
                    recipient=email,
                    household_references=references,
                )

            st.session_state.recovery_request_sent = True
            st.session_state.show_recovery_dialog = True

            st.rerun()

        except Exception:

            st.error(
                "We couldn't process the recovery request "
                "right now. Please try again."
            )


# ---------------------------------------------------------
# Existing household dialog
# ---------------------------------------------------------

@st.dialog("Return to Existing Household")
def existing_household_dialog():

    # -----------------------------------------------------
    # Stage 1: Household ID
    # -----------------------------------------------------

    if st.session_state.verification_reference is None:

        st.write(
            "Enter the Household ID from your "
            "previous registration."
        )

        household_reference = st.text_input(
            "Household ID",
            placeholder="ASC-XXXXXX",
        )

        if st.button(
            "Send Verification Code",
            type="primary",
            use_container_width=True,
        ):

            if not household_reference.strip():

                st.error(
                    "Please enter your Household ID."
                )

                return

            try:

                verification = (
                    create_household_verification(
                        household_reference
                    )
                )

                if verification is None:

                    st.error(
                        "We couldn't find a household "
                        "with that ID."
                    )

                    return

                send_verification_email(
                    recipient=verification["email"],
                    verification_code=verification["code"],
                    household_reference=(
                        verification[
                            "household_reference"
                        ]
                    ),
                    expires_minutes=(
                        verification[
                            "expires_minutes"
                        ]
                    ),
                )

                st.session_state.verification_reference = (
                    verification[
                        "household_reference"
                    ]
                )

                st.session_state.verification_email = (
                    verification["email"]
                )

                st.session_state.show_existing_dialog = True

                st.rerun()

            except Exception as exc:

                st.error(
                    "We couldn't send the verification "
                    f"email: {exc}"
                )

        st.divider()

        if st.button(
            "Forgot Household ID?",
            use_container_width=True,
        ):

            clear_verification_state()

            st.session_state.show_recovery_dialog = True

            st.rerun()

        return

    # -----------------------------------------------------
    # Stage 2: Verification code
    # -----------------------------------------------------

    household_reference = (
        st.session_state.verification_reference
    )

    email = (
        st.session_state.verification_email
    )

    st.success(
        "Verification code sent."
    )

    st.write(
        "We sent a 6-digit verification code to:"
    )

    st.write(
        f"**{mask_email(email)}**"
    )

    st.caption(
        "The code expires in 10 minutes."
    )

    verification_code = st.text_input(
        "Verification Code",
        max_chars=6,
        placeholder="123456",
    )

    if st.button(
        "Verify & Continue",
        type="primary",
        use_container_width=True,
    ):

        if not verification_code.strip():

            st.error(
                "Please enter the verification code."
            )

            return

        verified, status = verify_household_code(
            household_reference,
            verification_code,
        )

        if not verified:

            if status == "expired":

                st.error(
                    "That verification code has expired. "
                    "Please request a new one."
                )

            elif status == "locked":

                st.error(
                    "Too many incorrect attempts. "
                    "Please request a new code."
                )

            elif status == "no_active_code":

                st.error(
                    "There is no active verification code. "
                    "Please request a new one."
                )

            else:

                st.error(
                    "That verification code is incorrect."
                )

            return

        # ---------------------------------------------
        # Verification passed.
        # Load the household.
        # ---------------------------------------------

        result = get_registration_by_reference(
            household_reference
        )

        if result is None:

            st.error(
                "The household could not be loaded."
            )

            return

        household, children = result

        st.session_state.household = {

            "parent_a_first_name":
                household[
                    "parent_a_first_name"
                ],

            "parent_a_last_name":
                household[
                    "parent_a_last_name"
                ],

            "parent_a_email":
                household[
                    "parent_a_email"
                ],

            "parent_a_phone":
                household[
                    "parent_a_phone"
                ],

            "parent_b_first_name":
                household[
                    "parent_b_first_name"
                ] or "",

            "parent_b_last_name":
                household[
                    "parent_b_last_name"
                ] or "",

            "parent_b_email":
                household[
                    "parent_b_email"
                ] or "",

            "parent_b_phone":
                household[
                    "parent_b_phone"
                ] or "",

            "address_line_1":
                household[
                    "address_line_1"
                ],

            "address_line_2":
                household[
                    "address_line_2"
                ] or "",

            "city":
                household[
                    "city"
                ],

            "state":
                household[
                    "state"
                ],

            "zip_code":
                household[
                    "zip_code"
                ],
        }

        st.session_state.children = children

        st.session_state.existing_household_id = (
            household[
                "household_id"
            ]
        )

        st.session_state.existing_household_reference = (
            household[
                "household_reference"
            ]
        )

        st.session_state.registration_mode = (
            "existing"
        )

        clear_verification_state()
        clear_recovery_state()

        st.rerun()

    st.divider()

    # -----------------------------------------------------
    # Resend code
    # -----------------------------------------------------

    if st.button(
        "Send a New Code",
        use_container_width=True,
    ):

        try:

            verification = (
                create_household_verification(
                    household_reference
                )
            )

            if verification is None:

                st.error(
                    "The household could not be found."
                )

                return

            send_verification_email(
                recipient=verification["email"],
                verification_code=verification["code"],
                household_reference=(
                    verification[
                        "household_reference"
                    ]
                ),
                expires_minutes=(
                    verification[
                        "expires_minutes"
                    ]
                ),
            )

            st.session_state.verification_email = (
                verification[
                    "email"
                ]
            )

            st.success(
                "A new verification code was sent."
            )

        except Exception as exc:

            st.error(
                "We couldn't send a new verification "
                f"code: {exc}"
            )

    if st.button(
        "Use a Different Household ID",
        use_container_width=True,
    ):

        st.session_state.verification_reference = None
        st.session_state.verification_email = None
        st.session_state.show_existing_dialog = True

        st.rerun()


# ---------------------------------------------------------
# Household dialog
# ---------------------------------------------------------

@st.dialog("Household Information")
def household_dialog():

    household = (
        st.session_state.household
        or {}
    )

    with st.form(
        "household_form",
        enter_to_submit=False,
    ):

        # -------------------------------------------------
        # Parent / Guardian A
        # -------------------------------------------------

        st.subheader(
            "Parent / Guardian A"
        )

        st.caption(
            "Required"
        )

        col1, col2 = st.columns(2)

        with col1:

            parent_a_first_name = st.text_input(
                "First name",
                value=household.get(
                    "parent_a_first_name",
                    "",
                ),
            )

        with col2:

            parent_a_last_name = st.text_input(
                "Last name",
                value=household.get(
                    "parent_a_last_name",
                    "",
                ),
            )

        col1, col2 = st.columns(2)

        with col1:

            parent_a_email = st.text_input(
                "Email",
                value=household.get(
                    "parent_a_email",
                    "",
                ),
            )

        with col2:

            parent_a_phone = st.text_input(
                "Phone",
                value=household.get(
                    "parent_a_phone",
                    "",
                ),
            )

        st.divider()

        # -------------------------------------------------
        # Parent / Guardian B
        # -------------------------------------------------

        st.subheader(
            "Parent / Guardian B"
        )

        st.caption(
            "Optional"
        )

        col1, col2 = st.columns(2)

        with col1:

            parent_b_first_name = st.text_input(
                "First name",
                value=household.get(
                    "parent_b_first_name",
                    "",
                ),
                key="parent_b_first_name",
            )

        with col2:

            parent_b_last_name = st.text_input(
                "Last name",
                value=household.get(
                    "parent_b_last_name",
                    "",
                ),
                key="parent_b_last_name",
            )

        col1, col2 = st.columns(2)

        with col1:

            parent_b_email = st.text_input(
                "Email",
                value=household.get(
                    "parent_b_email",
                    "",
                ),
                key="parent_b_email",
            )

        with col2:

            parent_b_phone = st.text_input(
                "Phone",
                value=household.get(
                    "parent_b_phone",
                    "",
                ),
                key="parent_b_phone",
            )

        st.divider()

        # -------------------------------------------------
        # Address
        # -------------------------------------------------

        st.subheader(
            "Home Address"
        )

        address_line_1 = st.text_input(
            "Street address",
            value=household.get(
                "address_line_1",
                "",
            ),
        )

        address_line_2 = st.text_input(
            "Apartment, unit, etc.",
            value=household.get(
                "address_line_2",
                "",
            ),
        )

        city_col, state_col, zip_col = (
            st.columns(
                [2, 1, 1]
            )
        )

        with city_col:

            city = st.text_input(
                "City",
                value=household.get(
                    "city",
                    "",
                ),
            )

        with state_col:

            state = st.text_input(
                "State",
                value=household.get(
                    "state",
                    "WV",
                ),
                max_chars=2,
            )

        with zip_col:

            zip_code = st.text_input(
                "ZIP",
                value=household.get(
                    "zip_code",
                    "",
                ),
            )

        submitted = st.form_submit_button(
            "Save Household",
            type="primary",
            use_container_width=True,
        )

        if submitted:

            # ---------------------------------------------
            # Required field validation
            # ---------------------------------------------

            required_fields = {

                "Parent / Guardian A first name":
                    parent_a_first_name,

                "Parent / Guardian A last name":
                    parent_a_last_name,

                "Email":
                    parent_a_email,

                "Phone":
                    parent_a_phone,

                "Street address":
                    address_line_1,

                "City":
                    city,

                "State":
                    state,

                "ZIP":
                    zip_code,
            }

            missing = [
                name
                for name, value
                in required_fields.items()
                if not value.strip()
            ]

            if missing:

                st.error(
                    "Please complete all required "
                    "household information."
                )

                return

            # ---------------------------------------------
            # Parent A email
            # ---------------------------------------------

            if not is_valid_email(
                parent_a_email
            ):

                st.error(
                    "Please enter a valid email address "
                    "for Parent / Guardian A."
                )

                return

            # ---------------------------------------------
            # Parent B email
            # ---------------------------------------------

            if (
                parent_b_email.strip()
                and not is_valid_email(
                    parent_b_email
                )
            ):

                st.error(
                    "Please enter a valid email address "
                    "for Parent / Guardian B."
                )

                return

            # ---------------------------------------------
            # Parent A phone
            # ---------------------------------------------

            parent_a_phone_formatted = (
                normalize_phone(
                    parent_a_phone
                )
            )

            if (
                parent_a_phone_formatted
                is None
            ):

                st.error(
                    "Please enter a valid 10-digit "
                    "phone number for Parent / Guardian A."
                )

                return

            # ---------------------------------------------
            # Parent B phone
            # ---------------------------------------------

            parent_b_phone_formatted = None

            if parent_b_phone.strip():

                parent_b_phone_formatted = (
                    normalize_phone(
                        parent_b_phone
                    )
                )

                if (
                    parent_b_phone_formatted
                    is None
                ):

                    st.error(
                        "Please enter a valid 10-digit "
                        "phone number for Parent / Guardian B."
                    )

                    return

            # ---------------------------------------------
            # ZIP code
            # ---------------------------------------------

            zip_code_formatted = (
                normalize_zip(
                    zip_code
                )
            )

            if zip_code_formatted is None:

                st.error(
                    "Please enter a valid ZIP code "
                    "such as 25033 or 25033-1234."
                )

                return

            # ---------------------------------------------
            # State
            # ---------------------------------------------

            state_formatted = (
                state.strip().upper()
            )

            if not re.fullmatch(
                r"[A-Z]{2}",
                state_formatted,
            ):

                st.error(
                    "Please enter a valid two-letter "
                    "state abbreviation."
                )

                return

            # ---------------------------------------------
            # Save to session
            # ---------------------------------------------

            st.session_state.household = {

                "parent_a_first_name":
                    parent_a_first_name.strip(),

                "parent_a_last_name":
                    parent_a_last_name.strip(),

                "parent_a_email":
                    parent_a_email.strip(),

                "parent_a_phone":
                    parent_a_phone_formatted,

                "parent_b_first_name":
                    parent_b_first_name.strip(),

                "parent_b_last_name":
                    parent_b_last_name.strip(),

                "parent_b_email":
                    parent_b_email.strip(),

                "parent_b_phone":
                    parent_b_phone_formatted or "",

                "address_line_1":
                    address_line_1.strip(),

                "address_line_2":
                    address_line_2.strip(),

                "city":
                    city.strip(),

                "state":
                    state_formatted,

                "zip_code":
                    zip_code_formatted,
            }

            st.rerun()


# ---------------------------------------------------------
# Child dialog
# ---------------------------------------------------------

@st.dialog("Child Information")
def child_dialog(
    child_index: int | None = None,
):

    editing = (
        child_index is not None
    )

    if editing:

        child = (
            st.session_state.children[
                child_index
            ]
        )

    else:

        child = {}

    household = (
        st.session_state.household
        or {}
    )

    default_last_name = household.get(
        "parent_a_last_name",
        "",
    )

    grades = [
        "Select grade",
        "Pre-K",
        "K",
        "1",
        "2",
        "3",
        "4",
        "5",
        "6",
        "7",
        "8",
        "9",
        "10",
        "11",
        "12",
    ]

    existing_grade = child.get(
        "grade",
        "Select grade",
    )

    try:

        grade_index = (
            grades.index(
                existing_grade
            )
        )

    except ValueError:

        grade_index = 0

    with st.form(
        f"child_form_"
        f"{child_index if editing else 'new'}",
        enter_to_submit=False,
    ):

        col1, col2 = st.columns(2)

        with col1:

            first_name = st.text_input(
                "First name",
                value=child.get(
                    "first_name",
                    "",
                ),
            )

        with col2:

            middle_name = st.text_input(
                "Middle name",
                value=child.get(
                    "middle_name",
                    "",
                ),
            )

        last_name = st.text_input(
            "Last name",
            value=child.get(
                "last_name",
                default_last_name,
            ),
        )

        date_of_birth = st.date_input(
            "Date of birth",
            value=child.get(
                "date_of_birth",
                None,
            ),
            max_value=date.today(),
        )

        grade = st.selectbox(
            "Grade",
            grades,
            index=grade_index,
        )

        school = st.text_input(
            "School",
            value=child.get(
                "school",
                "",
            ),
        )

        receiving_confirmation = (
            st.toggle(
                "Receiving Confirmation this year",
                value=child.get(
                    "receiving_confirmation",
                    False,
                ),
            )
        )

        button_text = (
            "Save Changes"
            if editing
            else "Add Child"
        )

        submitted = st.form_submit_button(
            button_text,
            type="primary",
            use_container_width=True,
        )

        if submitted:

            if not first_name.strip():

                st.error(
                    "Please enter the child's "
                    "first name."
                )

                return

            if not last_name.strip():

                st.error(
                    "Please enter the child's "
                    "last name."
                )

                return

            if not school.strip():

                st.error(
                    "Please enter the child's school."
                )

                return

            if date_of_birth is None:

                st.error(
                    "Please enter a date of birth."
                )

                return

            if grade == "Select grade":

                st.error(
                    "Please select a grade."
                )

                return

            child_data = {

                "first_name":
                    first_name.strip(),

                "middle_name":
                    middle_name.strip(),

                "last_name":
                    last_name.strip(),

                "date_of_birth":
                    date_of_birth,

                "grade":
                    grade,

                "school":
                    school.strip(),

                "receiving_confirmation":
                    receiving_confirmation,
            }

            # Preserve database child_id
            # when editing an existing child.
            if (
                editing
                and child.get(
                    "child_id"
                ) is not None
            ):

                child_data[
                    "child_id"
                ] = child[
                    "child_id"
                ]

            if editing:

                st.session_state.children[
                    child_index
                ] = child_data

            else:

                st.session_state.children.append(
                    child_data
                )

            st.rerun()


# ---------------------------------------------------------
# Review dialog
# ---------------------------------------------------------

@st.dialog("Review Registration")
def review_dialog():

    household = (
        st.session_state.household
    )

    children = (
        st.session_state.children
    )

    editing_existing = (
        st.session_state.registration_mode
        == "existing"
    )

    st.subheader(
        "Household"
    )

    parent_a = (
        f"{household['parent_a_first_name']} "
        f"{household['parent_a_last_name']}"
    )

    st.write(
        f"**{parent_a}**"
    )

    st.write(
        household[
            "parent_a_email"
        ]
    )

    st.write(
        household[
            "parent_a_phone"
        ]
    )

    if (
        household.get(
            "parent_b_first_name"
        )
        or household.get(
            "parent_b_last_name"
        )
    ):

        parent_b = (
            f"{household.get('parent_b_first_name', '')} "
            f"{household.get('parent_b_last_name', '')}"
        ).strip()

        st.write("")

        st.write(
            f"**{parent_b}**"
        )

        if household.get(
            "parent_b_email"
        ):

            st.write(
                household[
                    "parent_b_email"
                ]
            )

        if household.get(
            "parent_b_phone"
        ):

            st.write(
                household[
                    "parent_b_phone"
                ]
            )

    st.write("")

    st.write(
        household[
            "address_line_1"
        ]
    )

    if household.get(
        "address_line_2"
    ):

        st.write(
            household[
                "address_line_2"
            ]
        )

    st.write(
        f"{household['city']}, "
        f"{household['state']} "
        f"{household['zip_code']}"
    )

    st.divider()

    st.subheader(
        "Children"
    )

    for child in children:

        full_name = " ".join(
            part
            for part in [
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
            ]
            if part
        )

        age = calculate_age(
            child[
                "date_of_birth"
            ]
        )

        st.write(
            f"**{full_name}**"
        )

        st.caption(
            f"Grade {child['grade']} • "
            f"{child['school']} • "
            f"DOB: "
            f"{child['date_of_birth'].strftime('%m/%d/%Y')} "
            f"(Age {age})"
        )

        if child.get(
            "receiving_confirmation",
            False,
        ):

            st.write(
                "✓ **Receiving Confirmation "
                "this year**"
            )

        else:

            st.write(
                "**Confirmation:** No"
            )

    st.divider()

    st.warning(
        "Please review the information above "
        "before submitting."
    )

    submit_label = (
        "Save Changes"
        if editing_existing
        else "Submit Registration"
    )

    if st.button(
        submit_label,
        type="primary",
        use_container_width=True,
    ):

        st.session_state.confirmation_email_sent = None
        st.session_state.confirmation_email_address = None
        st.session_state.confirmation_email_error = None

        recipient_email = (
            household[
                "parent_a_email"
            ]
        )

        try:

            # -----------------------------------------
            # Existing household
            # -----------------------------------------

            if editing_existing:

                update_registration(
                    st.session_state.existing_household_id,
                    household,
                    children,
                )

                household_id = (
                    st.session_state.existing_household_id
                )

                household_reference = (
                    st.session_state.existing_household_reference
                )

                st.session_state.submitted_household_id = (
                    household_id
                )

                st.session_state.submitted_household_reference = (
                    household_reference
                )

                try:

                    send_update_confirmation(
                        recipient=recipient_email,
                        household_reference=(
                            household_reference
                        ),
                    )

                    st.session_state.confirmation_email_sent = True

                    st.session_state.confirmation_email_address = (
                        recipient_email
                    )

                except Exception as email_exc:

                    st.session_state.confirmation_email_sent = False

                    st.session_state.confirmation_email_address = (
                        recipient_email
                    )

                    st.session_state.confirmation_email_error = (
                        str(email_exc)
                    )

            # -----------------------------------------
            # New household
            # -----------------------------------------

            else:

                (
                    household_id,
                    household_reference,
                ) = save_registration(
                    household,
                    children,
                )

                st.session_state.submitted_household_id = (
                    household_id
                )

                st.session_state.submitted_household_reference = (
                    household_reference
                )

                try:

                    send_registration_confirmation(
                        recipient=recipient_email,
                        household_reference=(
                            household_reference
                        ),
                        children=children,
                    )

                    st.session_state.confirmation_email_sent = True

                    st.session_state.confirmation_email_address = (
                        recipient_email
                    )

                except Exception as email_exc:

                    st.session_state.confirmation_email_sent = False

                    st.session_state.confirmation_email_address = (
                        recipient_email
                    )

                    st.session_state.confirmation_email_error = (
                        str(email_exc)
                    )

            st.session_state.household = None
            st.session_state.children = []

            st.rerun()

        except Exception as exc:

            st.error(
                "Registration could not be saved: "
                f"{exc}"
            )


# ---------------------------------------------------------
# Registration complete
# ---------------------------------------------------------

if (
    st.session_state.submitted_household_id
    is not None
):

    st.title(
        "Ascension Registration"
    )

    if (
        st.session_state.registration_mode
        == "existing"
    ):

        st.success(
            "Household changes saved successfully."
        )

        st.write(
            "Your household information "
            "has been updated."
        )

    else:

        st.success(
            "Registration submitted successfully."
        )

        st.write(
            "Thank you! Your family's "
            "registration has been received."
        )

    st.subheader(
        "Your Household ID"
    )

    st.code(
        st.session_state.submitted_household_reference,
        language=None,
    )

    st.info(
        "Please keep this Household ID. "
        "You'll be able to use it later "
        "to return to your household "
        "and make changes."
    )

    # -----------------------------------------------------
    # Confirmation email result
    # -----------------------------------------------------

    if (
        st.session_state.confirmation_email_sent
        is True
    ):

        st.success(
            "A confirmation email was sent to "
            f"{st.session_state.confirmation_email_address}."
        )

    elif (
        st.session_state.confirmation_email_sent
        is False
    ):

        st.warning(
            "Your registration was saved successfully, "
            "but we couldn't send the confirmation email. "
            "Please make a note of your Household ID."
        )

    if st.button(
        "Return to Start"
    ):

        st.session_state.household = None
        st.session_state.children = []

        st.session_state.submitted_household_id = None
        st.session_state.submitted_household_reference = None

        st.session_state.existing_household_id = None
        st.session_state.existing_household_reference = None

        st.session_state.registration_mode = None

        st.session_state.confirmation_email_sent = None
        st.session_state.confirmation_email_address = None
        st.session_state.confirmation_email_error = None

        clear_verification_state()
        clear_recovery_state()

        st.rerun()

    st.stop()


# ---------------------------------------------------------
# Entrance screen
# ---------------------------------------------------------

if (
    st.session_state.registration_mode
    is None
):

    st.title(
        "Ascension Registration"
    )

    st.write(
        "Register your household or return "
        "to an existing registration."
    )

    st.divider()

    col1, col2 = st.columns(2)

    # -----------------------------------------------------
    # New registration
    # -----------------------------------------------------

    with col1:

        if st.button(
            "Start a New Registration",
            type="primary",
            use_container_width=True,
        ):

            st.session_state.household = None
            st.session_state.children = []

            st.session_state.existing_household_id = None
            st.session_state.existing_household_reference = None

            st.session_state.confirmation_email_sent = None
            st.session_state.confirmation_email_address = None
            st.session_state.confirmation_email_error = None

            st.session_state.registration_mode = "new"

            clear_verification_state()
            clear_recovery_state()

            st.rerun()

    # -----------------------------------------------------
    # Existing registration
    # -----------------------------------------------------

    with col2:

        if st.button(
            "Return to Existing Household",
            use_container_width=True,
        ):

            clear_recovery_state()

            st.session_state.show_existing_dialog = True

            st.rerun()

    # -----------------------------------------------------
    # Recover Household ID
    # -----------------------------------------------------

    st.write("")

    st.caption(
        "Don't have your Household ID?"
    )

    if st.button(
        "Recover Household ID",
        use_container_width=True,
    ):

        clear_verification_state()

        st.session_state.show_recovery_dialog = True

        st.rerun()

    # -----------------------------------------------------
    # Open exactly one dialog per run
    # -----------------------------------------------------

    if st.session_state.show_existing_dialog:

        existing_household_dialog()

    elif st.session_state.show_recovery_dialog:

        recover_household_id_dialog()

    st.stop()


# ---------------------------------------------------------
# Main registration page
# ---------------------------------------------------------

st.title(
    "Ascension Registration"
)

if (
    st.session_state.registration_mode
    == "existing"
):

    st.write(
        f"Updating Household ID: "
        f"**{st.session_state.existing_household_reference}**"
    )

else:

    st.write(
        "Complete the information below "
        "to register your family."
    )

st.divider()


# ---------------------------------------------------------
# Household section
# ---------------------------------------------------------

st.header(
    "Household"
)

household = (
    st.session_state.household
)

if household is None:

    st.info(
        "Household information must be "
        "completed before adding children."
    )

    if st.button(
        "Add Household Information",
        type="primary",
    ):

        household_dialog()

else:

    with st.container(
        border=True
    ):

        parent_a = (
            f"{household['parent_a_first_name']} "
            f"{household['parent_a_last_name']}"
        )

        parent_b = (
            f"{household.get('parent_b_first_name', '')} "
            f"{household.get('parent_b_last_name', '')}"
        ).strip()

        if parent_b:

            st.subheader(
                f"{parent_a} & {parent_b}"
            )

        else:

            st.subheader(
                parent_a
            )

        st.write(
            household[
                "address_line_1"
            ]
        )

        if household.get(
            "address_line_2"
        ):

            st.write(
                household[
                    "address_line_2"
                ]
            )

        st.write(
            f"{household['city']}, "
            f"{household['state']} "
            f"{household['zip_code']}"
        )

        st.write("")

        st.caption(
            f"{household['parent_a_email']} "
            f"• "
            f"{household['parent_a_phone']}"
        )

        if st.button(
            "Edit Household",
            key="edit_household",
        ):

            household_dialog()


st.divider()


# ---------------------------------------------------------
# Children section
# ---------------------------------------------------------

st.header(
    "Children"
)

if household is None:

    st.caption(
        "Complete household information "
        "before adding children."
    )

else:

    children = (
        st.session_state.children
    )

    if not children:

        st.info(
            "No children have been added yet."
        )

    for index, child in enumerate(
        children
    ):

        with st.container(
            border=True
        ):

            (
                name_col,
                edit_col,
                remove_col,
            ) = st.columns(
                [5, 1.25, 1.75]
            )

            with name_col:

                full_name = " ".join(
                    part
                    for part in [
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
                    ]
                    if part
                )

                st.subheader(
                    full_name
                )

                age = calculate_age(
                    child[
                        "date_of_birth"
                    ]
                )

                st.caption(
                    f"Grade {child['grade']} • "
                    f"{child['school']} • "
                    f"DOB: "
                    f"{child['date_of_birth'].strftime('%m/%d/%Y')} "
                    f"(Age {age})"
                )

                if child.get(
                    "receiving_confirmation",
                    False,
                ):

                    st.caption(
                        "✓ Receiving Confirmation "
                        "this year"
                    )

            with edit_col:

                if st.button(
                    "Edit",
                    key=(
                        f"edit_child_"
                        f"{index}"
                    ),
                    use_container_width=True,
                ):

                    child_dialog(
                        index
                    )

            with remove_col:

                if st.button(
                    "Remove",
                    key=(
                        f"remove_child_"
                        f"{index}"
                    ),
                    use_container_width=True,
                ):

                    st.session_state.children.pop(
                        index
                    )

                    st.rerun()

    if st.button(
        "＋ Add a Child",
        type="primary",
    ):

        child_dialog()


st.divider()


# ---------------------------------------------------------
# Review / submit
# ---------------------------------------------------------

st.header(
    "Review"
)

registration_ready = (
    st.session_state.household
    is not None
    and len(
        st.session_state.children
    ) > 0
)

if registration_ready:

    child_count = len(
        st.session_state.children
    )

    st.success(
        f"Household information complete • "
        f"{child_count} "
        f"{'child' if child_count == 1 else 'children'} "
        f"added"
    )

    review_button_text = (
        "Review & Save Changes"
        if (
            st.session_state.registration_mode
            == "existing"
        )
        else "Review & Submit"
    )

    if st.button(
        review_button_text,
        type="primary",
        use_container_width=True,
    ):

        review_dialog()

else:

    st.caption(
        "Complete household information "
        "and add at least one child "
        "before submitting."
    )

    st.button(
        "Review & Submit",
        disabled=True,
        use_container_width=True,
    )