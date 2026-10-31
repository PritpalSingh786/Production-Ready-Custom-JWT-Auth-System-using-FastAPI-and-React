import socketio
import jwt
from app.config import settings

sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins=[settings.FRONTEND_URL, "http://localhost:3000"],
    logger=False,
    engineio_logger=False,
)

def _extract_token(environ: dict) -> str | None:
    qs = environ.get("QUERY_STRING", "") or ""
    if "token=" not in qs:
        return None
    return qs.split("token=")[1].split("&")[0]

@sio.event
async def connect(sid, environ, auth):
    token = _extract_token(environ)
    if not token:
        await sio.disconnect(sid)
        return False

    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            audience=settings.JWT_AUDIENCE,
            issuer=settings.JWT_ISSUER,
        )
        if payload.get("type") != "access":
            raise jwt.InvalidTokenError("Invalid token type")
    except Exception as e:
        print("JWT ERROR:", str(e))
        await sio.disconnect(sid)
        return False

    user_id = payload["user_id"]
    device_id = payload.get("device_id")
    if not device_id:
        await sio.disconnect(sid)
        return False

    room = f"user_{user_id}_{device_id}"
    await sio.enter_room(sid, room)
    
    await sio.save_session(
        sid,
        {
            "user_id": user_id,
            "device_id": device_id,
            "platform": payload.get("platform"),
            "room": room,
        },
    )

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