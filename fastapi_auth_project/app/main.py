import socketio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
# main.py ke top par imports ke saath
from app.celery_app import celery_worker  # <-- Ye line add karni hai

from app.config import settings
from app.routers import users
from app.socketio_server import sio

limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="Auth Project", debug=settings.DEBUG)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL, "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

templates = Jinja2Templates(directory="templates")
app.include_router(users.router, prefix="/api/users", tags=["users"])

# Socket.IO ASGI mount mapped to /ws/auth
socket_app = socketio.ASGIApp(sio, other_asgi_app=app, socketio_path="ws/auth")