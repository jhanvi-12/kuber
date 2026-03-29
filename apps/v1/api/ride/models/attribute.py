"""This module is responsible to contain ride attribute definitions."""

from enum import Enum

class RideStatusEnum(str, Enum):
    """
    Enum for ride status.
    """
    FAILED = 0
    ACCEPTED = 1
    REACHED = 2
    STARTED = 3
    COMPLETED = 4
    CANCELLED = 5
