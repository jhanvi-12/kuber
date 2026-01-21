"""This module is responsible to contain ride attribute definitions."""

from enum import Enum

class RideStatusEnum(str, Enum):
    """
    Enum for ride status.
    """
    SEARCHING = "Searching"
    FINDING_DRIVERS = "Finding_drivers"
    BOOKED = "Booked"
    ACCEPTED = "Accepted"
    REACHED = "Reached"
    STARTED = "Started"
    COMPLETED = "Completed"
    CANCELLED = "Cancelled"
