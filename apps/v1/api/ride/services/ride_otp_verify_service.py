"""This module is responsible to maintain the ride OTP verification logic."""

from fastapi import status
from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession

from apps.v1.api.auth.models.method import UserAuthMethod
from apps.v1.api.auth.models.model import User
from apps.v1.api.base_service import BaseResponseService
from apps.v1.api.driver.models.method import DriverMethod
from apps.v1.api.driver.models.model import Driver
from apps.v1.api.ride.models.model import Ride
from core.utils.message_variable import *


class RideOTPService(BaseResponseService):
    """This class is used to define the ride otp verification service methods."""

    async def ride_otp_verification_service(self, db: AsyncSession, body, current_user):
        """This method is used to verify the ride otp when driver accept the ride.

        Args:
            db (AsyncSession): DB session
            body (object): Body with otp and ride_id
            current_user (dict): USer data.
        """
        try:
            body = body.dict()
            driver_id = current_user["user_id"]
            driver_data = DriverMethod(Driver).get_driver_by_id(db, driver_id)
            if not await driver_data:
                return self.response(
                    status.HTTP_400_BAD_REQUEST, ErrorMessage.driverNotFound
                )

            ride_obj = await UserAuthMethod(Ride).find_by_id(db, body["ride_id"])
            if not ride_obj:
                return self.response(
                    status.HTTP_400_BAD_REQUEST, ErrorMessage.rideNotFound
                )

            user_obj = await UserAuthMethod(User).find_by_id(db, ride_obj.user_id)
            if not user_obj:
                return self.response(
                    status.HTTP_400_BAD_REQUEST, ErrorMessage.userNotVerifiedOrFound
                )

            ride_otp = user_obj.code
            if ride_otp != body["otp"]:
                return self.response(
                    status.HTTP_400_BAD_REQUEST, ErrorMessage.invalidOtp
                )

            return self.response(
                status.HTTP_200_OK, InfoMessage.otpVerified
            )

        except Exception:
            return self.response(
                status.HTTP_400_BAD_REQUEST, ErrorMessage.generalTryAgain
            )
