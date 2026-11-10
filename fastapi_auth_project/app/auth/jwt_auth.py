
from dataclasses import dataclass
from typing import Optional

import redis

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.redis_client import redis_client
from app.utils.jwt_utils import decode_token, get_token_version, is_token_blacklisted


bearer_scheme = HTTPBearer(auto_error=False)


@dataclass
class AuthContext:
    user: User
    token: str
    device_id: Optional[str]
    platform: Optional[str]


async def get_current_auth(
    creds: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> AuthContext:

    if creds is None or creds.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header",
        )

    payload = decode_token(creds.credentials, "access")

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    # Reject access tokens explicitly revoked by logout or another security action.
    try:
        if is_token_blacklisted(payload.get("jti", "")):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token revoked. Please login again.",
            )
    except redis.RedisError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service temporarily unavailable",
        )

    user_id = payload.get("user_id")

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    # Check whether this token has been revoked.
    try:
        current_version = get_token_version(user_id)
    except (redis.RedisError, ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service temporarily unavailable",
        )

    token_version = payload.get("ver", 0)

    if token_version != current_version:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session revoked. Please login again.",
        )

    user = db.query(User).filter(
        User.id == user_id,
        User.is_deleted.is_(False),
        User.is_active.is_(True),
    ).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    return AuthContext(
        user=user,
        token=creds.credentials,
        device_id=payload.get("device_id"),
        platform=payload.get("platform"),
    )
