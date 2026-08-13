from datetime import date

import streamlit as st

from db import (
    get_registration_by_reference,
    init_db,
    save_registration,
    update_registration,
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
# Existing household dialog
# ---------------------------------------------------------

@st.dialog("Return to Existing Household")
def existing_household_dialog():

    st.write(
        "Enter the Household ID from your previous registration."
    )

    household_reference = st.text_input(
        "Household ID",
        placeholder="ASC-XXXXXX",
    )

    st.caption(
        "During development, the Household ID is sufficient. "
        "Email verification will be added before deployment."
    )

    if st.button(
        "Find Household",
        type="primary",
        use_container_width=True,
    ):

        if not household_reference.strip():
            st.error("Please enter your Household ID.")
            return

        result = get_registration_by_reference(
            household_reference
        )

        if result is None:
            st.error(
                "We couldn't find a household with that ID."
            )
            return

        household, children = result

        # Put the editable household information
        # back into session state.
        st.session_state.household = {
            "parent_a_first_name":
                household["parent_a_first_name"],
            "parent_a_last_name":
                household["parent_a_last_name"],
            "parent_a_email":
                household["parent_a_email"],
            "parent_a_phone":
                household["parent_a_phone"],

            "parent_b_first_name":
                household["parent_b_first_name"] or "",
            "parent_b_last_name":
                household["parent_b_last_name"] or "",
            "parent_b_email":
                household["parent_b_email"] or "",
            "parent_b_phone":
                household["parent_b_phone"] or "",

            "address_line_1":
                household["address_line_1"],
            "address_line_2":
                household["address_line_2"] or "",
            "city":
                household["city"],
            "state":
                household["state"],
            "zip_code":
                household["zip_code"],
        }

        # These children include their existing child_id values.
        st.session_state.children = children

        st.session_state.existing_household_id = (
            household["household_id"]
        )

        st.session_state.existing_household_reference = (
            household["household_reference"]
        )

        st.session_state.registration_mode = "existing"

        st.rerun()


# ---------------------------------------------------------
# Household dialog
# ---------------------------------------------------------

@st.dialog("Household Information")
def household_dialog():

    household = st.session_state.household or {}

    with st.form(
        "household_form",
        enter_to_submit=False,
    ):

        st.subheader("Parent / Guardian A")
        st.caption("Required")

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

        st.subheader("Parent / Guardian B")
        st.caption("Optional")

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

        st.subheader("Home Address")

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

        city_col, state_col, zip_col = st.columns(
            [2, 1, 1]
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

            st.session_state.household = {
                "parent_a_first_name":
                    parent_a_first_name.strip(),
                "parent_a_last_name":
                    parent_a_last_name.strip(),
                "parent_a_email":
                    parent_a_email.strip(),
                "parent_a_phone":
                    parent_a_phone.strip(),

                "parent_b_first_name":
                    parent_b_first_name.strip(),
                "parent_b_last_name":
                    parent_b_last_name.strip(),
                "parent_b_email":
                    parent_b_email.strip(),
                "parent_b_phone":
                    parent_b_phone.strip(),

                "address_line_1":
                    address_line_1.strip(),
                "address_line_2":
                    address_line_2.strip(),
                "city":
                    city.strip(),
                "state":
                    state.strip().upper(),
                "zip_code":
                    zip_code.strip(),
            }

            st.rerun()


# ---------------------------------------------------------
# Child dialog
# ---------------------------------------------------------

@st.dialog("Child Information")
def child_dialog(
    child_index: int | None = None,
):

    editing = child_index is not None

    if editing:
        child = st.session_state.children[
            child_index
        ]
    else:
        child = {}

    household = st.session_state.household or {}

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
        grade_index = grades.index(
            existing_grade
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

        receiving_confirmation = st.toggle(
            "Receiving Confirmation this year",
            value=child.get(
                "receiving_confirmation",
                False,
            ),
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

            # IMPORTANT:
            # If this child already exists in the database,
            # preserve the database child_id when they are edited.
            #
            # New children won't have a child_id yet.
            if (
                editing
                and child.get("child_id")
                is not None
            ):
                child_data["child_id"] = (
                    child["child_id"]
                )

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

    household = st.session_state.household
    children = st.session_state.children

    editing_existing = (
        st.session_state.registration_mode
        == "existing"
    )

    st.subheader("Household")

    parent_a = (
        f"{household['parent_a_first_name']} "
        f"{household['parent_a_last_name']}"
    )

    st.write(f"**{parent_a}**")
    st.write(household["parent_a_email"])
    st.write(household["parent_a_phone"])

    if (
        household.get("parent_b_first_name")
        or household.get("parent_b_last_name")
    ):
        parent_b = (
            f"{household.get('parent_b_first_name', '')} "
            f"{household.get('parent_b_last_name', '')}"
        ).strip()

        st.write("")
        st.write(f"**{parent_b}**")

        if household.get("parent_b_email"):
            st.write(
                household["parent_b_email"]
            )

        if household.get("parent_b_phone"):
            st.write(
                household["parent_b_phone"]
            )

    st.write("")
    st.write(
        household["address_line_1"]
    )

    if household.get("address_line_2"):
        st.write(
            household["address_line_2"]
        )

    st.write(
        f"{household['city']}, "
        f"{household['state']} "
        f"{household['zip_code']}"
    )

    st.divider()

    st.subheader("Children")

    for child in children:

        full_name = " ".join(
            part
            for part in [
                child["first_name"],
                child.get(
                    "middle_name",
                    "",
                ),
                child["last_name"],
            ]
            if part
        )

        age = calculate_age(
            child["date_of_birth"]
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

        try:

            # -----------------------------------------
            # Existing household
            # -----------------------------------------

            if editing_existing:

                update_registration(
                    st.session_state
                    .existing_household_id,
                    household,
                    children,
                )

                st.session_state\
                    .submitted_household_id = (
                        st.session_state
                        .existing_household_id
                    )

                st.session_state\
                    .submitted_household_reference = (
                        st.session_state
                        .existing_household_reference
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

                st.session_state\
                    .submitted_household_id = (
                        household_id
                    )

                st.session_state\
                    .submitted_household_reference = (
                        household_reference
                    )

            # Clear editable data after successful save.
            st.session_state.household = None
            st.session_state.children = []

            st.rerun()

        except Exception as exc:
            st.error(
                "Registration could not be "
                f"submitted: {exc}"
            )


# ---------------------------------------------------------
# Registration complete
# ---------------------------------------------------------

if (
    st.session_state
    .submitted_household_id
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
        st.session_state
        .submitted_household_reference,
        language=None,
    )

    st.info(
        "Please keep this Household ID. "
        "You'll be able to use it later "
        "to return to your household "
        "and make changes."
    )

    if st.button(
        "Return to Start"
    ):

        st.session_state.household = None
        st.session_state.children = []

        st.session_state\
            .submitted_household_id = None

        st.session_state\
            .submitted_household_reference = None

        st.session_state\
            .existing_household_id = None

        st.session_state\
            .existing_household_reference = None

        st.session_state\
            .registration_mode = None

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

    with col1:

        if st.button(
            "Start a New Registration",
            type="primary",
            use_container_width=True,
        ):

            st.session_state.household = None
            st.session_state.children = []

            st.session_state\
                .existing_household_id = None

            st.session_state\
                .existing_household_reference = None

            st.session_state\
                .registration_mode = "new"

            st.rerun()

    with col2:

        if st.button(
            "Return to Existing Household",
            use_container_width=True,
        ):
            existing_household_dialog()

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

st.header("Household")

household = st.session_state.household

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
            household["address_line_1"]
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

st.header("Children")

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
                        child["first_name"],
                        child.get(
                            "middle_name",
                            "",
                        ),
                        child["last_name"],
                    ]
                    if part
                )

                st.subheader(
                    full_name
                )

                age = calculate_age(
                    child["date_of_birth"]
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
                    st.session_state\
                        .children.pop(
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

st.header("Review")

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
            st.session_state
            .registration_mode
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