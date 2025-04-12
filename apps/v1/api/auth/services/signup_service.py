"""
This module defines the service for admin user signup, including the creation of new admin users.
"""
import uuid
from fastapi import BackgroundTasks, status
from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession
from werkzeug.security import generate_password_hash

from apps.v1.api.auth.models.attribute import UserTypeEnum
from apps.v1.api.auth.models.method import UserAuthMethod
from apps.v1.api.auth.models.model import OtpVerification, User
from apps.v1.api.auth.serializer import RegisterResSchema
from apps.v1.api.base_service import BaseResponseService
from apps.v1.api.driver.models.model import Driver
from config import aws_config, mail_config
from core.utils import DataBaseMethod
from core.utils import constant_variable as constant
from core.utils import db_method
from core.utils.email_service import EmailService
from core.utils.message_variable import ErrorMessage, InfoMessage


class SignUpService(BaseResponseService):
    """
    This class represents the service for creating admin users.

    Methods:
        create_signup_service(db, body): Creates a new admin user.
    """

    async def create_signup_service(self, request, db: AsyncSession, user_type, body):
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
            body = body.dict()
            if user_type.value == UserTypeEnum.CUSTOMER.value:
                # Check body's Email already exist
                file_path = f"{aws_config.AWS_USER_PROFILE_PATH}{uuid.uuid4()}"
                data = await self.check_existing_user_details_with_email(
                    request, User, file_path, body, db
                )
                if not data:
                    return self.response(
                        status.HTTP_400_BAD_REQUEST, ErrorMessage.errorCreatingUser
                    )
                user_obj = User(
                    full_name=body["full_name"],
                    email=body["email"],
                    password=data["hashed_password"],
                    user_type=user_type.value,
                    mobile=data["contact"],
                    profile_image=data["profile_image"],
                )

            else:
                user_obj = await self.register_driver_service(
                    request, db, user_type, body
                )
                if user_obj is constant.STATUS_FALSE:
                    return self.response(
                        status.HTTP_400_BAD_REQUEST, ErrorMessage.emailAllreadyExists
                    )

            model = Driver if user_type.value == UserTypeEnum.DRIVER.value else User
            if not await DataBaseMethod(model).save(user_obj, db):
                return self.response(
                    status.HTTP_400_BAD_REQUEST, ErrorMessage.internalServerErr
                )

            # Commit the transaction so that the changes are saved in the database.
            await db.commit()
            data = jsonable_encoder(user_obj)
            data.pop("password")

            if self.convert_datetime_format(data) is None:
                return self.response(
                    status.HTTP_400_BAD_REQUEST, ErrorMessage.errGeneratingRes
                )
            response_data = RegisterResSchema().dump(data)

            # Generate otp for the user
            otp_code = await self.create_otp_code_service(db, user_obj)
            if otp_code is constant.STATUS_FALSE:
                return self.response(
                    status.HTTP_400_BAD_REQUEST, ErrorMessage.otpGenerationFailed
                )

            # Send Otp in register user email
            html_file = "otp_email_verification.html"
            background_tasks = BackgroundTasks()
            body = {"otp_code": otp_code}
            # EmailService().send_mail(mail_config.OTP_MAIL_SUBJECT, body, html_file, user_obj.email)

            return self.response(
                status.HTTP_201_CREATED,
                InfoMessage.userSignupSuccess,
                response_data,
            )
        except Exception:
            return self.response(
                status.HTTP_400_BAD_REQUEST,
                ErrorMessage.generalTryAgain,
            )

    async def create_otp_code_service(self, db: AsyncSession, user_obj):
        """
        Generates and saves a one-time password (OTP) for the given email.

        Args:
            db (AsyncSession): The database session.
            email (str): The email address of the user.

        Returns:
            str: The generated OTP code.
        """
        try:
            # Generate a random OTP code
            otp_code = self.generate_otp_code()

            driver_id, user_id = (
                (user_obj.id, constant.STATUS_NULL)
                if user_obj.user_type.value == UserTypeEnum.DRIVER.value
                else (constant.STATUS_NULL, user_obj.id)
            )
            # Save the OTP code in the database
            otp_obj = OtpVerification(
                user_id=user_id, driver_id=driver_id, otp_code=otp_code
            )
            if not await db_method.DataBaseMethod(OtpVerification).save(otp_obj, db):
                return constant.STATUS_FALSE

            await db.commit()
            return otp_code
        except Exception:
            return self.response(
                status.HTTP_400_BAD_REQUEST, ErrorMessage.otpGenerationFailed
            )

    async def register_driver_service(
        self, request, db: AsyncSession, user_type, body: dict
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
            data = await self.check_existing_user_details_with_email(
                request, Driver, file_path, body, db
            )
            if not data:
                return self.response(
                    status.HTTP_400_BAD_REQUEST, ErrorMessage.emailAllreadyExists
                )

            user_obj = Driver(
                full_name=body["full_name"],
                email=body["email"],
                password=data["hashed_password"],
                user_type=user_type.value,
                mobile=data["contact"],
                profile_image=data["profile_image"],
            )

            return user_obj
        except Exception:
            return constant.STATUS_FALSE

    async def check_existing_user_details_with_email(
        self, request, model_name, file_path, body: dict, db: AsyncSession
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
            if await UserAuthMethod(model_name).find_by_email(db, body["email"]):
                return self.response(
                    status.HTTP_400_BAD_REQUEST, ErrorMessage.emailAllreadyExists
                )
            hashed_password = generate_password_hash(body["password"])
            contact = body["mobile"] if body["mobile"] else constant.STATUS_NULL
            if body["profile_image"]:
                profile_image = self.get_upload_file_to_s3(
                    request, body["profile_image"], file_path
                )
            else:
                profile_image = constant.STATUS_NULL
            data = {
                "hashed_password": hashed_password,
                "contact": contact,
                "profile_image": profile_image,
            }
            return data
        except Exception:
            return constant.STATUS_FALSE
