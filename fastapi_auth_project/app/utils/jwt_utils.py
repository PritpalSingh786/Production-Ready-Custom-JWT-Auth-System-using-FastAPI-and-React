import uuid
from datetime import datetime, timedelta, timezone
import jwt
from app.config import settings

def _now() -> datetime:
    return datetime.now(timezone.utc)

def create_access_token(user, device_id=None, platform="web") -> str:
    payload = {
        "user_id": str(user.id),
        "device_id": str(device_id) if device_id else None,
        "platform": platform,
        "type": "access",
        "exp": _now() + timedelta(minutes=settings.ACCESS_TOKEN_LIFETIME),
        "iat": _now(),
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

def create_refresh_token(user, device_id=None, platform="web") -> str:
    payload = {
        "user_id": str(user.id),
        "device_id": str(device_id) if device_id else None,
        "platform": platform,
        "type": "refresh",
        "exp": _now() + timedelta(days=settings.REFRESH_TOKEN_LIFETIME),
        "iat": _now(),
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

def decode_token(token: str, token_type: str):
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            audience=settings.JWT_AUDIENCE,
            issuer=settings.JWT_ISSUER,
            options={"require": ["exp", "iat", "jti", "type"]},
        )
        if payload["type"] != token_type:
            return None
        return payload
    except Exception:
        return None