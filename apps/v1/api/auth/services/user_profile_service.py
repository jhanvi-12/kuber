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
            user_obj.full_name = body.get("full_name") if body.get("full_name") is not None else user_obj.full_name
            user_obj.email = body.get("email") if body.get("email") is not None else user_obj.email

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
            data["profile_image"] = (
                    f"{aws_config.AWS_BASE_URL}{data['profile_image']}"
            )
            data.pop("password")
            return self.response(status.HTTP_200_OK, InfoMessage.userUpdated, data)
        except Exception:
            return self.response(
                status.HTTP_400_BAD_REQUEST, ErrorMessage.generalTryAgain
            )

    async def change_user_number_service(
        self, db: AsyncSession, current_user: dict, body: dict
    ):
        """This method is used to initiate the change of user's mobile number by generating and sending OTP to user's email."""
        try:
            # Validate mobile number
            mobile = body.get("mobile")
            if not self.validate_mobile_number(mobile):
                return self.response(
                    status.HTTP_400_BAD_REQUEST, ErrorMessage.invalidMobileNumber
                )

            user_obj = await self.get_current_user_details(db, current_user)
            if not user_obj:
                return self.response(
                    status.HTTP_401_UNAUTHORIZED, ErrorMessage.userNotFound
                )

            user_obj.mobile = mobile
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
            return self.response(status.HTTP_200_OK, InfoMessage.numberChanged, data)
        except Exception as e:
            return self.response(
                status.HTTP_400_BAD_REQUEST, ErrorMessage.generalTryAgain
            )
