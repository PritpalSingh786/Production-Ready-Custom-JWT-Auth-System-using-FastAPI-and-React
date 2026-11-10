import socketio

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates

from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.config import settings
from app.routers import users
from app.socketio_server import sio
from app.celery_app import celery_worker
from app.limiter import limiter

app = FastAPI(
    title="Auth Project",
    debug=settings.DEBUG
)

# Rate Limiter
app.state.limiter = limiter
app.add_exception_handler(
    RateLimitExceeded,
    _rate_limit_exceeded_handler
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.DOMAIN_URL,
        "http://localhost:8000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Templates
templates = Jinja2Templates(directory="templates")

# Users API Router
app.include_router(
    users.router,
    prefix="/api/users",
    tags=["users"]
)

# HTML Pages Router
app.include_router(
    users.pages_router,
    prefix="/api/users",
    tags=["authentication-pages"]
)

# Socket.IO
socket_app = socketio.ASGIApp(
    sio,
    other_asgi_app=app,
    socketio_path="ws/auth"
)
