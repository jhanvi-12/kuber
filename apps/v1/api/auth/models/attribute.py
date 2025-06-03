"""This module is responsible for the creation of the type definition."""
from enum import Enum


class UserTypeEnum(str, Enum):
    """This enum represents the user type."""
    CUSTOMER = "customer"
    DRIVER = "driver"

class PlanNameEnum(str, Enum):
    """This enum represents the plan name."""
    BASIC = "Basic"
    PREMIUM = "Premium"
    DOMESTIC = "Domestic"
    INTERNATIONAL = "International"
