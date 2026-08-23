"""
This module defines the service for admin user signup, including the creation of new admin users.
"""

import json
import uuid

from fastapi import Response, status
from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession
from werkzeug.security import generate_password_hash

from apps.v1.api.auth.models.attribute import UserTypeEnum
from apps.v1.api.auth.models.method import UserAuthMethod
from apps.v1.api.auth.models.model import User
from apps.v1.api.auth.serializer import RegisterResSchema
from apps.v1.api.base_service import BaseResponseService
from apps.v1.api.driver.models.model import Driver
from config import aws_config
from core.utils import DataBaseMethod, ValidationMethods
from core.utils import constant_variable as constant
from core.utils.message_variable import ErrorMessage, InfoMessage
from apps.v1.api.driver.models.attribute import DriverStatusEnum

class SignUpService(BaseResponseService):
    """
    This class represents the service for creating admin users.

    Methods:
        create_signup_service(db, body): Creates a new admin user.
    """

    async def create_signup_service(
        self, request, db: AsyncSession, user_type, body, profile_image
    ):
        """
        Creates a new admin user.

        Args:
            db (AsyncSession): The database session.
            user_type (UserType): The user type (customer/driver).
            body (dict): The request body containing user details.

        Returns:
            StandardResponse: The response object with status and message.
        """
        try:
            ValidationMethods().validate_password(body["password"])
            if not ValidationMethods().validate_number(body["mobile"], num_type="mobile"):
                return self.response(
                    status.HTTP_400_BAD_REQUEST, ErrorMessage.invalidMobileNumber
                )

            if user_type.value == UserTypeEnum.CUSTOMER.value:
                # Check body's Email already exist
                file_path = f"{aws_config.AWS_USER_PROFILE_PATH}{uuid.uuid4()}"
                user_data = await self.check_existing_user_details_with_email(
                    request, profile_image, User, file_path, body, db
                )
                if user_data.status_code != status.HTTP_200_OK:
                    return self.response(
                        status.HTTP_400_BAD_REQUEST,
                        json.loads(user_data.body)["message"],
                    )

                data = json.loads(user_data.body)["data"]
                code = self.generate_otp_code()
                user_obj = User(
                    full_name=body["full_name"],
                    email=body["email"],
                    password=data["hashed_password"],
                    user_type=user_type.value,
                    mobile=data["contact"],
                    profile_image=data["profile_image"],
                    code=code
                )

            else:
                user_obj = await self.register_driver_service(
                    request, db, user_type, body, profile_image
                )

                if isinstance(user_obj, Response):
                    if user_obj.status_code != status.HTTP_200_OK:
                        return self.response(
                            status.HTTP_400_BAD_REQUEST,
                            json.loads(user_obj.body)["message"],
                        )

            model = Driver if user_type.value == UserTypeEnum.DRIVER.value else User
            if not await DataBaseMethod(model).save(user_obj, db):
                return self.response(
                    status.HTTP_400_BAD_REQUEST, ErrorMessage.internalServerErr
                )

            # Commit the transaction so that the changes are saved in the database.
            # TODO :- commit after all opertaions like otp generation and email sending.
            await db.commit()
            response_data = jsonable_encoder(user_obj)
            profile_image = (
                f"{aws_config.AWS_BASE_URL}{response_data['profile_image']}"
                if response_data["profile_image"]
                else constant.STATUS_NULL
            )
            response_data.pop("password")

            if self.convert_datetime_format(response_data) is None:
                return self.response(
                    status.HTTP_400_BAD_REQUEST, ErrorMessage.errGeneratingRes
                )

            return self.response(
                status.HTTP_201_CREATED,
                InfoMessage.userSignupSuccess,
                RegisterResSchema().dump(response_data),
            )

        except ValueError as ve:
            return self.response(
                status.HTTP_400_BAD_REQUEST,
                str(ve)
            )

        except Exception:
            return self.response(
                status.HTTP_400_BAD_REQUEST,
                ErrorMessage.generalTryAgain,
            )

    async def register_driver_service(
        self, request, db: AsyncSession, user_type, body: dict, profile_image_file
    ):
        """
        Registers a new driver.

        Args:
            db (AsyncSession): The database session.
            user_type (UserType): The user type (driver).
            body (dict): The request body containing driver details.

        Returns:
            User: The registered driver object.
        """
        try:
            file_path = f"{aws_config.AWS_DRIVER_PROFILE_PATH}{uuid.uuid4()}"
            driver_data = await self.check_existing_user_details_with_email(
                request, profile_image_file, Driver, file_path, body, db
            )
            if driver_data.status_code != status.HTTP_200_OK:
                return self.response(
                    status.HTTP_400_BAD_REQUEST, json.loads(driver_data.body)["message"]
                )

            data = json.loads(driver_data.body)["data"]
            user_obj = Driver(
                full_name=body["full_name"],
                email=body["email"],
                password=data["hashed_password"],
                user_type=user_type.value,
                mobile=data["contact"],
                profile_image=data["profile_image"],
                # By default status is pending
                is_docs_verified=DriverStatusEnum.INITIAL.value
            )

            return user_obj
        except Exception:
            return self.response(
                status.HTTP_400_BAD_REQUEST, ErrorMessage.driverSignupFailed
            )

    async def check_existing_user_details_with_email(
        self,
        request,
        profile_image_file,
        model_name: str,
        file_path: str,
        body: dict,
        db: AsyncSession,
    ):
        """
        Checks if a user with the given email already exists.

        Args:
            db (AsyncSession): The database session.
            email (str): The email address of the user.

        Returns:
            dict: data dict if the user exists, False otherwise.
        """
        try:
            email = body["email"]
            mobile = body["mobile"]

            email_exists = (
                await UserAuthMethod(User).find_by_email(db, email)
                or await UserAuthMethod(Driver).find_by_email(db, email)
            )
            if email_exists:
                return self.response(
                    status.HTTP_400_BAD_REQUEST, ErrorMessage.emailAllreadyExists
                )

            mobile_exists = (
                await UserAuthMethod(User).find_verified_mobile_user(db, mobile)
                or await UserAuthMethod(Driver).find_verified_mobile_user(db, mobile)
            )
            if mobile_exists:
                return self.response(
                    status.HTTP_400_BAD_REQUEST, "Mobile number already exists."
                )
            hashed_password = generate_password_hash(body["password"])
            contact = body["mobile"] if body["mobile"] else constant.STATUS_NULL
            if profile_image_file:
                profile_image = self.get_upload_file_to_s3(
                    request, profile_image_file, file_path
                )
            else:
                profile_image = constant.STATUS_NULL

            data = {
                "hashed_password": hashed_password,
                "contact": contact,
                "profile_image": profile_image,
            }
            return self.response(
                status.HTTP_200_OK, InfoMessage.imageUploadSuccess, data
            )
        except Exception:
            return constant.STATUS_FALSE
