import jwt
import socketio
from app.config import settings

# Redis manager lets Celery workers publish logout events to the ASGI process.
redis_manager = socketio.AsyncRedisManager(settings.REDIS_URL)
sio = socketio.AsyncServer(
    async_mode="asgi",
    client_manager=redis_manager,
    cors_allowed_origins=[settings.DATABASE_URL],
    logger=False,
    engineio_logger=False,
)


def _extract_token(environ: dict) -> str | None:
    query_string = environ.get("QUERY_STRING", "") or ""
    for item in query_string.split("&"):
        if item.startswith("token="):
            from urllib.parse import unquote
            return unquote(item.partition("=")[2])
    return None


@sio.event
async def connect(sid, environ, auth):
    token = _extract_token(environ)
    if not token and isinstance(auth, dict):
        token = auth.get("token")
    if not token:
        return False

    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            audience=settings.JWT_AUDIENCE,
            issuer=settings.JWT_ISSUER,
            options={"require": ["exp", "iat", "jti", "type"]},
        )
        if payload.get("type") != "access":
            return False
    except jwt.PyJWTError:
        return False

    user_id = payload.get("user_id")
    device_id = payload.get("device_id")
    if not user_id or not device_id:
        return False

    room = f"user_{user_id}_{device_id}"
    await sio.enter_room(sid, room)
    await sio.save_session(sid, {
        "user_id": user_id,
        "device_id": device_id,
        "platform": payload.get("platform"),
        "room": room,
    })
    await sio.emit(
        "message",
        {"type": "CONNECTED", "message": "WebSocket connected successfully"},
        to=sid,
    )
    return True


@sio.event
async def disconnect(sid):
    try:
        session = await sio.get_session(sid)
        room = session.get("room")
        if room:
            await sio.leave_room(sid, room)
    except Exception:
        pass
