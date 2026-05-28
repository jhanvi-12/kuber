"""This module is responsible to contain ride attribute definitions."""

from enum import Enum

class RideStatusEnum(int, Enum):
    """
    Enum for ride status.
    """
    INITIAL = -1
    FAILED = 0
    ACCEPTED = 1
    REACHED = 2
    STARTED = 3
    COMPLETED = 4
    CANCELLED = 5

