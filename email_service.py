from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage

import streamlit as st


# ---------------------------------------------------------
# Email configuration
# ---------------------------------------------------------

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 465

SENDER_NAME = "Ascension Registration"


# ---------------------------------------------------------
# Credentials
# ---------------------------------------------------------

def _get_email_credentials() -> tuple[str, str]:
    """
    Read the Gmail address and App Password
    from Streamlit secrets.
    """

    try:
        email_address = st.secrets["email"]["address"]
        app_password = st.secrets["email"]["app_password"]

    except KeyError as exc:
        raise RuntimeError(
            "Email credentials are missing from "
            ".streamlit/secrets.toml."
        ) from exc

    return email_address, app_password


# ---------------------------------------------------------
# Core email sender
# ---------------------------------------------------------

def _send_email(
    recipient: str,
    subject: str,
    body: str,
) -> None:
    """
    Send a plain-text email using the registration
    Gmail account.
    """

    sender_email, app_password = (
        _get_email_credentials()
    )

    message = EmailMessage()

    message["From"] = (
        f"{SENDER_NAME} <{sender_email}>"
    )

    message["To"] = recipient
    message["Subject"] = subject

    message.set_content(body)

    context = ssl.create_default_context()

    try:

        with smtplib.SMTP_SSL(
            SMTP_SERVER,
            SMTP_PORT,
            context=context,
        ) as smtp:

            smtp.login(
                sender_email,
                app_password,
            )

            smtp.send_message(message)

    except smtplib.SMTPAuthenticationError as exc:
        raise RuntimeError(
            "Gmail rejected the email credentials. "
            "Check the Gmail address and App Password."
        ) from exc

    except smtplib.SMTPException as exc:
        raise RuntimeError(
            f"Email could not be sent: {exc}"
        ) from exc


# ---------------------------------------------------------
# Verification code email
# ---------------------------------------------------------

def send_verification_email(
    recipient: str,
    verification_code: str,
    household_reference: str,
    expires_minutes: int = 10,
) -> None:
    """
    Send the one-time verification code used to
    access an existing household registration.
    """

    subject = (
        "Ascension Registration Verification Code"
    )

    body = f"""
Hello,

You requested access to your Ascension household registration.

Household ID:

{household_reference}

Your verification code is:

{verification_code}

This code will expire in {expires_minutes} minutes.

If you did not request access to this household,
you can ignore this email.

Ascension Catholic Church
Hurricane, West Virginia
""".strip()

    _send_email(
        recipient=recipient,
        subject=subject,
        body=body,
    )


# ---------------------------------------------------------
# Household ID recovery email
# ---------------------------------------------------------

def send_household_id_recovery(
    recipient: str,
    household_references: list[str],
) -> None:
    """
    Send one or more Household IDs associated
    with the supplied email address.

    This function should only be called when the
    database has found at least one matching household.
    """

    if not household_references:
        raise ValueError(
            "At least one Household ID is required "
            "to send a recovery email."
        )

    subject = (
        "Your Ascension Registration Household ID"
    )

    if len(household_references) == 1:

        household_text = household_references[0]

        body = f"""
Hello,

We received a request to recover your Ascension Registration
Household ID.

Your Household ID is:

{household_text}

You can use this ID on the Ascension Registration page to
return to your household registration.

For security, you will still be asked to verify your email
before your household information is displayed.

If you did not request your Household ID, you can ignore
this email.

Ascension Catholic Church
Hurricane, West Virginia
""".strip()

    else:

        household_lines = "\n".join(
            f"- {reference}"
            for reference in household_references
        )

        body = f"""
Hello,

We received a request to recover your Ascension Registration
Household ID.

Your email address is associated with more than one
household registration.

Your Household IDs are:

{household_lines}

You can use the appropriate ID on the Ascension Registration
page to return to that household registration.

For security, you will still be asked to verify your email
before any household information is displayed.

If you did not request your Household IDs, you can ignore
this email.

Ascension Catholic Church
Hurricane, West Virginia
""".strip()

    _send_email(
        recipient=recipient,
        subject=subject,
        body=body,
    )


# ---------------------------------------------------------
# Registration confirmation email
# ---------------------------------------------------------

def send_registration_confirmation(
    recipient: str,
    household_reference: str,
    children: list[dict],
) -> None:
    """
    Send a confirmation after a new registration
    has been successfully submitted.
    """

    subject = (
        "Ascension Registration Received"
    )

    child_lines = []

    for child in children:

        full_name = " ".join(
            part
            for part in [
                child.get("first_name", ""),
                child.get("middle_name", ""),
                child.get("last_name", ""),
            ]
            if part
        )

        child_lines.append(
            f"- {full_name}"
        )

    children_text = "\n".join(
        child_lines
    )

    body = f"""
Thank you for registering with Ascension Catholic Church.

Your registration has been received.

Your Household ID is:

{household_reference}

Children included in this registration:

{children_text}

Please keep your Household ID. You can use it to return
to your household registration and make changes later.

If you lose your Household ID, you can recover it using
the email address associated with your registration.

Ascension Catholic Church
Hurricane, West Virginia
""".strip()

    _send_email(
        recipient=recipient,
        subject=subject,
        body=body,
    )


# ---------------------------------------------------------
# Updated-registration confirmation
# ---------------------------------------------------------

def send_update_confirmation(
    recipient: str,
    household_reference: str,
) -> None:
    """
    Send confirmation after an existing household
    registration has been updated.
    """

    subject = (
        "Ascension Registration Updated"
    )

    body = f"""
Hello,

Your Ascension Catholic Church household registration
has been updated successfully.

Household ID:

{household_reference}

Please keep this Household ID for future access.

If you lose your Household ID, you can recover it using
the email address associated with your registration.

Ascension Catholic Church
Hurricane, West Virginia
""".strip()

    _send_email(
        recipient=recipient,
        subject=subject,
        body=body,
    )


# ---------------------------------------------------------
# Development test
# ---------------------------------------------------------

def send_test_email(
    recipient: str,
) -> None:
    """
    Send a simple test message to confirm that
    Gmail SMTP is configured correctly.
    """

    subject = (
        "Ascension Registration Email Test"
    )

    body = """
This is a test email from the Ascension Registration App.

If you received this message, the Gmail email service
is configured correctly.

Ascension Catholic Church
Hurricane, West Virginia
""".strip()

    _send_email(
        recipient=recipient,
        subject=subject,
        body=body,
    )