"""This module is used to fetch the ride related all details for the driver and customer."""

from fastapi import status
from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession

from apps.v1.api.auth.models.method import UserAuthMethod
from apps.v1.api.auth.models.model import User
from apps.v1.api.base_service import BaseResponseService
from apps.v1.api.driver.models.method import DriverMethod
from apps.v1.api.driver.models.model import Driver
from apps.v1.api.ride.models.attribute import RideStatusEnum
from apps.v1.api.ride.models.model import Ride
from apps.v1.api.ride.serializer import RideResponse
from apps.v1.api.ride.services.socket_emitter import RideSocketEmitter
from apps.v1.api.vehicle.models.model import Vehicle
from config import aws_config
from core.utils.message_variable import *


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

    async def driver_reached_service(
        self, db: AsyncSession, current_user: dict, ride_id: int
    ):
        """
        Update the ride status when the driver reaches the pickup location.
        Args:
            db (AsyncSession): The database session.
            body (dict): The request body containing ride details.
            Returns:
            StandardResponse: The response object with status and message.
        """
        try:
            driver_id = current_user["user_id"]
            ride = await UserAuthMethod(Ride).find_by_ride_id_status(
                db, ride_id, RideStatusEnum.ACCEPTED.value
            )
            if not ride:
                return self.response(
                    status.HTTP_404_NOT_FOUND, ErrorMessage.rideNotFound
                )

            # Validate driver assignment (MOST IMPORTANT)
            if ride.driver_id != driver_id:
                return self.response(
                    status.HTTP_403_FORBIDDEN, ErrorMessage.driverNotAssignedToRide
                )

            # Fetch driver (optional but safe)
            driver = await DriverMethod(Driver).get_driver_by_id(db, driver_id)
            if not driver:
                return self.response(
                    status.HTTP_404_NOT_FOUND, ErrorMessage.driverNotFound
                )

            ride.status = RideStatusEnum.REACHED.value
            db.add(ride)
            await db.commit()

            vehicle_data = await UserAuthMethod(Vehicle).find_by_driver_id(db, driver_id)
            if not vehicle_data:
                return self.response(
                    status.HTTP_400_BAD_REQUEST, ErrorMessage.vehicleNotFound
                )
            # emit the book_ride_status api to update the reached status
            response = jsonable_encoder(driver)
            response["plate_number"] = vehicle_data.plate_number
            data = RideResponse().dump(response)

            await RideSocketEmitter.book_ride_status(
                ride_status=RideStatusEnum.REACHED.value,
                ride_request_id=None,
                ride_id=ride.id,
                driver_data=data,
            )
            return self.response(
                status.HTTP_200_OK,
                InfoMessage.driverArrived,
                data=data,
            )
        except Exception:
            return self.response(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                ErrorMessage.generalTryAgain,
            )
