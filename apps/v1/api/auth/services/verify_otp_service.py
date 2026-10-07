"""This module is responsible for the OTP services"""

import json
from datetime import datetime, timedelta

from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from apps.v1.api.auth.models.attribute import OtpTypeEnum
from apps.v1.api.auth.models.method import UserAuthMethod
from apps.v1.api.auth.models.model import OtpVerification, User
from apps.v1.api.base_service import BaseResponseService
from apps.v1.api.driver.models.model import Driver
from apps.v1.api.resend_email_service import send_otp_email
from config import aws_config
from core.utils import db_method
from core.utils.message_variable import ErrorMessage, InfoMessage
from core.utils import constant_variable as constant


class VerifyOtpService(BaseResponseService):
    """
    Service class for verifying OTP.
    """

    async def verify_otp_service(self, db: AsyncSession, body):
        """
        Verifies the OTP for the given user.

        Args:
            db (AsyncSession): The database session.
            body (dict): The request body containing email, OTP, and otp_type.

        Returns:
            dict: The response containing the user details and success/failure message.
        """
        try:
            body = body.dict()
            email = body["email"].strip()
            otp_code = body["otp"]
            otp_type = body["otp_type"]
            otp_obj = await UserAuthMethod(OtpVerification).find_by_user_email(
                db, email, otp_code, otp_type
            )
            if not otp_obj:
                return self.response(
                    status.HTTP_404_NOT_FOUND, ErrorMessage.otpExpiredOrInvalid
                )

            otp_obj.is_verified = constant.STATUS_TRUE
            db.add(otp_obj)
            await db.commit()
            return self.response(status.HTTP_200_OK, InfoMessage.otpVerified)

        except Exception:
            return self.response(
                status.HTTP_400_BAD_REQUEST, ErrorMessage.internalServerErr
            )

    async def create_otp_code_service(self, db: AsyncSession, email, otp_type):
        """
        Generates and saves a one-time password (OTP) for the given email.

        Reuses the existing row for the same email and otp_type when present.
        The account does not exist yet for a register OTP, so user_id and
        driver_id stay empty until register links them.

        Args:
            db (AsyncSession): The database session.
            email (str): The email address of the user.
            otp_type (int): 1 for register, 2 for forgot password.

        Returns:
            str: The generated OTP code.
        """
        try:
            otp_code = self.generate_otp_code()
            existing = await UserAuthMethod(OtpVerification).find_by_email_and_otp_type(
                db, email, otp_type
            )
            expires_at = datetime.now() + timedelta(minutes=constant.STATUS_FIVE)

            if existing:
                existing.otp_code = otp_code
                existing.is_verified = constant.STATUS_FALSE
                existing.expires_at = expires_at
                existing.updated_at = datetime.now()
                existing.deleted_at = constant.STATUS_NULL
                otp_obj = existing
            else:
                otp_obj = OtpVerification(
                    email=email,
                    otp_code=otp_code,
                    otp_type=otp_type,
                    is_verified=False,
                    expires_at=expires_at,
                )
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

    async def _registered_account_exists(self, db: AsyncSession, email: str) -> bool:
        """True when the email belongs to an active customer or driver."""
        customer = await UserAuthMethod(User).find_active_by_email_ci(db, email)
        if customer:
            return True
        driver = await UserAuthMethod(Driver).find_active_by_email_ci(db, email)
        return driver is not None

    async def request_otp_service(self, db: AsyncSession, body):
        """Generates and sends a new OTP to the user.

        Args:
            db (AsyncSession): The database session.
            body: email and otp_type from the request payload.
        """
        try:
            body = body.dict()
            email = body["email"].strip()
            otp_type = body["otp_type"]

            if otp_type not in (
                OtpTypeEnum.REGISTER.value,
                OtpTypeEnum.FORGOT_PASSWORD.value,
            ):
                return self.response(
                    status.HTTP_400_BAD_REQUEST, ErrorMessage.invalidOtpType
                )

            # Forgot password can only be sent to an account that already exists.
            # Register OTP is allowed before the account is created.
            if otp_type == OtpTypeEnum.FORGOT_PASSWORD.value:
                if not await self._registered_account_exists(db, email):
                    return self.response(
                        status.HTTP_404_NOT_FOUND, ErrorMessage.otpOnlyExistingUser
                    )

            otp_obj = await self.create_otp_code_service(db, email, otp_type)

            if otp_obj.status_code != status.HTTP_200_OK:
                return self.response(
                    status.HTTP_400_BAD_REQUEST, ErrorMessage.otpGenerationFailed
                )
            otp_code = json.loads(otp_obj.body)["data"]

            email_res = send_otp_email(
                email, str(otp_code["otp_code"]), aws_config.KUBER_LOGO
            )

            if not email_res:
                return self.response(
                    status.HTTP_400_BAD_REQUEST, ErrorMessage.otpSendFailed
                )
            return self.response(
                status.HTTP_200_OK, InfoMessage.otpGenerationSuccess
            )
        except Exception:
            return self.response(
                status.HTTP_400_BAD_REQUEST, ErrorMessage.generalTryAgain
            )
