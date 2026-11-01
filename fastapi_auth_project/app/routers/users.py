from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import bcrypt  # <-- passlib ki jagah bcrypt import kiya
from sqlalchemy.orm import Session

from app.auth.jwt_auth import AuthContext, get_current_auth
from app.config import settings
from app.database import get_db
from app.models.user import User, Device
from app.redis_client import redis_client
from app.schemas.user import (
    RegisterRequest, RegisterResponse, RegisterResponseData,
    LoginRequest, LoginResponse, LoginUserData,
    RefreshRequest, RefreshResponse,
    LogoutRequest, LogoutResponse,
    ForgotPasswordRequest, ForgotPasswordResponse,
    PasswordChangeRequest, PasswordChangeResponse,
    SecurePasswordChangeRequest,
    AuthenticatedResponse, AuthenticatedUser,
)
from app.tasks.email_tasks import send_email_task, logout_all_devices_task
from app.utils.jwt_utils import create_access_token, create_refresh_token, decode_token
from app.utils.tokens import (
    store_refresh_token, generate_verification_token, verify_email_token, delete_verify_email_token,
    generate_password_reset_token, verify_password_reset_token, delete_password_reset_token,
    secure_verify_password_reset_token, delete_secure_password_reset_token
)
import asyncio
from fastapi import Response 

router = APIRouter()
templates = Jinja2Templates(directory="templates")

def _send_verification_email(user: User) -> bool:
    try:
        token = generate_verification_token(user.id)

        link = f"{settings.DOMAIN_URL}/api/users/verify-email/?user_id={user.user_id}&token={token}"

        message = f"Hello {user.user_id},\n\nPlease verify your email: {link}"

        result = send_email_task.delay(
            "Verify Your Email",
            message,
            [user.email]
        )

        print("Celery task ID:", result.id)

        return True

    except Exception as e:
        print(f"Celery submission error: {e}")
        return False

@router.post("/register/", response_model=RegisterResponse, status_code=201)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    if db.query(User).filter(User.user_id.ilike(payload.user_id)).first():
        raise HTTPException(400, detail={"user_id": "userId already exists"})
    if db.query(User).filter(User.email.ilike(payload.email)).first():
        raise HTTPException(400, detail={"email": "Email already exists"})

    # Password ko bytes mein convert karke hash karo
    password_bytes = payload.password.encode('utf-8')
    hashed_password_bytes = bcrypt.hashpw(password_bytes, bcrypt.gensalt())
    hashed_password = hashed_password_bytes.decode('utf-8') # DB mein save karne ke liye string mein decode kiya

    user = User(
        user_id=payload.user_id,
        email=payload.email,
        hashed_password=hashed_password,
        is_active=False,
        email_verified=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    print( _send_verification_email(user), "error")
    _send_verification_email(user)

    print("success api")

    return RegisterResponse(
        success=True,
        message="Registration successful. Check your email.",
        data=RegisterResponseData(user_id=user.user_id, email=user.email),
    )

@router.get("/verify-email/", response_class=HTMLResponse)
def verify_email(request: Request, user_id: str | None = None, token: str | None = None, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user or not verify_email_token(user.id, token):
        return templates.TemplateResponse("users/email_verification_error.html", {"request": request, "message": "Invalid token"}, status_code=400)

    user.email_verified = True
    user.is_active = True
    db.commit()
    delete_verify_email_token(user.id, token)
    return templates.TemplateResponse("users/email_verification_success.html", {"request": request, "user_id": user.user_id, "email": user.email})

@router.post("/login/", response_model=LoginResponse)
def login(payload: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.user_id == payload.userId).first()
    
    is_password_valid = False
    if user:
        try:
            stored_hash = user.hashed_password.encode('utf-8')
            input_password = payload.password.encode('utf-8')
            is_password_valid = bcrypt.checkpw(input_password, stored_hash)
        except Exception as e:
            print(f"Bcrypt verify error: {e}")
            is_password_valid = False

    if not user or not is_password_valid:
        raise HTTPException(400, detail="Invalid credentials")

    if not user.email_verified:
        raise HTTPException(400, detail="Email not verified.")

    device_name = request.headers.get("user-agent", "Unknown")
    device = db.query(Device).filter(Device.user_id == user.id, Device.device_name == device_name).first()
    if not device:
        device = Device(user_id=user.id, device_name=device_name)
        db.add(device)
        db.commit()
        db.refresh(device)

    access_token = create_access_token(user, device_id=str(device.device_id), platform=payload.platform)
    refresh_token = create_refresh_token(user, device_id=str(device.device_id), platform=payload.platform)
    store_refresh_token(refresh_token, user, device_id=str(device.device_id), platform=payload.platform)

    user_data = LoginUserData(id=user.id, userId=user.user_id, email=user.email)

    if payload.platform == "web":
        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            secure=False,       # Production mein True karna
            samesite="lax",
            max_age=settings.REFRESH_TOKEN_LIFETIME * 24 * 60 * 60, # 15 days
            path="/api/users/"
        )
        return LoginResponse(
            access=access_token,
            user=user_data,
            refresh="Token sent via HttpOnly Cookie"
        )
    else:
        return LoginResponse(
            access=access_token,
            user=user_data,
            refresh=refresh_token
        )

@router.post("/token/refresh/", response_model=RefreshResponse)
def refresh_token(payload: RefreshRequest, request: Request, response: Response):
    if payload.platform == "web":
        refresh_token_val = request.cookies.get("refresh_token")
    else:
        refresh_token_val = payload.refresh

    if not refresh_token_val:
        raise HTTPException(401, detail="Refresh token missing")

    token_payload = decode_token(refresh_token_val, "refresh")
    if not token_payload:
        raise HTTPException(401, detail="Invalid or expired refresh token")
    
    user_id = token_payload["user_id"]
    jti = token_payload["jti"]
    user_tokens_key = f"hash-rt-for-user-{user_id}"
    stored_data = redis_client.hget(user_tokens_key, jti)
    if not stored_data:
        raise HTTPException(401, detail="Refresh token revoked or not found")

    class DummyUser:
        def __init__(self, uid):
            self.id = uid

    dummy_user = DummyUser(user_id)
    new_access = create_access_token(dummy_user, device_id=token_payload.get("device_id"), platform=payload.platform)

    if payload.platform == "web":
        response.set_cookie(
            key="refresh_token",
            value=refresh_token_val,
            httponly=True,
            secure=False,
            samesite="lax",
            max_age=settings.REFRESH_TOKEN_LIFETIME * 24 * 60 * 60,
            path="/api/users/"
        )
        return RefreshResponse(
            access=new_access, 
            refresh="Token sent via HttpOnly Cookie"
        )
    else:
        return RefreshResponse(
            access=new_access, 
            refresh=refresh_token_val
        )

@router.post("/logout/", response_model=LogoutResponse)
def logout(payload: LogoutRequest, request: Request, response: Response):
    if payload.platform == "web":
        refresh_token_val = request.cookies.get("refresh_token")
    else:
        refresh_token_val = payload.refresh

    if refresh_token_val:
        token_payload = decode_token(refresh_token_val, "refresh")
        if token_payload:
            user_id = token_payload["user_id"]
            jti = token_payload["jti"]
            redis_client.hdel(f"hash-rt-for-user-{user_id}", jti)
    
    if payload.platform == "web":
        response.delete_cookie(key="refresh_token", path="/api/users/")
    
    return LogoutResponse(message="Successfully logged out")

@router.get("/authenticated/", response_model=AuthenticatedResponse)
def get_authenticated_user(auth: AuthContext = Depends(get_current_auth)):
    return AuthenticatedResponse(
        msg="Authenticated successfully",
        user=AuthenticatedUser(id=auth.user.id, userId=auth.user.user_id, email=auth.user.email),
        device_id=auth.device_id,
        platform=auth.platform,
    )

@router.post("/forgot-password/", response_model=ForgotPasswordResponse)
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.user_id == payload.userId).first()
    if user:
        token = generate_password_reset_token(user.id)
        link = f"{settings.DOMAIN_URL}/api/users/password-change/?user_id={user.user_id}&token={token}"
        message = f"Password reset link: {link}"
        send_email_task.delay("Password Reset", message, [user.email])
    return ForgotPasswordResponse(success=True, message="If user exists, password reset link sent.")

@router.post("/password-change/", response_model=PasswordChangeResponse)
def password_change(payload: PasswordChangeRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.user_id == payload.user_id).first()
    if not user or not verify_password_reset_token(user.id, payload.token):
        raise HTTPException(400, detail="Invalid or expired token")

    # bcrypt se naya password hash karo
    new_password_bytes = payload.new_password.encode('utf-8')
    hashed_password_bytes = bcrypt.hashpw(new_password_bytes, bcrypt.gensalt())
    user.hashed_password = hashed_password_bytes.decode('utf-8') # String mein decode karke save karo

    db.commit()
    delete_password_reset_token(user.id, payload.token)
    
    # Celery task to logout devices (agar Celery use kar rahe ho toh)
    logout_all_devices_task.delay(str(user.id))

    return PasswordChangeResponse(success=True, message="Password changed successfully")

@router.post("/secure-password-change/", response_model=PasswordChangeResponse)
def secure_password_change(payload: SecurePasswordChangeRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.user_id == payload.user_id).first()
    
    # 1. Current password verify karo (bcrypt se)
    is_password_valid = False
    if user:
        try:
            stored_hash = user.hashed_password.encode('utf-8')
            input_password = payload.current_password.encode('utf-8')
            is_password_valid = bcrypt.checkpw(input_password, stored_hash)
        except Exception as e:
            print(f"Bcrypt verify error: {e}")
            is_password_valid = False

    if not user or not is_password_valid:
        raise HTTPException(400, detail="Invalid current password")

    if not secure_verify_password_reset_token(user.id, payload.token):
        raise HTTPException(400, detail="Invalid or expired secure token")

    # 2. Naya password hash karo (bcrypt se)
    new_password_bytes = payload.new_password.encode('utf-8')
    hashed_password_bytes = bcrypt.hashpw(new_password_bytes, bcrypt.gensalt())
    user.hashed_password = hashed_password_bytes.decode('utf-8') # String mein decode karke DB mein save karo

    db.commit()
    delete_secure_password_reset_token(user.id, payload.token)
    
    # Celery task to logout devices
    logout_all_devices_task.delay(str(user.id))

    return PasswordChangeResponse(success=True, message="Secure password changed successfully")