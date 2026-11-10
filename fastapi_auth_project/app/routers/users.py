
import json
import uuid
from datetime import datetime, timezone

import bcrypt

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    Response,
    status,
)
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.auth.jwt_auth import AuthContext, get_current_auth
from app.config import settings
from app.database import get_db
from app.limiter import limiter
from app.models.user import User, Device
from app.redis_client import redis_client

from app.schemas.user import (
    RegisterRequest,
    RegisterResponse,
    RegisterResponseData,
    LoginRequest,
    LoginResponse,
    LoginUserData,
    RefreshRequest,
    RefreshResponse,
    LogoutRequest,
    LogoutResponse,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    PasswordChangeRequest,
    PasswordChangeResponse,
    SecurePasswordChangeRequest,
    AuthenticatedResponse,
    AuthenticatedUser,
)

from app.tasks.email_tasks import (
    send_email_task,
    send_forgot_password_email_task,
    send_new_login_alert_task,
    send_password_changed_email_task,
    logout_all_devices_task,
)

from app.utils.jwt_utils import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_token_version,
    increment_token_version,
)

from app.utils.tokens import (
    store_refresh_token,
    generate_verification_token,
    verify_email_token,
    delete_verify_email_token,
    generate_password_reset_token,
    verify_password_reset_token,
    delete_password_reset_token,
    secure_generate_password_reset_token,
    secure_verify_password_reset_token,
    delete_secure_password_reset_token,
)


router = APIRouter()
pages_router = APIRouter()

templates = Jinja2Templates(directory="templates")


# --------------------------------------------------
# PASSWORD HELPERS
# --------------------------------------------------

def _hash_password(password: str) -> str:
    return bcrypt.hashpw(
        password.encode("utf-8"),
        bcrypt.gensalt(),
    ).decode("utf-8")


def _check_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(
            password.encode("utf-8"),
            hashed.encode("utf-8"),
        )
    except (ValueError, TypeError):
        return False


# --------------------------------------------------
# CLIENT INFORMATION
# --------------------------------------------------

def _client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")

    if forwarded:
        return forwarded.split(",")[0].strip()[:64]

    return request.client.host if request.client else None


# --------------------------------------------------
# EMAIL VERIFICATION
# --------------------------------------------------

def _send_verification_email(user: User) -> bool:
    try:
        token = generate_verification_token(user.id)

        link = (
            f"{settings.DOMAIN_URL}/api/users/verify-email/"
            f"?user_id={user.user_id}&token={token}"
        )

        message = (
            f"Hello {user.user_id},\n\n"
            f"Please verify your email address using this link "
            f"(expires in 5 minutes):\n{link}"
        )

        send_email_task.delay(
            "Verify Your Email - 5 Minutes Expiry",
            message,
            [user.email],
        )

        return True

    except Exception:
        return False


def _render_error(request: Request, template: str, message: str):
    return templates.TemplateResponse(
        template,
        {
            "request": request,
            "message": message,
        },
        status_code=400,
    )


# --------------------------------------------------
# REGISTER
# --------------------------------------------------

@router.post(
    "/register/",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("3/minute")
def register(
    request: Request,
    payload: RegisterRequest,
    db: Session = Depends(get_db),
):

    if db.query(User).filter(
        User.user_id.ilike(payload.user_id)
    ).first():

        raise HTTPException(
            400,
            detail={"user_id": "userId already exists"},
        )

    if db.query(User).filter(
        User.email.ilike(str(payload.email))
    ).first():

        raise HTTPException(
            400,
            detail={"email": "Email already exists"},
        )

    user = User(
        user_id=payload.user_id,
        email=str(payload.email).lower(),
        hashed_password=_hash_password(payload.password),
        is_active=False,
        email_verified=False,
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    if not _send_verification_email(user):

        message = (
            "Registration successful, but verification email "
            "could not be queued. Please try logging in to resend it."
        )

    else:

        message = (
            "Registration successful. Please check your email "
            "for verification link (expires in 5 minutes)."
        )

    return RegisterResponse(
        success=True,
        message=message,
        data=RegisterResponseData(
            user_id=user.user_id,
            email=user.email,
        ),
    )


# --------------------------------------------------
# VERIFY EMAIL
# --------------------------------------------------

@router.get("/verify-email/", response_class=HTMLResponse)
def verify_email(
    request: Request,
    user_id: str | None = None,
    token: str | None = None,
    db: Session = Depends(get_db),
):

    if not user_id or not token:

        return _render_error(
            request,
            "users/email_verification_error.html",
            "Verification link is incomplete.",
        )

    user = db.query(User).filter(
        User.user_id == user_id
    ).first()

    if not user or not verify_email_token(user.id, token):

        return _render_error(
            request,
            "users/email_verification_error.html",
            "Verification link has expired or is invalid.",
        )

    user.email_verified = True
    user.is_active = True

    db.commit()

    delete_verify_email_token(user.id, token)

    return templates.TemplateResponse(
        "users/email_verification_success.html",
        {
            "request": request,
            "user_id": user.user_id,
            "email": user.email,
        },
    )


# --------------------------------------------------
# LOGIN
# --------------------------------------------------

@router.post("/login/", response_model=LoginResponse)
@limiter.limit("5/minute")
def login(
    request: Request,
    payload: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
):

    user = db.query(User).filter(
        User.user_id == payload.userId,
        User.is_deleted.is_(False),
    ).first()

    if not user or not _check_password(
        payload.password,
        user.hashed_password,
    ):

        raise HTTPException(
            400,
            detail="Invalid credentials",
        )

    if not user.email_verified or not user.is_active:

        _send_verification_email(user)

        raise HTTPException(
            400,
            detail=(
                "Email not verified. A verification link has been "
                "sent to your email. Please verify your email before logging in."
            ),
        )

    device_name = request.headers.get(
        "user-agent",
        "Unknown",
    )[:255]

    ip_address = _client_ip(request)

    device = db.query(Device).filter(
        Device.user_id == user.id,
        Device.device_name == device_name,
        Device.is_deleted.is_(False),
    ).first()

    if not device:

        device = Device(
            user_id=user.id,
            device_name=device_name,
            user_agent=request.headers.get("user-agent"),
            ip_address=ip_address,
            is_active=True,
        )

        db.add(device)

    else:

        device.ip_address = ip_address
        device.user_agent = request.headers.get("user-agent")
        device.is_active = True
        device.last_login = datetime.now(timezone.utc)

    user.last_login = datetime.now(timezone.utc)

    db.commit()
    db.refresh(device)

    device_id = str(device.device_id)

    # Get current Redis token version.
    token_version = get_token_version(user.id)

    # Create access and refresh tokens.
    access_token = create_access_token(
        user,
        device_id=device_id,
        platform=payload.platform,
        token_version=token_version,
    )

    refresh_token = create_refresh_token(
        user,
        device_id=device_id,
        platform=payload.platform,
        token_version=token_version,
    )

    # Store refresh token in Redis.
    if not store_refresh_token(
        refresh_token,
        user,
        device_id=device_id,
        platform=payload.platform,
        device_name=device_name,
        ip_address=ip_address or "",
    ):

        raise HTTPException(
            503,
            detail="Could not create session. Please try again.",
        )

    # New login security alert.
    secure_token = secure_generate_password_reset_token(user.id)

    try:

        send_new_login_alert_task.delay(
            user_email=user.email,
            user_id=str(user.id),
            userId=user.user_id,
            device_name=device_name,
            ip_address=ip_address or "Unknown",
            platform=payload.platform,
            reset_token=secure_token,
        )

    except Exception:
        pass

    user_data = LoginUserData(
        id=user.id,
        userId=user.user_id,
        email=user.email,
    )

    if payload.platform == "web":

        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            secure=not settings.DEBUG,
            samesite="lax",
            # max_age=60,
            max_age=settings.REFRESH_TOKEN_LIFETIME * 86400,
            path="/api/users/",
        )

        return LoginResponse(
            access=access_token,
            user=user_data,
            refresh="Token sent via HttpOnly Cookie",
        )

    return LoginResponse(
        access=access_token,
        user=user_data,
        refresh=refresh_token,
    )


# --------------------------------------------------
# REFRESH TOKEN
# --------------------------------------------------

@router.post("/token/refresh/", response_model=RefreshResponse)
def refresh_token(
    payload: RefreshRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):

    token_value = (
        request.cookies.get("refresh_token")
        if payload.platform == "web"
        else payload.refresh
    )

    if not token_value:

        raise HTTPException(
            401,
            detail="Refresh token missing",
        )

    token_payload = decode_token(
        token_value,
        "refresh",
    )

    if not token_payload:

        raise HTTPException(
            401,
            detail="Invalid or expired refresh token",
        )

    if token_payload.get("platform") != payload.platform:

        raise HTTPException(
            401,
            detail="Refresh token platform mismatch",
        )

    user_id = token_payload["user_id"]
    old_jti = token_payload["jti"]

    # Check current token version.
    current_version = get_token_version(user_id)

    if token_payload.get("ver", 0) != current_version:

        raise HTTPException(
            401,
            detail="Session revoked. Please login again.",
        )

    key = f"hash-rt-for-user-{user_id}"

    old_data = redis_client.hget(
        key,
        old_jti,
    )

    if not old_data:

        raise HTTPException(
            401,
            detail="Session expired. Please login again.",
        )

    try:

        token_info = json.loads(old_data)

    except (TypeError, json.JSONDecodeError):

        redis_client.hdel(key, old_jti)

        raise HTTPException(
            401,
            detail="Invalid session data. Please login again.",
        )

    user = db.query(User).filter(
        User.id == user_id,
        User.is_deleted.is_(False),
    ).first()

    if not user or not user.is_active:

        redis_client.hdel(key, old_jti)

        raise HTTPException(
            401,
            detail="User account is unavailable",
        )

    device_id = token_payload.get("device_id")

    new_access = create_access_token(
        user,
        device_id=device_id,
        platform=payload.platform,
        token_version=current_version,
    )

    new_refresh = create_refresh_token(
        user,
        device_id=device_id,
        platform=payload.platform,
        token_version=current_version,
    )

    # Store replacement refresh token first.
    if not store_refresh_token(
        new_refresh,
        user,
        device_id=device_id,
        platform=payload.platform,
        device_name=token_info.get("device_name", ""),
        ip_address=token_info.get("ip_address", ""),
    ):

        raise HTTPException(
            503,
            detail="Could not rotate session. Please try again.",
        )

    # Remove old refresh token.
    redis_client.hdel(key, old_jti)

    if payload.platform == "web":

        response.set_cookie(
            key="refresh_token",
            value=new_refresh,
            httponly=True,
            secure=not settings.DEBUG,
            samesite="lax",
            max_age=settings.REFRESH_TOKEN_LIFETIME * 86400,
            path="/api/users/",
        )

        return RefreshResponse(
            access=new_access,
            refresh="Token sent via HttpOnly Cookie",
        )

    return RefreshResponse(
        access=new_access,
        refresh=new_refresh,
    )


# --------------------------------------------------
# LOGOUT
# --------------------------------------------------

@router.post("/logout/", response_model=LogoutResponse)
def logout(
    payload: LogoutRequest,
    request: Request,
    response: Response,
):

    token_value = (
        request.cookies.get("refresh_token")
        if payload.platform == "web"
        else payload.refresh
    )

    if token_value:

        token_payload = decode_token(
            token_value,
            "refresh",
        )

        if (
            token_payload
            and token_payload.get("platform") == payload.platform
        ):

            redis_client.hdel(
                f"hash-rt-for-user-{token_payload['user_id']}",
                token_payload["jti"],
            )

    if payload.platform == "web":

        response.delete_cookie(
            key="refresh_token",
            path="/api/users/",
        )

    return LogoutResponse(
        message="Logout successful",
    )


# --------------------------------------------------
# AUTHENTICATED USER
# --------------------------------------------------

@router.get(
    "/authenticated/",
    response_model=AuthenticatedResponse,
)
def get_authenticated_user(
    auth: AuthContext = Depends(get_current_auth),
):

    return AuthenticatedResponse(
        msg="Welcome to authenticated view",
        user=AuthenticatedUser(
            id=auth.user.id,
            userId=auth.user.user_id,
            email=auth.user.email,
        ),
        device_id=auth.device_id,
        platform=auth.platform,
    )


# --------------------------------------------------
# FORGOT PASSWORD
# --------------------------------------------------

@router.post(
    "/forgot-password/",
    response_model=ForgotPasswordResponse,
)
def forgot_password(
    payload: ForgotPasswordRequest,
    db: Session = Depends(get_db),
):

    user = db.query(User).filter(
        User.user_id == payload.userId,
        User.is_deleted.is_(False),
    ).first()

    if user:

        token = generate_password_reset_token(user.id)

        link = (
            f"{settings.DOMAIN_URL}/api/users/"
            f"password-change-template/{user.id}/{token}/"
        )

        message = (
            f"Hello {user.user_id},\n\n"
            "We received a password reset request.\n"
            "Use this link within 5 minutes:\n"
            f"{link}\n\n"
            "If you did not request this, ignore this email."
        )

        send_forgot_password_email_task.delay(
            "Reset Your Password",
            message,
            [user.email],
        )

    return ForgotPasswordResponse(
        success=True,
        message=(
            "If the account exists, a password reset link has been sent."
        ),
    )


# --------------------------------------------------
# NORMAL PASSWORD CHANGE
# --------------------------------------------------

@router.post(
    "/password-change/",
    response_model=PasswordChangeResponse,
)
def password_change(
    payload: PasswordChangeRequest,
    db: Session = Depends(get_db),
):

    if payload.new_password != payload.confirm_password:

        raise HTTPException(
            400,
            detail={
                "confirm_password": "Passwords do not match."
            },
        )

    try:

        user_uuid = uuid.UUID(payload.user_id)

    except ValueError:

        raise HTTPException(
            400,
            detail="Invalid user ID",
        )

    user = db.query(User).filter(
        User.id == user_uuid,
        User.is_deleted.is_(False),
    ).first()

    if not user or not verify_password_reset_token(
        user.id,
        payload.token,
    ):

        raise HTTPException(
            400,
            detail="Invalid or expired link.",
        )

    user.hashed_password = _hash_password(
        payload.new_password,
    )

    db.commit()

    # Immediately invalidate all old JWT tokens.
    increment_token_version(user.id)

    delete_password_reset_token(
        user.id,
        payload.token,
    )

    # Remove refresh sessions and notify connected devices.
    logout_all_devices_task.delay(
        str(user.id),
    )

    return PasswordChangeResponse(
        success=True,
        message=(
            "Password changed successfully. "
            "Please login again."
        ),
    )


# --------------------------------------------------
# SECURE PASSWORD CHANGE
# --------------------------------------------------

@router.post(
    "/secure-password-change/",
    response_model=PasswordChangeResponse,
)
def secure_password_change(
    payload: SecurePasswordChangeRequest,
    db: Session = Depends(get_db),
):

    if payload.new_password != payload.confirm_password:

        raise HTTPException(
            400,
            detail={
                "confirm_password": "New passwords do not match"
            },
        )

    try:

        user_uuid = uuid.UUID(payload.user_id)

    except ValueError:

        raise HTTPException(
            400,
            detail="Invalid user ID",
        )

    user = db.query(User).filter(
        User.id == user_uuid,
        User.is_deleted.is_(False),
    ).first()

    if not user or not _check_password(
        payload.current_password,
        user.hashed_password,
    ):

        raise HTTPException(
            400,
            detail="Current password is incorrect",
        )

    if not secure_verify_password_reset_token(
        user.id,
        payload.token,
    ):

        raise HTTPException(
            400,
            detail="Invalid or expired secure token",
        )

    user.hashed_password = _hash_password(
        payload.new_password,
    )

    db.commit()

    # Revoke all previously issued JWT tokens.
    increment_token_version(user.id)

    delete_secure_password_reset_token(
        user.id,
        payload.token,
    )

    send_password_changed_email_task.delay(
        user.email,
        user.user_id,
    )

    logout_all_devices_task.delay(
        str(user.id),
    )

    return PasswordChangeResponse(
        success=True,
        message=(
            "Password changed successfully! "
            "You have been logged out from all devices."
        ),
        redirect="/login/",
    )


# --------------------------------------------------
# EMAIL VERIFICATION HTML PAGE
# --------------------------------------------------

@pages_router.get(
    "/verify-email/",
    response_class=HTMLResponse,
)
def verify_email_page(
    request: Request,
    user_id: str | None = None,
    token: str | None = None,
    db: Session = Depends(get_db),
):

    return verify_email(
        request,
        user_id,
        token,
        db,
    )


# --------------------------------------------------
# PASSWORD RESET HTML PAGE
# --------------------------------------------------

@pages_router.get(
    "/password-change-template/{user_id}/{token}/",
    response_class=HTMLResponse,
)
def password_change_template(
    request: Request,
    user_id: str,
    token: str,
):

    if not verify_password_reset_token(
        user_id,
        token,
    ):

        return _render_error(
            request,
            "users/password_change_error.html",
            "Invalid or expired link.",
        )

    return templates.TemplateResponse(
        "users/password_change_template.html",
        {
            "request": request,
            "user_id": user_id,
            "token": token,
        },
    )


# --------------------------------------------------
# SECURE PASSWORD RESET HTML PAGE
# --------------------------------------------------

@pages_router.get(
    "/secure-password-change-template/{user_id}/{token}/",
    response_class=HTMLResponse,
)
def secure_password_change_template(
    request: Request,
    user_id: str,
    token: str,
    db: Session = Depends(get_db),
):

    try:

        user_uuid = uuid.UUID(user_id)

    except ValueError:

        return _render_error(
            request,
            "users/error.html",
            "Invalid or expired link. Please request a new one.",
        )

    user = db.query(User).filter(
        User.id == user_uuid,
        User.is_deleted.is_(False),
    ).first()

    if not user or not secure_verify_password_reset_token(
        user.id,
        token,
    ):

        return _render_error(
            request,
            "users/error.html",
            "Invalid or expired link. Please request a new one.",
        )

    return templates.TemplateResponse(
        "users/secure_password_change_template.html",
        {
            "request": request,
            "user_id": user_id,
            "token": token,
        },
    )
