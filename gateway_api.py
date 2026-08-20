from __future__ import annotations

import os
import secrets

from fastapi import Depends, FastAPI, Header, HTTPException, status
from pydantic import BaseModel
import streamlit as st

from db import (
    claim_next_queued_recipient,
    claim_next_queued_test_recipient,
    cancel_claimed_test_recipient,
    release_claimed_recipient,
    get_gateway_queue_summary,
    mark_recipient_failed,
    mark_recipient_sent,
    mark_recipient_submitted,
)


APP_NAME = "Ascension Messenger Gateway DEV"


def _load_gateway_token() -> str:
    """
    Resolve the DEV gateway bearer token.

    Priority:
        1. GATEWAY_API_TOKEN environment variable
        2. [gateway].token in Streamlit secrets

    Streamlit handles TOML parsing; this file does not import
    tomllib, tomli, or configparser.
    """

    environment_token = (
        os.getenv(
            "GATEWAY_API_TOKEN",
            "",
        )
        .strip()
    )

    if environment_token:
        return environment_token

    try:
        file_token = str(
            st.secrets[
                "gateway"
            ][
                "token"
            ]
        ).strip()

        if file_token:
            return file_token

    except Exception as exc:
        raise RuntimeError(
            "No gateway token was found in GATEWAY_API_TOKEN "
            "or [gateway].token in .streamlit/secrets.toml."
        ) from exc

    raise RuntimeError(
        "No gateway token was found in GATEWAY_API_TOKEN "
        "or [gateway].token in .streamlit/secrets.toml."
    )


GATEWAY_TOKEN = _load_gateway_token()


app = FastAPI(
    title=APP_NAME,
    docs_url=None,
    redoc_url=None,
)


def require_gateway_token(
    authorization: str | None = Header(
        default=None
    ),
) -> None:

    expected = (
        f"Bearer {GATEWAY_TOKEN}"
    )

    if (
        authorization is None
        or not secrets.compare_digest(
            authorization,
            expected,
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid gateway token.",
        )


class RecipientUpdate(BaseModel):
    claim_token: str
    transport: str = "android_auto"


class RecipientFailure(RecipientUpdate):
    error_message: str


@app.get("/health")
def health() -> dict:
    return {
        "ok": True,
        "service": APP_NAME,
    }


@app.get(
    "/gateway/summary",
    dependencies=[
        Depends(
            require_gateway_token
        )
    ],
)
def gateway_summary() -> dict:
    return get_gateway_queue_summary()


@app.post(
    "/gateway/claim-next-test",
    dependencies=[
        Depends(
            require_gateway_token
        )
    ],
)
def claim_next_test() -> dict:
    return {
        "recipient":
            claim_next_queued_test_recipient(),
    }


@app.post(
    "/gateway/claim-next",
    dependencies=[
        Depends(
            require_gateway_token
        )
    ],
)
def claim_next() -> dict:
    return {
        "recipient":
            claim_next_queued_recipient(),
    }


@app.post(
    "/gateway/recipients/{recipient_id}/released",
    dependencies=[
        Depends(
            require_gateway_token
        )
    ],
)
def recipient_released(
    recipient_id: int,
    update: RecipientUpdate,
) -> dict:

    updated = (
        release_claimed_recipient(
            recipient_id,
            update.claim_token,
        )
    )

    if not updated:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Recipient is not a claimed real household message "
                "owned by this claim token."
            ),
        )

    return {
        "ok": True,
        "status": "queued",
    }


@app.post(
    "/gateway/recipients/{recipient_id}/cancelled",
    dependencies=[
        Depends(
            require_gateway_token
        )
    ],
)
def recipient_cancelled(
    recipient_id: int,
    update: RecipientUpdate,
) -> dict:

    updated = (
        cancel_claimed_test_recipient(
            recipient_id,
            update.claim_token,
        )
    )

    if not updated:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Recipient is not a claimed DEV test owned "
                "by this claim token."
            ),
        )

    return {
        "ok": True,
        "status": "cancelled",
    }


@app.post(
    "/gateway/recipients/{recipient_id}/submitted",
    dependencies=[
        Depends(
            require_gateway_token
        )
    ],
)
def recipient_submitted(
    recipient_id: int,
    update: RecipientUpdate,
) -> dict:

    updated = (
        mark_recipient_submitted(
            recipient_id,
            update.claim_token,
            update.transport,
        )
    )

    if not updated:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Recipient is not in a valid claimed state "
                "for this token."
            ),
        )

    return {
        "ok": True,
        "status": "submitted",
    }


@app.post(
    "/gateway/recipients/{recipient_id}/sent",
    dependencies=[
        Depends(
            require_gateway_token
        )
    ],
)
def recipient_sent(
    recipient_id: int,
    update: RecipientUpdate,
) -> dict:

    updated = (
        mark_recipient_sent(
            recipient_id,
            update.claim_token,
            update.transport,
        )
    )

    if not updated:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Recipient is not in a valid state "
                "for this token."
            ),
        )

    return {
        "ok": True,
        "status": "sent",
    }


@app.post(
    "/gateway/recipients/{recipient_id}/failed",
    dependencies=[
        Depends(
            require_gateway_token
        )
    ],
)
def recipient_failed(
    recipient_id: int,
    update: RecipientFailure,
) -> dict:

    updated = (
        mark_recipient_failed(
            recipient_id,
            update.claim_token,
            update.error_message,
            update.transport,
        )
    )

    if not updated:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Recipient is not in a valid state "
                "for this token."
            ),
        )

    return {
        "ok": True,
        "status": "failed",
    }
