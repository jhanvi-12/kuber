"""This module is responsible to contain ride attribute definitions."""

from enum import Enum

class RideStatusEnum(str, Enum):
    """
    Enum for ride status.
    """
    BOOKED = "booked"
    ACCEPTED = "accepted"
    REACHED = "reached"
    STARTED = "started"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
