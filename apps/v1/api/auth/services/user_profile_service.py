"""This module is used to defines the user profile related service functionality."""

from fastapi import status
from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession

from apps.v1.api.auth.models.attribute import UserTypeEnum
from apps.v1.api.auth.models.model import User
from apps.v1.api.base_service import BaseResponseService
from apps.v1.api.driver.models.model import Driver
from config import aws_config
from core.utils.db_method import DataBaseMethod
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
            data["profile_image"] = f"{aws_config.AWS_BASE_URL}{data["profile_image"]}"

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
            body = body.dict()
            user_obj = await self.get_current_user_details(db, current_user)
            if not user_obj:
                return self.response(
                    status.HTTP_401_UNAUTHORIZED, ErrorMessage.userNotFound
                )

            # Upload image to S3 bucket if provided
            if body.get("profile_image"):
                file_obj = self.get_upload_file_to_s3(
                    request, body["profile_image"],
                    aws_config.AWS_USER_PROFILE_PATH
                    )
            else:
                file_obj = user_obj.profile_image

            user_obj.profile_image = file_obj
            user_obj.full_name = body.get("full_name", user_obj.full_name)
            user_obj.email = body.get("email", user_obj.email)

            model = Driver if current_user["user_type"] == UserTypeEnum.DRIVER.value else User

            if not await DataBaseMethod(model).save(user_obj, db):
                return self.response(
                    status.HTTP_400_BAD_REQUEST, ErrorMessage.errorSavingUser
                )

            data = jsonable_encoder(user_obj)
            data.pop("password")
            return self.response(
                status.HTTP_200_OK, InfoMessage.userUpdated, data
            )
        except Exception:
            return self.response(
                status.HTTP_400_BAD_REQUEST, ErrorMessage.generalTryAgain
            )
