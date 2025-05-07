"""This module is used to defines the user profile related service functionality."""

import uuid
from datetime import datetime

from fastapi import status
from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession

from apps.v1.api.auth.models.attribute import UserTypeEnum
from apps.v1.api.auth.models.method import UserAuthMethod
from apps.v1.api.auth.models.model import OtpVerification, User
from apps.v1.api.base_service import BaseResponseService
from apps.v1.api.driver.models.model import Driver
from config import aws_config, mail_config
from core.utils import constant_variable as constant
from core.utils.db_method import DataBaseMethod
from core.utils.email_service import EmailService
from core.utils.message_variable import ErrorMessage, InfoMessage


class UserProfileService(BaseResponseService):
    """
    This class is used to define the user profile and edit profile methods.
    """

    async def get_user_profile_service(self, db: AsyncSession, current_user: dict):
        """This method is used to fetch the user profile details.

        Args:
            db (AsyncSession): database session
            current_user (dict): current user data.
        """
        try:
            user_obj = await self.get_current_user_details(db, current_user)
            if not user_obj:
                return self.response(
                    status.HTTP_401_UNAUTHORIZED, ErrorMessage.userNotFound
                )
            data = jsonable_encoder(user_obj)
            data.pop("password")
            data["profile_image"] = f"{aws_config.AWS_BASE_URL}{data["profile_image"]}" if data.get("profile_image") else None

            return self.response(
                status.HTTP_200_OK, InfoMessage.userRetrievedSuccess, data
            )

        except Exception:
            return self.response(
                status.HTTP_400_BAD_REQUEST, ErrorMessage.generalTryAgain
            )

    async def get_edit_user_profile_service(
        self, request, db: AsyncSession, body, current_user
    ):
        """This method is used to edit the user profile details.
        Args:
            db (AsyncSession): database session
            body: request body
            current_user (dict): current user data.
        Returns:
            dict: response data
        """
        try:
            user_obj = await self.get_current_user_details(db, current_user)
            if not user_obj:
                return self.response(
                    status.HTTP_401_UNAUTHORIZED, ErrorMessage.userNotFound
                )

            # Upload image to S3 bucket if provided
            if body.get("profile_image"):
                file_obj = self.get_upload_file_to_s3(
                    request,
                    body["profile_image"],
                    f"{aws_config.AWS_USER_PROFILE_PATH}{uuid.uuid4()}",
                )
            else:
                file_obj = user_obj.profile_image

            user_obj.profile_image = file_obj
            user_obj.full_name = body.get("full_name", user_obj.full_name)
            user_obj.email = body.get("email", user_obj.email)

            model = (
                Driver
                if current_user["user_type"] == UserTypeEnum.DRIVER.value
                else User
            )

            if not await DataBaseMethod(model).save(user_obj, db):
                return self.response(
                    status.HTTP_400_BAD_REQUEST, ErrorMessage.errorSavingUser
                )

            data = jsonable_encoder(user_obj)
            data.pop("password")
            return self.response(status.HTTP_200_OK, InfoMessage.userUpdated, data)
        except Exception:
            return self.response(
                status.HTTP_400_BAD_REQUEST, ErrorMessage.generalTryAgain
            )

    async def get_change_number_service(
        self, db: AsyncSession, current_user: dict, number: str
    ):
        """This method is used to initiate the change of user's mobile number by generating and sending OTP to user's email."""
        try:
            # Validate mobile number
            if not self.validate_mobile_number(number):
                return self.response(
                    status.HTTP_400_BAD_REQUEST, ErrorMessage.invalidMobileNumber
                )

            user_obj = await self.get_current_user_details(db, current_user)
            if not user_obj:
                return self.response(
                    status.HTTP_401_UNAUTHORIZED, ErrorMessage.userNotFound
                )

            # Generate OTP
            otp_code = self.generate_otp_code()
            driver_id, user_id = (
                (user_obj.id, constant.STATUS_NULL)
                if user_obj.user_type == UserTypeEnum.DRIVER.value
                else (constant.STATUS_NULL, user_obj.id)
            )
            # Save OTP for this user and new number
            otp_obj = OtpVerification(
                user_id=user_id,
                driver_id=driver_id,
                otp_code=otp_code,
            )
            if not await DataBaseMethod(OtpVerification).save(otp_obj, db):
                return self.response(
                    status.HTTP_400_BAD_REQUEST, ErrorMessage.otpGenerationFailed
                )
            await db.commit()

            # Send OTP to user's email
            html_file = "otp_email_verification.html"
            body = {"otp_code": otp_code}
            try:
                EmailService().send_mail(
                    mail_config.OTP_MAIL_SUBJECT, body, html_file, user_obj.email
                )
            except Exception as e:
                print(f"Error in send_mail: {str(e)}")
            return self.response(status.HTTP_200_OK, InfoMessage.otpSent)
        except Exception as e:
            print(f"Error in get_change_number_service: {str(e)}")
            return self.response(
                status.HTTP_400_BAD_REQUEST, ErrorMessage.generalTryAgain
            )

    async def verify_change_number_otp_service(
        self, db: AsyncSession, current_user: dict, number: str, otp_code: int
    ):
        """This method verifies the OTP and updates the user's mobile number if OTP is valid."""
        try:
            # Validate mobile number
            if not self.validate_mobile_number(number):
                return self.response(
                    status.HTTP_400_BAD_REQUEST, ErrorMessage.invalidMobileNumber
                )

            user_obj = await self.get_current_user_details(db, current_user)
            if not user_obj:
                return self.response(
                    status.HTTP_401_UNAUTHORIZED, ErrorMessage.userNotFound
                )

            driver_id, user_id = (
                (user_obj.id, constant.STATUS_NULL)
                if user_obj.user_type == UserTypeEnum.DRIVER.value
                else (constant.STATUS_NULL, user_obj.id)
            )
            # Fetch OTP verification record
            otp_record = await UserAuthMethod(
                OtpVerification
            ).find_user_by_otp_reference(db, otp_code, user_id, driver_id)
            if not otp_record:
                return self.response(
                    status.HTTP_400_BAD_REQUEST, ErrorMessage.invalidOtp
                )
            # Check if OTP is expired
            if (
                hasattr(otp_record, "expires_at")
                and otp_record.expires_at < datetime.now()
            ):
                return self.response(
                    status.HTTP_400_BAD_REQUEST, ErrorMessage.otpExpired
                )
            # OTP is valid, update the number
            user_obj.mobile = number
            if not await DataBaseMethod(type(user_obj)).save(user_obj, db):
                return self.response(
                    status.HTTP_400_BAD_REQUEST, ErrorMessage.errorSavingUser
                )
            await db.commit()
            data = jsonable_encoder(user_obj)
            data.pop("password", None)
            if data.get("profile_image"):
                data["profile_image"] = (
                    f"{aws_config.AWS_BASE_URL}{data['profile_image']}"
                )
            if not self.convert_datetime_format(data):
                return self.response(
                    status.HTTP_400_BAD_REQUEST, ErrorMessage.generalTryAgain
                )
            return self.response(status.HTTP_200_OK, InfoMessage.otpVerified, data)
        except Exception as e:
            print(f"Error in verify_change_number_otp_service: {str(e)}")
            return self.response(
                status.HTTP_400_BAD_REQUEST, ErrorMessage.generalTryAgain
            )
