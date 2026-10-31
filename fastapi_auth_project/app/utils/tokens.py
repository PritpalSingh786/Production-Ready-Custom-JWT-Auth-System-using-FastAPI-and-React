import json
import secrets
from datetime import datetime, timezone
import jwt
from app.config import settings
from app.redis_client import redis_client

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)

def store_refresh_token(refresh_token_str, user, device_id=None, platform="web", device_name="", ip_address="") -> bool:
    try:
        payload = jwt.decode(
            refresh_token_str,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            audience=settings.JWT_AUDIENCE,
            issuer=settings.JWT_ISSUER,
        )
        user_tokens_key = f"hash-rt-for-user-{user.id}"
        token_data = {
            "jti": payload.get("jti"),
            "user_id": str(user.id),
            "device_id": str(device_id) if device_id else None,
            "platform": platform,
            "device_name": device_name,
            "ip_address": ip_address,
            "created_at": _utcnow().isoformat(),
        }
        redis_client.hset(user_tokens_key, payload.get("jti"), json.dumps(token_data))
        redis_client.expire(user_tokens_key, settings.REFRESH_TOKEN_LIFETIME * 86400)
        return True
    except Exception as e:
        print(f"Error storing token: {e}")
        return False

def generate_verification_token(user_id) -> str:
    token = secrets.token_urlsafe(32)
    key = f"email_verify:{user_id}:{token}"
    redis_client.setex(key, 300, json.dumps({"token": token, "user_id": str(user_id)}))
    return token

def verify_email_token(user_id, token) -> bool:
    return redis_client.get(f"email_verify:{user_id}:{token}") is not None

def delete_verify_email_token(user_id, token) -> None:
    redis_client.delete(f"email_verify:{user_id}:{token}")

def generate_password_reset_token(user_id) -> str:
    token = secrets.token_urlsafe(32)
    key = f"password_reset:{user_id}:{token}"
    redis_client.setex(key, 300, json.dumps({"token": token, "user_id": str(user_id)}))
    return token

def verify_password_reset_token(user_id, token) -> bool:
    return redis_client.get(f"password_reset:{user_id}:{token}") is not None

def delete_password_reset_token(user_id, token) -> None:
    redis_client.delete(f"password_reset:{user_id}:{token}")

def secure_generate_password_reset_token(user_id) -> str:
    token = secrets.token_urlsafe(32)
    redis_client.setex(f"pwd_reset:{user_id}", 180, token)
    return token

def secure_verify_password_reset_token(user_id, token) -> bool:
    stored = redis_client.get(f"pwd_reset:{user_id}")
    return stored is not None and stored == token

def delete_secure_password_reset_token(user_id, token) -> None:
    redis_client.delete(f"pwd_reset:{user_id}")