"""This module defines the Ride model for the ride-hailing application."""

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text

from config.db_session import Base
from core.db.mixins.timestamp_mixin import TimestampMixin
from core.utils import constant_variable as constant


class Ride(Base, TimestampMixin):
    """
    Represents a ride taken by a user, including vehicle and driver details, fare,
    geolocation, and a security OTP.
    """

    __tablename__ = "rides"

    id = Column(
        Integer,
        primary_key=constant.STATUS_TRUE,
        index=constant.STATUS_TRUE,
        autoincrement=constant.STATUS_TRUE,
        doc="Primary key",
    )
    ride_uuid = Column(
        String(36),
        nullable=constant.STATUS_FALSE,
        doc="Universally unique identifier for the ride"
    )
    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=constant.STATUS_FALSE,
        index=constant.STATUS_TRUE,
        doc="ID of the user who booked the ride",
    )
    vehicle_id = Column(
        Integer,
        ForeignKey("vehicles.id"),
        nullable=constant.STATUS_TRUE,
        index=constant.STATUS_TRUE,
        doc="ID of the vehicle used",
    )
    driver_id = Column(
        Integer,
        ForeignKey("drivers.id"),
        nullable=constant.STATUS_TRUE,
        index=constant.STATUS_TRUE,
        doc="ID of the assigned driver",
    )

    ride_date = Column(DateTime, nullable=constant.STATUS_FALSE, doc="Date of the ride")
    ride_type = Column(String(50), nullable=constant.STATUS_FALSE, doc="Type of ride")
    # ride_time = Column(DateTime, nullable=False, doc="Time of the ride")
    status = Column(
        Integer,
        nullable=constant.STATUS_FALSE,
        doc="Status of the ride (0 failed, accepted 1, completed 4)",
    )
    ride_fare = Column(
        Float, nullable=constant.STATUS_FALSE, doc="Fare amount for the ride"
    )
    discount_fare = Column(
        Float,
        nullable=constant.STATUS_TRUE,
        default=0.0,
        server_default="0.0",
        doc="Discount amount applied to the ride",
    )
    total_fare = Column(
        Float,
        nullable=constant.STATUS_TRUE,
        default=0.0,
        server_default="0.0",
        doc="Total fare after discount",
    )
    distance = Column(
        Float,
        nullable=constant.STATUS_TRUE,
        default=0.0,
        server_default="0.0",
        doc="Distance between pickup and destination in km",
    )
    duration = Column(
        Float,
        nullable=constant.STATUS_TRUE,
        default=0.0,
        server_default="0.0",
        doc="Estimated duration of the ride in minutes",
    )
    coupon_code = Column(
        String(50),
        nullable=constant.STATUS_TRUE,
        default=constant.STATUS_NULL,
        doc="Coupon code applied to the ride (e.g. WELCOME50, COMMUTE25)",
    )
    is_welcome = Column(
        Integer,
        nullable=constant.STATUS_TRUE,
        default=constant.STATUS_FALSE,
        doc="Whether the ride is a welcome ride (1 for yes, 0 for no)",
    )
    is_commuter = Column(
        Integer,
        nullable=constant.STATUS_TRUE,
        default=constant.STATUS_FALSE,
        doc="Whether the ride is a commuter ride (1 for yes, 0 for no)",
    )
    pickup_latitude = Column(
        Float, nullable=constant.STATUS_FALSE, doc="Latitude of ride location"
    )
    pickup_longitude = Column(
        Float, nullable=constant.STATUS_FALSE, doc="Longitude of ride location"
    )

    pickup_address = Column(
        String(255), nullable=constant.STATUS_FALSE, doc="Address of the ride location"
    )
    destination_latitude = Column(
        Float, nullable=constant.STATUS_FALSE, doc="Latitude of destination"
    )
    destination_longitude = Column(
        Float, nullable=constant.STATUS_FALSE, doc="Longitude of destination"
    )

    destination_address = Column(
        String(255), nullable=constant.STATUS_FALSE, doc="Address of the destination"
    )
    cancellation_reason = Column(
        String(150), nullable=constant.STATUS_TRUE, doc="Reason for cancellation"
    )
    cancellation_description = Column(
        Text,
        nullable=constant.STATUS_TRUE,
        doc="Description of the cancellation reason",
    )
    cancelled_by = Column(
        String(50),
        nullable=constant.STATUS_TRUE,
        doc="Who cancelled the ride (user or driver)",
    )
