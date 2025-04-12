"""This module is responsible for the creation of the type definition."""
from enum import Enum


class UserTypeEnum(str, Enum):
    """This enum represents the user type."""
    CUSTOMER = "customer"
    DRIVER = "driver"
