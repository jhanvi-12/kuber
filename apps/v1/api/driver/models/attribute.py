"""This module is for the driver status"""

from enum import Enum

class DriverStatusEnum(str, Enum):
    """This class is used to represent the dirver status"""
    PENDING = 0
    APPROVED = 1
    REJECTED = 2
