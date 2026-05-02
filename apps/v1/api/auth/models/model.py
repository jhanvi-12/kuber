"""
This module defines the SQLAlchemy models for the authentication system, including
the User table and its attributes.

Classes:
    User: A model representing a user in the system.
"""

from datetime import datetime, timedelta
from sqlalchemy.sql import text
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    Double,
    func
)

from apps.v1.api.auth.models.attribute import UserTypeEnum
from config.db_session import Base
from core.db.mixins.timestamp_mixin import TimestampMixin
from core.utils import constant_variable as constant


class User(TimestampMixin, Base):
    """
    Table is responsible for creating User model and attributes.
    """

    __tablename__ = "users"
    id = Column(
        Integer,
        primary_key=constant.STATUS_TRUE,
        nullable=constant.STATUS_FALSE,
        autoincrement=constant.STATUS_TRUE,
    )
    full_name = Column(String(100), nullable=constant.STATUS_FALSE)
    email = Column(String(150), nullable=constant.STATUS_FALSE)
    password = Column(String(200), doc="Password of the user")
    mobile = Column(
        String(12), nullable=constant.STATUS_TRUE, doc="Contact number of the user"
    )
    user_type = Column(
        Enum(UserTypeEnum),
        default=UserTypeEnum.CUSTOMER,
        doc="User type for the users.",
    )
    profile_image = Column(
        Text, nullable=constant.STATUS_TRUE, doc="Image URL of user."
    )
    latitude = Column(
        Double, nullable=constant.STATUS_TRUE, doc="Current latitude of the driver"
    )
    longitude = Column(
        Double, nullable=constant.STATUS_TRUE, doc="Current longitude of the driver"
    )
    address = Column(
        String(255), nullable=constant.STATUS_TRUE, doc="Address of the user."
    )
    notification_flag = Column(
        Boolean,
        default=constant.STATUS_TRUE,
        doc="Whether user wants to receive notifications.",
    )
    # Device-related fields (NEW)
    device_token = Column(
        String(255),
        nullable=constant.STATUS_TRUE,
        doc="FCM / push notification device token",
    )
    platform = Column(
        String(20),
        nullable=constant.STATUS_TRUE,
        doc="Device platform (android / ios / web)",
    )
    device_id = Column(
        String(20),
        nullable=constant.STATUS_TRUE,
        doc="Unique device identifier",
    )
    #  Generate this code when user login and when logged out and re login generate again
    code = Column(
        Integer, nullable=constant.STATUS_TRUE, doc="4-digit OTP for ride verification"
    )


class OtpVerification(Base):
    """
    Table is responsible for creating OtpVerification model and attributes.
    """

    __tablename__ = "otp_verification"
    id = Column(
        Integer,
        primary_key=constant.STATUS_TRUE,
        nullable=constant.STATUS_FALSE,
        autoincrement=constant.STATUS_TRUE,
    )
    email = Column(String(150), nullable=constant.STATUS_FALSE)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=constant.STATUS_TRUE,
        doc="User id associated with the OtpVerification.",
    )
    driver_id = Column(
        Integer,
        ForeignKey("drivers.id", ondelete="CASCADE"),
        nullable=constant.STATUS_TRUE,
        doc="Driver id associated with the OtpVerification.",
    )
    otp_code = Column(Integer, nullable=constant.STATUS_FALSE, doc="Otp code.")
    created_at = Column(
        DateTime,
        default=datetime.now,
        nullable=False,
    )
    updated_at = Column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
    )
    expires_at = Column(
        DateTime,
        default=lambda: datetime.now() + timedelta(minutes=constant.STATUS_FIVE),
        nullable=False,
    )
    deleted_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

class Admin(TimestampMixin, Base):
    """Admin table"""
    __tablename__ = "admin"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(150), unique=True, nullable=False, index=True)
    password = Column(String(255), nullable=False)
    mobile = Column(String(15), unique=True, nullable=True)

class Session(TimestampMixin, Base):
    """Table to manage user sessions for JWT token tracking and invalidation."""
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    driver_id = Column(Integer, ForeignKey("drivers.id"), nullable=True, index=True)

    # store jti or session_id from JWT
    session_id = Column(String(255), unique=True, index=True, nullable=False)

