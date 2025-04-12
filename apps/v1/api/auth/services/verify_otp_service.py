"""This module is responsible for the OTP services"""

from datetime import datetime, timedelta

from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from apps.v1.api.auth.models.attribute import UserTypeEnum
from apps.v1.api.auth.models.method import UserAuthMethod
from apps.v1.api.auth.models.model import OtpVerification
from apps.v1.api.auth.services.login_service import LoginService
from apps.v1.api.base_service import BaseResponseService
from core.utils import constant_variable as constant
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
            user_obj = await LoginService().get_user_by_email(db, email)
            if not user_obj:
                return self.response(
                    status.HTTP_404_NOT_FOUND, ErrorMessage.userNotVerifiedOrFound
                )

            driver_id, user_id = (
                (user_obj.id, constant.STATUS_NULL)
                if user_obj.user_type.value == UserTypeEnum.DRIVER.value
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
            if otp_record.expires_at - datetime.now() <= timedelta(minutes=constant.STATUS_FIVE):
                return self.response(
                    status.HTTP_400_BAD_REQUEST, ErrorMessage.otpExpired
                )

            user_obj.is_verified = constant.STATUS_TRUE
            db.add(user_obj)

            await db.commit()
            # OTP is valid
            return self.response(status.HTTP_200_OK, InfoMessage.otpVerified)

        except Exception:
            return self.response(
                status.HTTP_400_BAD_REQUEST, ErrorMessage.generalTryAgain
            )
