"""
This module provides the implementation of the login service,
including the login operation.

Classes:
    LoginService: A service class for handling user login.

Methods:
    get_login_service(response, db, body): Performs the login operation.
"""

import uuid

import uuid

from fastapi import status
from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession
from werkzeug.security import check_password_hash

from apps.v1.api.auth.models.attribute import UserTypeEnum
from apps.v1.api.auth.models.method import UserAuthMethod
from apps.v1.api.auth.models.model import User, Admin
from apps.v1.api.base_service import BaseResponseService
from apps.v1.api.driver.models.model import Driver
from apps.v1.api.plans.models.method import PlansMethod
from apps.v1.api.plans.models.model import Plans
from config import aws_config
from core.utils import constant_variable as constant
from core.utils.message_variable import ErrorMessage, InfoMessage
from core.utils.token_authentication import JWTOAuth2
from apps.v1.api.driver.models.attribute import DriverStatusEnum
from apps.v1.api.auth.models.model import OtpVerification
from apps.v1.api.auth.models.model import Session
from apps.v1.api.auth.models.method import UserAuthMethod

class LoginService(BaseResponseService):
    """This class represents the login service"""

    async def get_login_service(self, db: AsyncSession, body):
        """
        Performs login operation.

        Args:
            response (Response): The response object.
            db (AsyncSession): The database session.
            body (dict): The request body containing login details.

        Returns:
            StandardResponse: The response object with status and message.
        """
        try:
            body = body.dict()
            # check if user email is exists or not.
            user_obj = await self.get_verified_user_by_email(db, body["email"], body.get("user_type"))
            if not user_obj:
                return self.response(
                    status.HTTP_404_NOT_FOUND, ErrorMessage.userNotFound
                )
            if not check_password_hash(user_obj.password, body["password"]):
                return self.response(
                    status.HTTP_401_UNAUTHORIZED,
                    ErrorMessage.invalidCred,
                )

            jti = str(uuid.uuid4())
            # Generate auth2 token
            token_data = {
                    "user_id": user_obj.id,
                    "jti": jti,
                    "email": user_obj.email,
                    "user_type": user_obj.user_type.value,
                }

            data = jsonable_encoder(user_obj)

            data.pop("password")
            data["profile_image"] = (
                f"{aws_config.AWS_BASE_URL}{data['profile_image']}"
                if data["profile_image"]
                else constant.STATUS_NULL
            )

            if user_obj.user_type == UserTypeEnum.DRIVER.value:
                plan_data = await PlansMethod(Plans).find_plan_by_driver_id(
                    db, user_obj.id
                )
                data["plan_details"] = jsonable_encoder(plan_data) if plan_data else constant.STATUS_NULL

            token = JWTOAuth2().encode_access_token(token_data)
            data["access_token"] = (
                token.decode("utf-8") if isinstance(token, bytes) else token
            )

            # Check if user/driver already has an active session
            if user_obj.user_type == UserTypeEnum.DRIVER.value:
                user_id, driver_id = None, user_obj.id
                existing_session = await UserAuthMethod(Session).find_active_session_by_id(db, user_id, driver_id)
            else:
                user_id, driver_id = user_obj.id, None
                existing_session = await UserAuthMethod(Session).find_active_session_by_id(db, user_id, driver_id)

            if existing_session:
                return self.response(
                    status.HTTP_409_CONFLICT,
                    ErrorMessage.alreadyLoggedIn,
                )

            session = Session(
                user_id=user_id,
                driver_id=driver_id,
                session_id=jti,
            )
            db.add(session)
            await db.commit()

            return self.response(
                status.HTTP_200_OK,
                InfoMessage.loginSuccess,
                data,
            )

        except Exception:
            return self.response(
                status.HTTP_400_BAD_REQUEST,
                ErrorMessage.generalTryAgain,
            )

    async def get_admin_login_service(self, db: AsyncSession, body):
        """
        Performs admin login operation.

        Args:
            response (Response): The response object.
            db (AsyncSession): The database session.
            body (dict): The request body containing login details.

        Returns:
            StandardResponse: The response object with status and message.
        """
        try:
            body = body.dict()
            # check if admin email is exists or not.
            admin_obj = await UserAuthMethod(Admin).find_by_email(db, body.get("email"))
            if not admin_obj:
                return self.response(
                    status.HTTP_404_NOT_FOUND, ErrorMessage.userNotFound
                )
            if not check_password_hash(admin_obj.password, body["password"]):
                return self.response(
                    status.HTTP_401_UNAUTHORIZED,
                    ErrorMessage.invalidCred,
                )

            # Generate auth2 token
            token_data = {
                    "user_id": admin_obj.id,
                    "email": admin_obj.email,
                    "user_type": "admin",
                }

            data = jsonable_encoder(admin_obj)
            data.pop("password")

            token = JWTOAuth2().encode_access_token(token_data)
            data["access_token"] = (
                token.decode("utf-8") if isinstance(token, bytes) else token
            )

            return self.response(
                status.HTTP_200_OK,
                InfoMessage.loginSuccess,
                data,
            )

        except Exception:
            return self.response(
                status.HTTP_400_BAD_REQUEST,
                ErrorMessage.generalTryAgain,
            )

    async def create_device_token(self, db: AsyncSession, body, current_user):
        """This service is used to create a device token

        Args:
            db (AsyncSession): The database session
            body (dict): payoad of device token
            current_user (dict): current_user for which need to generate device token
        """
        try:
            body = body.dict()
            # check if user email is exists or not.
            user_obj = await self.get_verified_user_by_email(db, current_user["email"], current_user["user_type"])
            if not user_obj:
                return self.response(
                    status.HTTP_404_NOT_FOUND, ErrorMessage.userNotFound
                )

            device_token = body.get("device_token", None)
            platform = body.get("platform", None)
            device_id = body.get("device_id", None)
            res = await UserAuthMethod(
                User
                if current_user["user_type"] == UserTypeEnum.CUSTOMER.value
                else Driver
            ).create_or_find_device_token(db, user_obj.id, device_token, platform, device_id)

            if not res:
                return self.response(
                    status.HTTP_400_BAD_REQUEST,
                    "Error while generating Device token"
                )
            return self.response(
                status.HTTP_200_OK,
                InfoMessage.deviceTokenGenerated
            )

        except Exception:
            return self.response(
                status.HTTP_400_BAD_REQUEST,
                ErrorMessage.generalTryAgain,
            )

    async def get_user_by_email(self, db: AsyncSession, email: str):
        """
        Finds a user by email.

        Args:
            db (AsyncSession): The database session.
            email (str): The email address.

        Returns:
            User: The user object if found, else None.
        """
        user_obj = await UserAuthMethod(User).find_by_email(db, email)
        if not user_obj:
            user_obj = await UserAuthMethod(Driver).find_by_email(db, email)
        return user_obj

    async def get_verified_user_by_email(self, db: AsyncSession, email: str, user_type: str):
        """
        Finds a user by email.

        Args:
            db (AsyncSession): The database session.
            email (str): The email address.

        Returns:
            User: The user object if found, else None.
        """
        user_type_model = Driver if user_type == "driver" else User
        user_obj = await UserAuthMethod(user_type_model).find_verified_email_user(db, email)
        return user_obj
