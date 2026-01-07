"""This module is used to fetch the ride related all details for the driver and customer."""

from fastapi import status
from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession

from apps.v1.api.auth.models.method import UserAuthMethod
from apps.v1.api.auth.models.model import User
from apps.v1.api.base_service import BaseResponseService
from apps.v1.api.ride.models.model import Ride
from config import aws_config
from core.utils.message_variable import *
from apps.v1.api.driver.models.model import Driver
from apps.v1.api.driver.models.method import DriverMethod
from core.utils import constant_variable as constant
from apps.v1.api.ride.models.attribute import RideStatusEnum

class RideDetailService(BaseResponseService):
    """This class is used to get the ride details"""

    async def get_ride_details(self, db: AsyncSession, ride_id: int, driver_id: int):
        """Method to fetch the ride details using ride_id

        Args:
            db (AsyncSession): DB session
            ride_id (int): Ride ID.
            driver_id (int): Driver ID.
        """
        try:
            if not await UserAuthMethod(Driver).find_by_id(db, driver_id):
                return self.response(
                    status.HTTP_400_BAD_REQUEST, ErrorMessage.driverNotFound
                )
            data = await UserAuthMethod(Ride).find_by_id(db, ride_id)
            if not data:
                return self.response(
                    status.HTTP_400_BAD_REQUEST, ErrorMessage.rideNotFound
                )

            user_data = await UserAuthMethod(User).find_by_id(db, data.user_id)
            if not user_data:
                return self.response(
                    status.HTTP_400_BAD_REQUEST, ErrorMessage.userNotFound
                )

            response = jsonable_encoder(user_data)
            response.pop("device_token")
            response.pop("password")
            response["profile_image"] = (
                f"{aws_config.AWS_BASE_URL}{response["profile_image"]}"
                if response["profile_image"] is not None
                else None
            )
            return self.response(status.HTTP_200_OK, InfoMessage.rideFound, response)

        except Exception:
            return self.response(
                status.HTTP_400_BAD_REQUEST, ErrorMessage.generalTryAgain
            )

    async def driver_reached_service(self, db: AsyncSession, ride_id, driver_id):
        """
        Update the ride status when the driver reaches the pickup location.
        Args:
            db (AsyncSession): The database session.
            body (dict): The request body containing ride details.
            Returns:
            StandardResponse: The response object with status and message.
        """
        try:
            ride = await DriverMethod(Ride).get_driver_by_id(db, ride_id)
            if not ride:
                return self.response(
                    status.HTTP_404_NOT_FOUND,
                    ErrorMessage.rideNotFound
                )

            # 2️⃣ Validate driver assignment (🔥 MOST IMPORTANT)
            if ride.driver_id != driver_id:
                return self.response(
                    status.HTTP_403_FORBIDDEN,
                    ErrorMessage.driverNotAssignedToRide
                )

            # 3️⃣ Fetch driver (optional but safe)
            driver = await DriverMethod(Driver).get_driver_by_id(db, driver_id)
            if not driver:
                return self.response(
                    status.HTTP_404_NOT_FOUND,
                    ErrorMessage.driverNotFound
                )

            ride.status = RideStatusEnum.REACHED.value
            db.add(ride)
            await db.commit()

            data = jsonable_encoder(driver)
            data["driver_status"] = constant.STATUS_THREE

            return self.response(
                status.HTTP_200_OK,
                InfoMessage.driverArrived,  # You might want a different message for 'reached'
                data=data,
            )
        except Exception:
            return self.response(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                ErrorMessage.generalTryAgain,
            )
