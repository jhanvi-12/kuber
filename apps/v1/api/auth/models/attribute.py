"""This module is responsible for the creation of the type definition."""
from enum import Enum


class UserTypeEnum(str, Enum):
    """This enum represents the user type."""
    CUSTOMER = "customer"
    DRIVER = "driver"


class OtpTypeEnum(int, Enum):
    """Identifies which flow requested the OTP."""
    REGISTER = 1
    FORGOT_PASSWORD = 2

class PlanNameEnum(str, Enum):
    """This enum represents the plan name."""
    FREE = "Free"
    BASIC = "Basic"
    PREMIUM = "Premium"
    DOMESTIC = "Domestic"
    INTERNATIONAL = "International"
