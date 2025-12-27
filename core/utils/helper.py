"""This module is used to define helper functions."""
from datetime import datetime

import pytz
import requests
from passlib.context import CryptContext


class PasswordUtils:
    """This class is used to manage password management"""

    def __init__(self):
        self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class DateTimeUtils:

    @staticmethod
    def get_time():
        """Returns current datetime in default timezone India Standard Time"""
        return datetime.now()

def send_request(
    method: str, url: str, headers: dict = None, json_header: bool = False, data: dict = None
) -> requests.Response:
    """This function sends an HTTP request to the specified URL with the given method.
    Args:
        method (str): The HTTP method to use (e.g., GET, POST, PUT, DELETE).
        url (str): The URL to send the request to.
        json_header (bool): Whether to include a JSON content type header.
    Returns:
        requests.Response: The response object from the request.
    """
    try:
        default_headers = {"accept": "application/json"}
        if json_header and method.upper() in ["POST", "PUT", "PATCH"]:
            headers["Content-Type"] = "application/json"

        # Merge with custom headers
        if headers:
            default_headers.update(headers)

        response = requests.request(method, url, headers=default_headers, data=data)
        return response
    except Exception as e:
        print(f"Error sending request to {url}: {e}")
        return None