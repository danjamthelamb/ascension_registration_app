from __future__ import annotations

import html
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

PARISH_NAME = "Ascension Catholic Church"
MINISTRY_NAME = "Faith Formation"
PARISH_ADDRESS = "905 Hickory Mills Rd"
PARISH_CITY_STATE_ZIP = "Hurricane, WV 25526"
PARISH_WEBSITE = "https://ascensionhurricane.org"

# Fill this in with the exact office hours you want shown
# in registration confirmation/update emails.
PARISH_OFFICE_HOURS = ""


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
# Shared email helpers
# ---------------------------------------------------------

def _safe(value) -> str:
    """HTML-escape a value before placing it in an HTML email."""

    return html.escape(str(value or ""))


def _compact_footer_plain() -> str:
    """Short footer for verification and recovery emails."""

    return (
        f"{PARISH_NAME}\n"
        f"{MINISTRY_NAME}\n"
        f"{PARISH_WEBSITE}"
    )


def _full_footer_plain() -> str:
    """Full footer for registration confirmation/update emails."""

    lines = [
        PARISH_NAME,
        MINISTRY_NAME,
        PARISH_ADDRESS,
        PARISH_CITY_STATE_ZIP,
    ]

    if PARISH_OFFICE_HOURS.strip():
        lines.append(
            f"Parish Office: {PARISH_OFFICE_HOURS}"
        )

    lines.append(PARISH_WEBSITE)

    return "\n".join(lines)


def _compact_footer_html() -> str:
    """Short HTML footer for verification and recovery emails."""

    return f"""
        <div style="
            margin-top: 30px;
            padding-top: 18px;
            border-top: 1px solid #D8D0C5;
            font-size: 13px;
            line-height: 1.6;
            color: #626A72;
        ">
            <strong style="color: #203A5C;">
                {_safe(PARISH_NAME)}
            </strong><br>
            {_safe(MINISTRY_NAME)}<br>
            <a
                href="{_safe(PARISH_WEBSITE)}"
                style="color: #203A5C;"
            >
                {_safe(PARISH_WEBSITE)}
            </a>
        </div>
    """


def _full_footer_html() -> str:
    """Full HTML footer for registration confirmation/update emails."""

    office_hours_html = ""

    if PARISH_OFFICE_HOURS.strip():
        office_hours_html = (
            f"<br>Parish Office: "
            f"{_safe(PARISH_OFFICE_HOURS)}"
        )

    return f"""
        <div style="
            margin-top: 32px;
            padding-top: 18px;
            border-top: 1px solid #D8D0C5;
            font-size: 13px;
            line-height: 1.6;
            color: #626A72;
        ">
            <strong style="color: #203A5C;">
                {_safe(PARISH_NAME)}
            </strong><br>
            {_safe(MINISTRY_NAME)}<br>
            {_safe(PARISH_ADDRESS)}<br>
            {_safe(PARISH_CITY_STATE_ZIP)}
            {office_hours_html}
            <br>
            <a
                href="{_safe(PARISH_WEBSITE)}"
                style="color: #203A5C;"
            >
                {_safe(PARISH_WEBSITE)}
            </a>
        </div>
    """


def _email_shell(
    content_html: str,
    footer_html: str,
) -> str:
    """
    Wrap email content in a restrained HTML layout.

    Inline CSS is used because it has the best support
    across common email clients.
    """

    return f"""
    <!doctype html>
    <html>
        <body style="
            margin: 0;
            padding: 0;
            background-color: #FFFFFF;
        ">
            <div style="
                max-width: 620px;
                margin: 0 auto;
                padding: 28px 22px;
                font-family: Arial, Helvetica, sans-serif;
                font-size: 16px;
                line-height: 1.6;
                color: #3F4750;
            ">
                {content_html}
                {footer_html}
            </div>
        </body>
    </html>
    """


def _verification_code_html(
    verification_code: str,
) -> str:
    """Render a one-time verification code prominently."""

    return f"""
        <div style="
            margin: 20px 0 18px 0;
            padding: 16px 20px;
            background-color: #F6F2EA;
            border: 1px solid #D8D0C5;
            border-radius: 8px;
            text-align: center;
            color: #203A5C;
            font-family: 'Courier New', Courier, monospace;
            font-size: 30px;
            line-height: 1.2;
            font-weight: 700;
            letter-spacing: 6px;
        ">
            {_safe(verification_code)}
        </div>
    """


# ---------------------------------------------------------
# Core email sender
# ---------------------------------------------------------

def _send_email(
    recipient: str,
    subject: str,
    body: str,
    html_body: str | None = None,
) -> None:
    """
    Send an email using the registration Gmail account.

    Every message includes a plain-text version. When
    html_body is supplied, it is added as an HTML alternative.
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

    if html_body:
        message.add_alternative(
            html_body,
            subtype="html",
        )

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
# Household verification code email
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

    subject = "Your Ascension verification code"

    body = f"""
Hello,

We received a request to return to your family's Faith Formation
registration at Ascension Catholic Church.

Your verification code is:

{verification_code}

This code will expire in {expires_minutes} minutes.

Household ID: {household_reference}

If you did not request access to this registration,
no action is needed.

{_compact_footer_plain()}
""".strip()

    content_html = f"""
        <p style="margin-top: 0;">Hello,</p>

        <p>
            We received a request to return to your family's
            Faith Formation registration at
            <strong>{_safe(PARISH_NAME)}</strong>.
        </p>

        <p style="
            margin-bottom: 6px;
            font-weight: 700;
            color: #203A5C;
        ">
            Your verification code:
        </p>

        {_verification_code_html(verification_code)}

        <p style="
            margin-top: 0;
            font-size: 14px;
            color: #626A72;
        ">
            This code will expire in
            {_safe(expires_minutes)} minutes.
        </p>

        <p>
            Household ID:
            <strong style="color: #203A5C;">
                {_safe(household_reference)}
            </strong>
        </p>

        <p>
            If you did not request access to this registration,
            no action is needed.
        </p>
    """

    html_body = _email_shell(
        content_html,
        _compact_footer_html(),
    )

    _send_email(
        recipient=recipient,
        subject=subject,
        body=body,
        html_body=html_body,
    )


# ---------------------------------------------------------
# Admin verification code email
# ---------------------------------------------------------

def send_admin_verification_email(
    recipient: str,
    verification_code: str,
    expires_minutes: int = 10,
) -> None:
    """
    Send a one-time admin login code.
    """

    subject = "Ascension Registration admin login code"

    body = f"""
Hello,

A request was made to sign in to the Ascension Registration
administration area.

Your admin login code is:

{verification_code}

This code will expire in {expires_minutes} minutes.

If you did not request this login,
no action is needed.

{_compact_footer_plain()}
""".strip()

    content_html = f"""
        <p style="margin-top: 0;">Hello,</p>

        <p>
            A request was made to sign in to the
            Ascension Registration administration area.
        </p>

        <p style="
            margin-bottom: 6px;
            font-weight: 700;
            color: #203A5C;
        ">
            Your admin login code:
        </p>

        {_verification_code_html(verification_code)}

        <p style="
            margin-top: 0;
            font-size: 14px;
            color: #626A72;
        ">
            This code will expire in
            {_safe(expires_minutes)} minutes.
        </p>

        <p>
            If you did not request this login,
            no action is needed.
        </p>
    """

    html_body = _email_shell(
        content_html,
        _compact_footer_html(),
    )

    _send_email(
        recipient=recipient,
        subject=subject,
        body=body,
        html_body=html_body,
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
    """

    if not household_references:
        raise ValueError(
            "At least one Household ID is required "
            "to send a recovery email."
        )

    subject = "Your Ascension Household ID"

    if len(household_references) == 1:
        household_reference = household_references[0]

        body = f"""
Hello,

We received a request to recover your Ascension
Faith Formation Household ID.

Your Household ID is:

{household_reference}

Use this ID on the Ascension Registration page to return
to your family's registration.

For security, you will still be asked to verify your email
before any household information is displayed.

If you did not request your Household ID,
no action is needed.

{_compact_footer_plain()}
""".strip()

        content_html = f"""
            <p style="margin-top: 0;">Hello,</p>

            <p>
                We received a request to recover your Ascension
                Faith Formation Household ID.
            </p>

            <p style="
                margin-bottom: 6px;
                font-weight: 700;
                color: #203A5C;
            ">
                Your Household ID:
            </p>

            <div style="
                margin: 14px 0 20px 0;
                padding: 14px 18px;
                background-color: #F6F2EA;
                border: 1px solid #D8D0C5;
                border-radius: 8px;
                color: #203A5C;
                font-size: 20px;
                font-weight: 700;
            ">
                {_safe(household_reference)}
            </div>

            <p>
                Use this ID on the Ascension Registration page
                to return to your family's registration.
            </p>

            <p style="font-size: 14px; color: #626A72;">
                For security, you will still be asked to verify
                your email before any household information
                is displayed.
            </p>

            <p>
                If you did not request your Household ID,
                no action is needed.
            </p>
        """

    else:
        household_lines = "\n".join(
            f"- {reference}"
            for reference in household_references
        )

        household_items_html = "".join(
            f"""
            <li style="margin-bottom: 6px;">
                <strong style="color: #203A5C;">
                    {_safe(reference)}
                </strong>
            </li>
            """
            for reference in household_references
        )

        body = f"""
Hello,

We received a request to recover your Ascension
Faith Formation Household ID.

Your email address is associated with more than one
household registration.

Your Household IDs are:

{household_lines}

Use the appropriate ID on the Ascension Registration page
to return to that household registration.

For security, you will still be asked to verify your email
before any household information is displayed.

If you did not request your Household IDs,
no action is needed.

{_compact_footer_plain()}
""".strip()

        content_html = f"""
            <p style="margin-top: 0;">Hello,</p>

            <p>
                We received a request to recover your Ascension
                Faith Formation Household ID.
            </p>

            <p>
                Your email address is associated with more than
                one household registration.
            </p>

            <p style="
                margin-bottom: 6px;
                font-weight: 700;
                color: #203A5C;
            ">
                Your Household IDs:
            </p>

            <div style="
                margin: 14px 0 20px 0;
                padding: 14px 20px;
                background-color: #F6F2EA;
                border: 1px solid #D8D0C5;
                border-radius: 8px;
            ">
                <ul style="margin: 0; padding-left: 22px;">
                    {household_items_html}
                </ul>
            </div>

            <p>
                Use the appropriate ID on the Ascension Registration
                page to return to that household registration.
            </p>

            <p style="font-size: 14px; color: #626A72;">
                For security, you will still be asked to verify
                your email before any household information
                is displayed.
            </p>

            <p>
                If you did not request your Household IDs,
                no action is needed.
            </p>
        """

    html_body = _email_shell(
        content_html,
        _compact_footer_html(),
    )

    _send_email(
        recipient=recipient,
        subject=subject,
        body=body,
        html_body=html_body,
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

    subject = "Faith Formation registration received"

    child_lines = []
    child_items_html = []

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

        grade = child.get("grade", "") or ""

        if grade:
            child_lines.append(
                f"- {full_name} — {grade}"
            )

            child_items_html.append(
                f"""
                <li style="margin-bottom: 6px;">
                    <strong>{_safe(full_name)}</strong>
                    — {_safe(grade)}
                </li>
                """
            )

        else:
            child_lines.append(
                f"- {full_name}"
            )

            child_items_html.append(
                f"""
                <li style="margin-bottom: 6px;">
                    <strong>{_safe(full_name)}</strong>
                </li>
                """
            )

    children_text = "\n".join(child_lines)
    children_html = "".join(child_items_html)

    body = f"""
Thank you for registering your family with Ascension Catholic Church.

Your Faith Formation registration has been received.

Household ID:

{household_reference}

Children included in this registration:

{children_text}

Please keep your Household ID. You can use it to return
to your household registration and make changes later.

If you lose your Household ID, you can recover it using
the email address associated with your registration.

{_full_footer_plain()}
""".strip()

    content_html = f"""
        <p style="
            margin-top: 0;
            font-size: 20px;
            font-weight: 700;
            color: #203A5C;
        ">
            Registration received
        </p>

        <p>
            Thank you for registering your family with
            <strong>{_safe(PARISH_NAME)}</strong>.
            Your Faith Formation registration has been received.
        </p>

        <p style="
            margin-bottom: 6px;
            font-weight: 700;
            color: #203A5C;
        ">
            Household ID
        </p>

        <div style="
            margin: 14px 0 22px 0;
            padding: 14px 18px;
            background-color: #F6F2EA;
            border: 1px solid #D8D0C5;
            border-radius: 8px;
            color: #203A5C;
            font-size: 20px;
            font-weight: 700;
        ">
            {_safe(household_reference)}
        </div>

        <p style="
            margin-bottom: 6px;
            font-weight: 700;
            color: #203A5C;
        ">
            Children included in this registration
        </p>

        <ul style="margin-top: 8px; padding-left: 22px;">
            {children_html}
        </ul>

        <p>
            Please keep your Household ID. You can use it
            to return to your household registration and
            make changes later.
        </p>

        <p>
            If you lose your Household ID, you can recover it
            using the email address associated with your registration.
        </p>
    """

    html_body = _email_shell(
        content_html,
        _full_footer_html(),
    )

    _send_email(
        recipient=recipient,
        subject=subject,
        body=body,
        html_body=html_body,
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

    subject = "Your Faith Formation registration was updated"

    body = f"""
Hello,

Your Ascension Catholic Church Faith Formation registration
has been updated successfully.

Household ID:

{household_reference}

Please keep this Household ID for future access.

If you lose your Household ID, you can recover it using
the email address associated with your registration.

{_full_footer_plain()}
""".strip()

    content_html = f"""
        <p style="
            margin-top: 0;
            font-size: 20px;
            font-weight: 700;
            color: #203A5C;
        ">
            Registration updated
        </p>

        <p>
            Your Ascension Catholic Church Faith Formation
            registration has been updated successfully.
        </p>

        <p style="
            margin-bottom: 6px;
            font-weight: 700;
            color: #203A5C;
        ">
            Household ID
        </p>

        <div style="
            margin: 14px 0 22px 0;
            padding: 14px 18px;
            background-color: #F6F2EA;
            border: 1px solid #D8D0C5;
            border-radius: 8px;
            color: #203A5C;
            font-size: 20px;
            font-weight: 700;
        ">
            {_safe(household_reference)}
        </div>

        <p>
            Please keep this Household ID for future access.
        </p>

        <p>
            If you lose your Household ID, you can recover it
            using the email address associated with your registration.
        </p>
    """

    html_body = _email_shell(
        content_html,
        _full_footer_html(),
    )

    _send_email(
        recipient=recipient,
        subject=subject,
        body=body,
        html_body=html_body,
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

    subject = "Ascension Registration Email Test"

    body = f"""
This is a test email from the Ascension Registration App.

If you received this message, the Gmail email service
is configured correctly.

{_compact_footer_plain()}
""".strip()

    content_html = """
        <p style="margin-top: 0;">
            This is a test email from the
            <strong>Ascension Registration App</strong>.
        </p>

        <p>
            If you received this message, the Gmail email
            service is configured correctly.
        </p>
    """

    html_body = _email_shell(
        content_html,
        _compact_footer_html(),
    )

    _send_email(
        recipient=recipient,
        subject=subject,
        body=body,
        html_body=html_body,
    )
