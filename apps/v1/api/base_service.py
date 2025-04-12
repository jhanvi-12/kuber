"""
This module defines the base service class providing common functionality for all services.

Classes:
- BaseResponseService: Provides common methods 
for creating standard responses and sending API requests.

Usage:
This module is intended to be inherited by other service classes to reuse common functionality.
"""

import base64
import io
import random

import magic
from dateutil import parser
from fastapi import status

from apps.v1.api.auth.models.attribute import UserTypeEnum
from apps.v1.api.auth.models.method import UserAuthMethod
from apps.v1.api.auth.models.model import User
from apps.v1.api.driver.models.model import Driver
from config import aws_config
from core.s3.aws_s3 import S3Manager
from core.utils import constant_variable as constant
from core.utils.message_variable import ErrorMessage
from core.utils.standard_response import StandardResponse


class BaseResponseService:
    """
    Base service class providing common functionality for all services.
    """

    def response(self, status_code, message, data=None, cookies=None):
        """
        Create a standard response.

        Args:
            status_code (int): The HTTP status code.
            message (str): The response message.
            data (dict, optional): The response data. Defaults to None.

        Returns:
            StandardResponse: The standard response object.
        """
        return StandardResponse(
            status_code, data or constant.EMPTY_LIST, message, cookies
        ).make

    def convert_datetime_format(self, data):
        """
        Converts the datetime format of the given data.

        Arguments:
            data (dict): The data containing datetime fields to be converted.

        Returns:
            dict: The data with converted datetime fields.
        """
        try:
            data["created_at"] = parser.parse(data["created_at"])
            data["updated_at"] = parser.parse(data["updated_at"])
            return data
        except Exception:
            return None

    def generate_otp_code(self):
        """
        Generates a random 6-digit OTP code.

        Returns:
            str: The 6-digit OTP code.
        """
        return random.randint(1000, 9999)

    async def get_current_user_details(self, db, current_user):
        """
        Fetches the current user details from the database.

        Args:
            db (AsyncSession): The database session.
            current_user (dict): The current user data.

        Returns:
            dict: The user object.
        """
        if current_user["user_type"] == UserTypeEnum.CUSTOMER.value:
            user_obj = await UserAuthMethod(User).find_by_id(
                db, current_user["user_id"]
            )
        else:
            user_obj = await UserAuthMethod(Driver).find_by_id(
                db, current_user["user_id"]
            )
        return user_obj

    def get_image_content_type(self, image_data: bytes):
        """
        Detects the content type of the image data.

        Args:
            image_data (bytes): The image data.

        Returns:
            str: The content type of the image.
        """
        try:
            mime = magic.Magic(mime=True)
            return mime.from_buffer(image_data)
        except Exception:
            return constant.STATUS_NULL

    def get_upload_file_to_s3(self, request, file_obj, path):
        """
        Uploads a file to S3.

        Args:
            request: The request object.
            file_obj: The file object to be uploaded.
            path (str): The S3 path where the file will be uploaded.
            content_type (str): The content type of the file.

        Returns:
            str: The URL of the uploaded file.
        """
        try:
            profile_data = base64.b64decode(file_obj)
            profile_image = io.BytesIO(profile_data)

            content_type = self.get_image_content_type(profile_data)
            content_type_data = "." + content_type.split("/")[1]
            path_data = f"{path}{content_type_data}"
            if not content_type:
                return self.response(
                    status.HTTP_400_BAD_REQUEST, ErrorMessage.invalidImageType
                )
            file_obj = S3Manager(request).upload_file(
                profile_image, path_data, content_type
            )
            return file_obj
        except Exception:
            return constant.STATUS_NULL
