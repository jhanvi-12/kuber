"""This module contains logout functionality."""

from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession
from werkzeug.security import check_password_hash

from apps.v1.api.auth.models.attribute import UserTypeEnum
from apps.v1.api.auth.models.method import UserAuthMethod
from apps.v1.api.auth.models.model import Session, User
from apps.v1.api.auth.services.login_service import LoginService
from apps.v1.api.base_service import BaseResponseService
from core.utils import constant_variable as constant
from core.utils.message_variable import ErrorMessage, InfoMessage
from core.utils.token_authentication import JWTOAuth2


class UserLogoutService(BaseResponseService):
    """Service class for retrieving user details."""

    async def get_logout_service(self, db: AsyncSession, current_user: dict, session_id):
        """This method is called when the user is logged out.

        Args:
            db (AsyncSession): Database connection
            user_id (int): User ID.
        Returns:
            StandardResponse: A response object with status and message.
        """
        try:

            payload = JWTOAuth2().verify_access_token(session_id)
            jti = payload.get("jti")
            user_id = payload.get("user_id")

            if not jti:
                return self.response(
                    status.HTTP_400_BAD_REQUEST,
                    ErrorMessage.expiredToken
                )

            # Find session
            if current_user.get("user_type") == UserTypeEnum.DRIVER.value:
                user_id, driver_id = None, current_user.get("user_id")
            else:
                user_id, driver_id = current_user.get("user_id"), None
                user = await UserAuthMethod(User).find_by_id(db, user_id)
                if user:
                    user.code = constant.STATUS_NULL
                    db.add(user)
                    await db.commit()

            session_obj = await UserAuthMethod(Session).find_by_session_id(
                db, driver_id, user_id, jti
            )

            if not session_obj:
                return self.response(
                    status.HTTP_401_UNAUTHORIZED,
                    ErrorMessage.expiredToken
                )

            # DELETE session (important)
            await db.delete(session_obj)
            await db.commit()

            return self.response(
                status.HTTP_200_OK,
                InfoMessage.logoutSuccess
            )

        except Exception:
            return self.response(
                status.HTTP_401_UNAUTHORIZED,
                ErrorMessage.internalServerErr
            )

    async def clear_session_service(self, db: AsyncSession, body):
        """
        Clears the active login session for a customer or driver using credentials.
        Used when the user is locked out by an existing session on another device.

        Args:
            db (AsyncSession): The database session.
            body: LoginSchema with email, password, and user_type.

        Returns:
            StandardResponse: The response object with status and message.
        """
        try:
            body = body.dict()
            user_type = body.get("user_type")

            user_obj = await LoginService().get_verified_user_by_email(
                db, body["email"], user_type
            )
            if not user_obj:
                return self.response(
                    status.HTTP_404_NOT_FOUND, ErrorMessage.userNotFound
                )

            if not check_password_hash(user_obj.password, body["password"]):
                return self.response(
                    status.HTTP_401_UNAUTHORIZED,
                    ErrorMessage.invalidCred,
                )

            if user_type == UserTypeEnum.DRIVER.value:
                user_id, driver_id = None, user_obj.id
            else:
                user_id, driver_id = user_obj.id, None

            session_obj = await UserAuthMethod(Session).find_active_session_by_id(
                db, user_id, driver_id
            )
            if not session_obj:
                return self.response(
                    status.HTTP_404_NOT_FOUND,
                    ErrorMessage.noActiveSession,
                )

            await db.delete(session_obj)

            if user_type == UserTypeEnum.CUSTOMER.value:
                user = await UserAuthMethod(User).find_by_id(db, user_obj.id)
                if user:
                    user.code = constant.STATUS_NULL
                    db.add(user)

            await db.commit()

            return self.response(
                status.HTTP_200_OK,
                InfoMessage.sessionCleared,
            )

        except Exception:
            return self.response(
                status.HTTP_400_BAD_REQUEST,
                ErrorMessage.generalTryAgain,
            )
