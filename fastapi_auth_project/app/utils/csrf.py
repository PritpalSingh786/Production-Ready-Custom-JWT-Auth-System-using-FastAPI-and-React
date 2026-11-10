import hashlib
import hmac
import os
import secrets
import time

from fastapi import HTTPException, Request


CSRF_COOKIE_NAME = "csrf_token"
CSRF_HEADER_NAME = "x-csrf-token"
CSRF_MAX_AGE = 3600


def _get_csrf_secret() -> bytes:
    secret = os.getenv("CSRF_SECRET_KEY")

    if not secret or len(secret) < 32:
        raise RuntimeError(
            "CSRF_SECRET_KEY must be configured with at least 32 characters"
        )

    return secret.encode("utf-8")


def generate_csrf_token() -> str:
    timestamp = str(int(time.time()))
    nonce = secrets.token_urlsafe(32)
    message = f"{timestamp}.{nonce}".encode("utf-8")

    signature = hmac.new(
        _get_csrf_secret(),
        message,
        hashlib.sha256,
    ).hexdigest()

    return f"{timestamp}.{nonce}.{signature}"


def validate_csrf_token(request: Request) -> None:
    cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
    header_token = request.headers.get(CSRF_HEADER_NAME)

    if not cookie_token or not header_token:
        raise HTTPException(status_code=403, detail="CSRF token missing")

    if not hmac.compare_digest(cookie_token, header_token):
        raise HTTPException(status_code=403, detail="Invalid CSRF token")

    try:
        timestamp, nonce, signature = cookie_token.split(".", 2)
        token_time = int(timestamp)
    except (ValueError, TypeError):
        raise HTTPException(status_code=403, detail="Invalid CSRF token")

    current_time = int(time.time())

    if token_time > current_time or current_time - token_time > CSRF_MAX_AGE:
        raise HTTPException(status_code=403, detail="CSRF token expired")

    message = f"{timestamp}.{nonce}".encode("utf-8")
    expected_signature = hmac.new(
        _get_csrf_secret(),
        message,
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(signature, expected_signature):
        raise HTTPException(status_code=403, detail="Invalid CSRF signature")
