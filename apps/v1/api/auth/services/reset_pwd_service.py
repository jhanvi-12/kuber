"""This module contains reset password functionality."""

import bcrypt
from fastapi import HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from apps.v1.api.auth.models.model import User
from apps.v1.api.base_service import BaseResponseService
from apps.v1.api.auth.models.method import UserAuthMethod
from core.utils.message_variable import InfoMessage, ErrorMessage
from core.utils.db_method import DataBaseMethod
from datetime import datetime, timedelta
from config import mail_config
from apps.v1.api.driver.models.model import Driver
from apps.v1.api.auth.services.login_service import LoginService
from core.utils.token_authentication import JWTOAuth2
from apps.v1.api.auth.models.attribute import UserTypeEnum
from werkzeug.security import generate_password_hash

RESET_TOKEN_EXPIRY_MINUTES = 15


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify if the given plain password matches the hashed password."""
    return bcrypt.checkpw(
        plain_password.encode("utf-8"), hashed_password.encode("utf-8")
    )


def get_password_hash(password: str) -> str:
    """Hash the password using bcrypt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


class ResetPasswordService(BaseResponseService):
    """Reset password functionality"""

    async def get_reset_password_service(self, db: AsyncSession, body):
        """
        Resets the password for the given user.
        Args:
            db (AsyncSession): The database session.
            user_id (int): The ID of the user.
            new_password (str): The new password.
        Returns:
            StandardResponse: The response object with status and message.
        """
        try:
            body = body.dict()
            data = JWTOAuth2().verify_access_token(body["token"])

            if not data:
                return self.response(
                    status.HTTP_404_NOT_FOUND, ErrorMessage.expiredToken
                )

            user_object = await LoginService().get_user_by_email(db, data)
            if not user_object:
                return self.response(
                    status.HTTP_404_NOT_FOUND, ErrorMessage.userNotFound
                )

            user_object.password = generate_password_hash(body["new_password"])
            model = User if user_object.user_type == UserTypeEnum.CUSTOMER else Driver
            if not await DataBaseMethod(model).save(user_object, db):
                return self.response(
                    status.HTTP_400_BAD_REQUEST,
                    ErrorMessage.genericError,
                )
            await db.commit()

            return self.response(
                status.HTTP_200_OK,
                InfoMessage.resetPasswordSuccess,
            )

        except Exception:
            return self.response(
                status.HTTP_400_BAD_REQUEST,
                ErrorMessage.somethingWentWrong,
            )

    async def get_forgot_password_service(
        self, db: AsyncSession, body: dict, background_tasks: BackgroundTasks
    ):
        """
        This function responds to a request forgot password
        to send reset password link

        Args:
            body (object): Request parameters
        Returns:
            Return reset password link
        """
        try:
            email = body["email"]
            # Checking email against existing email in db.
            user_object = await LoginService().get_user_by_email(db, email)
            if not user_object:
                return self.response(
                    status.HTTP_404_NOT_FOUND, ErrorMessage.userNotFound
                )
                
            # Generate reset password token (valid for 15 minutes)
            reset_token = JWTOAuth2().create_reset_token(
                {
                    "sub": email,
                    "exp": datetime.utcnow()
                    + timedelta(minutes=RESET_TOKEN_EXPIRY_MINUTES),
                }
            )

            # TODO : add FE url here.
            reset_link = (
                f"https://yourdomain.com/reset-password?token={reset_token}"
            )

            # Email subject & template
            subject = mail_config.RESET_PASSWORD_MAIL_SUBJECT
            html_file = "reset_password.html"
            render_args = {
                "reset_link": reset_link,
                "username": user_object.full_name,
            }

            # Send email in the background
            # EmailService().send_email_background(background_tasks, subject, email, render_args, html_file)

            return self.response(
                status.HTTP_200_OK,
                "Reset password link sent to your email successfully!",
            )
        except Exception:
            return self.response(status.HTTP_400_BAD_REQUEST, None, "User not found!")
