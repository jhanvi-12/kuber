"""This module is responsible for the OTP services"""

import json

from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from apps.v1.api.auth.models.method import UserAuthMethod
from apps.v1.api.auth.models.model import OtpVerification
from apps.v1.api.base_service import BaseResponseService
from apps.v1.api.sendgrid_email_service import send_otp_email
from config import aws_config
from core.utils import db_method
from core.utils.message_variable import ErrorMessage, InfoMessage


class VerifyOtpService(BaseResponseService):
    """
    Service class for verifying OTP.
    """

    async def verify_otp_service(self, db: AsyncSession, body):
        """
        Verifies the OTP for the given user.

        Args:
            db (AsyncSession): The database session.
            body (dict): The request body containing email and OTP.

        Returns:
            dict: The response containing the user details and success/failure message.
        """
        try:
            body = body.dict()
            email = body["email"]
            otp_code = body["otp"]
            # Fetch user by email
            user_obj = await UserAuthMethod(OtpVerification).find_by_user_email(
                db, email, otp_code
            )
            if not user_obj:
                return self.response(
                    status.HTTP_404_NOT_FOUND, ErrorMessage.otpExpiredOrInvalid
                )

            # OTP is valid
            return self.response(status.HTTP_200_OK, InfoMessage.otpVerified)

        except Exception:
            return self.response(
                status.HTTP_400_BAD_REQUEST, ErrorMessage.internalServerErr
            )

    async def create_otp_code_service(self, db: AsyncSession, email):
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
            # Save the OTP code in the database
            otp_obj = OtpVerification(email=email, otp_code=otp_code)
            if not await db_method.DataBaseMethod(OtpVerification).save(otp_obj, db):
                return self.response(
                    status.HTTP_400_BAD_REQUEST, ErrorMessage.internalServerErr
                )

            await db.commit()
            return self.response(
                status.HTTP_200_OK,
                InfoMessage.otpGenerationSuccess,
                {"otp_code": otp_code},
            )
        except Exception:
            return self.response(
                status.HTTP_400_BAD_REQUEST, ErrorMessage.otpGenerationFailed
            )

    async def request_otp_service(self, db: AsyncSession, body):
        """Generates and sends a new OTP to the user.

        Args:
            db (AsyncSession): The database session.
            body (EmailStr): email of the user
        """
        try:
            body = body.dict()
            email = body["email"]

            # Generate otp for the user
            otp_obj = await self.create_otp_code_service(db, email)
            if otp_obj.status_code != status.HTTP_200_OK:
                return self.response(
                    status.HTTP_400_BAD_REQUEST, ErrorMessage.otpGenerationFailed
                )
            otp_code = json.loads(otp_obj.body)["data"]

            # Send Otp in register user email
            data = {"otp_code": otp_code["otp_code"]}
            # Send OTP to the user's email using sendgrid.
            email_res = send_otp_email(email, str(otp_code["otp_code"]), aws_config.KUBER_LOGO)

            if not email_res:
                return self.response(
                    status.HTTP_400_BAD_REQUEST, ErrorMessage.otpSendFailed
                )
            return self.response(
                status.HTTP_200_OK, InfoMessage.otpGenerationSuccess, data
            )
        except Exception:
            return self.response(
                status.HTTP_400_BAD_REQUEST, ErrorMessage.generalTryAgain
            )
