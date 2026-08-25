"""This module is used to implement vehicle specific table functionality."""

from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime

from config.db_session import Base
from core.db.mixins.timestamp_mixin import TimestampMixin
from core.utils import constant_variable as constant


class Vehicle(Base, TimestampMixin):
    """
    Vehicle table with below fields.
    """

    __tablename__ = "vehicles"
    id = Column(
        Integer,
        primary_key=constant.STATUS_TRUE,
        nullable=constant.STATUS_FALSE,
        autoincrement=constant.STATUS_TRUE,
    )
    driver_id = Column(
        Integer,
        ForeignKey("drivers.id", ondelete="CASCADE"),
        nullable=constant.STATUS_TRUE,
        doc="Driver ID of the driver.",
    )
    plate_number = Column(
        String(100), nullable=constant.STATUS_FALSE, doc="Vehicle plate number"
    )
    ride_type = Column(
        String(100), nullable=constant.STATUS_TRUE, doc="Vehicle ride type"
    )
    vehicle_type = Column(
        String(150), nullable=constant.STATUS_TRUE, doc="Vehicle type"
    )
    vehicle_model = Column(
        Integer, nullable=constant.STATUS_FALSE, doc="Vehicle model"
    )
    make = Column(String(50), nullable=constant.STATUS_TRUE, doc="Vehicle make year")
    vehicle_image = Column(Text, nullable=constant.STATUS_TRUE, doc="Vehicle image URL")
    vehicle_insurance_expiration_date = Column(
        DateTime, nullable=constant.STATUS_TRUE, doc="Vehicle insurance expiration date"
    )
    vehicle_insurance_image = Column(
        Text, nullable=constant.STATUS_TRUE, doc="Vehicle issurance image URL"
    )
