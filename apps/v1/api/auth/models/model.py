"""
This module defines the SQLAlchemy models for the authentication system, including
the User table and its attributes.

Classes:
    User: A model representing a user in the system.
"""

from datetime import datetime, timedelta

import pytz
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
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
    is_verified = Column(
        Boolean, default=constant.STATUS_FALSE, doc="Whether user is verified or not."
    )
    notification_flag = Column(
        Boolean,
        default=constant.STATUS_TRUE,
        doc="Whether user wants to receive notifications.",
    )


class OtpVerification(Base, TimestampMixin):
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
    expires_at = Column(
        DateTime,
        default=datetime.now(pytz.timezone("Asia/Kolkata"))
        + timedelta(minutes=constant.STATUS_FIVE),
    )
