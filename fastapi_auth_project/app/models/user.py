import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base

def _uuid() -> uuid.UUID:
    return uuid.uuid4()

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=_uuid, index=True)
    user_id = Column(String(150), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    first_name = Column(String(150), default="", nullable=False)
    last_name = Column(String(150), default="", nullable=False)

    email_verified = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_staff = Column(Boolean, default=False, nullable=False)

    phone_number = Column(String(20), nullable=True)
    profile_picture = Column(Text, nullable=True)
    date_joined = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    last_login = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False)
    is_deleted = Column(Boolean, default=False, nullable=False)

    devices = relationship("Device", back_populates="user", cascade="all, delete-orphan")

class Device(Base):
    __tablename__ = "devices"
    __table_args__ = (UniqueConstraint("user_id", "device_name", name="uq_user_device"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=_uuid, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    device_name = Column(String(255), nullable=False)
    device_id = Column(UUID(as_uuid=True), default=_uuid, unique=True, nullable=False)
    ip_address = Column(String(64), nullable=True)
    user_agent = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False)
    is_deleted = Column(Boolean, default=False, nullable=False)

    user = relationship("User", back_populates="devices")