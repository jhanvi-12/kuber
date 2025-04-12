"""This module is used to define helper functions."""
from datetime import datetime

import pytz
from passlib.context import CryptContext


class PasswordUtils:
    """This class is used to manage password management"""

    def __init__(self):
        self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class DateTimeUtils:

    @staticmethod
    def get_time():
        """Returns current datetime in default timezone India Standard Time"""
        timezone = "Asia/Kolkata"
        return datetime.now(pytz.timezone(timezone))
