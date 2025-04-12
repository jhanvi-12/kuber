"""This module is used to implement driver specific table functionality."""

from sqlalchemy import Boolean, Column, Enum, ForeignKey, Integer, String, Text

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
    #TODO:
    # vehicle_id = Column(
    #     Integer,
    #     ForeignKey("vehicles.id", ondelete="CASCADE"),
    #     nullable=constant.STATUS_TRUE,
    #     doc="Vehicle ID of the driver.",
    # )
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

