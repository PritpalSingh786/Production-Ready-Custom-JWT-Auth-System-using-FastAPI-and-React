
import uuid
from datetime import datetime, timedelta, timezone

import jwt

from app.config import settings
from app.redis_client import redis_client


def _now() -> datetime:
    return datetime.now(timezone.utc)


def get_token_version(user_id) -> int:
    """
    Returns the current token version for a user.
    A new user starts at version 0.
    """
    key = f"token-version:{user_id}"
    value = redis_client.get(key)
    return int(value) if value is not None else 0


def increment_token_version(user_id) -> int:
    """
    Invalidates all previously issued access and refresh tokens.
    """
    return redis_client.incr(f"token-version:{user_id}")


def blacklist_token_payload(payload: dict) -> bool:
    """Store a revoked JWT JTI in Redis until its original expiry."""
    jti = payload.get("jti")
    exp = payload.get("exp")
    if not jti or not exp:
        return False
    remaining = int(float(exp) - _now().timestamp())
    if remaining <= 0:
        return True  # An already-expired token needs no blacklist entry.
    # NX makes refresh-token rotation single-use even under concurrent requests.
    return bool(redis_client.set(
        f"token-blacklist:{jti}", "1", ex=remaining, nx=True
    ))


def is_token_blacklisted(jti: str) -> bool:
    return bool(redis_client.exists(f"token-blacklist:{jti}"))


def create_access_token(
    user,
    device_id=None,
    platform="web",
    token_version=0,
) -> str:
    now = _now()

    payload = {
        "user_id": str(user.id),
        "device_id": str(device_id) if device_id else None,
        "platform": platform,
        "type": "access",
        "ver": token_version,
        "exp": now + timedelta(minutes=settings.ACCESS_TOKEN_LIFETIME),
        "iat": now,
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
        "jti": str(uuid.uuid4()),
    }

    return jwt.encode(
        payload,
        settings.SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def create_refresh_token(
    user,
    device_id=None,
    platform="web",
    token_version=0,
) -> str:
    now = _now()

    payload = {
        "user_id": str(user.id),
        "device_id": str(device_id) if device_id else None,
        "platform": platform,
        "type": "refresh",
        "ver": token_version,
        "exp": now + timedelta(days=settings.REFRESH_TOKEN_LIFETIME),
        "iat": now,
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
        "jti": str(uuid.uuid4()),
    }

    return jwt.encode(
        payload,
        settings.SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def decode_token(token: str, token_type: str):
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            audience=settings.JWT_AUDIENCE,
            issuer=settings.JWT_ISSUER,
            options={
                "require": ["exp", "iat", "jti", "type"],
            },
        )

        if payload["type"] != token_type:
            return None

        return payload

    except Exception:
        return None
