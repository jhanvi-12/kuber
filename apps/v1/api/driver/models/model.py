"""This module is used to implement driver specific table functionality."""

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Double,
    Enum,
    Float,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from apps.v1.api.auth.models.attribute import UserTypeEnum
from config.db_session import Base
from core.db.mixins.timestamp_mixin import TimestampMixin
from core.utils import constant_variable as constant


class Driver(Base, TimestampMixin):
    """
    Driver table with fields: id, name, phone_number, email, password, user_type, vehicle_id.
    """

    __tablename__ = "drivers"
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
        default=UserTypeEnum.DRIVER,
        doc="User type for the users.",
    )
    profile_image = Column(
        Text, nullable=constant.STATUS_TRUE, doc="Image URL of user."
    )
    notification_flag = Column(
        Boolean,
        default=constant.STATUS_TRUE,
        doc="Whether user wants to receive notifications.",
    )
    license_number = Column(
        String(100), nullable=constant.STATUS_TRUE, doc="Driver license number"
    )
    license_image = Column(
        Text, nullable=constant.STATUS_TRUE, doc="Driver license image URL"
    )
    license_expiry_date = Column(
        DateTime, nullable=constant.STATUS_TRUE, doc="Driver license expiry date"
    )
    latitude = Column(
        Double, nullable=constant.STATUS_TRUE, doc="Current latitude of the driver"
    )
    longitude = Column(
        Double, nullable=constant.STATUS_TRUE, doc="Current longitude of the driver"
    )
    device_token = Column(
        String(255),
        nullable=constant.STATUS_TRUE,
        doc="Device token for push notifications",
    )
    is_active = Column(
        Boolean, default=constant.STATUS_FALSE, doc="Whether driver is active or not"
    )

    # Relationship with Plans model
    plans = relationship("Plans", back_populates="driver", cascade="all, delete-orphan")
    review = Column(
        Float,
        nullable=constant.STATUS_TRUE,
        default=0.0,
        doc="Average rating of the driver",
    )
    # 🔹 Device-related fields (NEW)
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
