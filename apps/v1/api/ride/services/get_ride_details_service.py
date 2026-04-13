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
from apps.v1.api.ride.serializer import (CustomerRidesResSchema,
                                         DriverRidesResponseSchema,
                                         RideResponse)
from apps.v1.api.ride.services.socket_emitter import RideSocketEmitter
from apps.v1.api.vehicle.models.model import Vehicle
from config import aws_config
from core.utils import constant_variable as constant
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

    async def update_ride_status_service(
        self, db: AsyncSession, current_user: dict, body: dict
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
            ride_id = body.get("ride_id")
            ride_status = body.get("status")
            ride = await UserAuthMethod(Ride).find_by_ride_id_status(
                db, ride_id, RideStatusEnum.ACCEPTED.value
            )
            if not ride:
                return self.response(
                    status.HTTP_404_NOT_FOUND, ErrorMessage.rideNotFoundWithAccept
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

            status_mapping = {
                constant.STATUS_TWO: {
                    "status": RideStatusEnum.REACHED.value,
                    "message": InfoMessage.driverArrived,
                },
                constant.STATUS_THREE: {
                    "status": RideStatusEnum.STARTED.value,
                    "message": InfoMessage.rideStarted,
                },
                constant.STATUS_FOUR: {
                    "status": RideStatusEnum.COMPLETED.value,
                    "message": InfoMessage.thankYou,
                },
            }

            message = InfoMessage.driverStatusUpdated
            update_status = status_mapping.get(ride_status)
            if update_status:
                ride.status = update_status["status"]
                message = update_status["message"]
            db.add(ride)
            await db.commit()

            vehicle_data = await UserAuthMethod(Vehicle).find_by_driver_id(
                db, driver_id
            )
            if not vehicle_data:
                return self.response(
                    status.HTTP_400_BAD_REQUEST, ErrorMessage.vehicleNotFound
                )
            # emit the book_ride_status api to update the reached status
            response = jsonable_encoder(driver)
            response["plate_number"] = vehicle_data.plate_number
            data = RideResponse().dump(response)

            await RideSocketEmitter.book_ride_status(
                ride_status=ride.status,
                ride_request_id=None,
                ride_id=ride.id,
                driver_data=data,
            )
            return self.response(
                status.HTTP_200_OK,
                message,
                data=jsonable_encoder(ride),
            )
        except Exception:
            return self.response(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                ErrorMessage.generalTryAgain,
            )

    async def fetch_user_rides_service(self, db: AsyncSession, current_user: dict):
        """This method is used to fetch the customer rides upto 5 days.

        Args:
            db (AsyncSession): Db Session
            current_user (dict): user for which need to fetch the rides.
        """
        try:
            user_id = current_user.get("user_id")
            user_obj = await UserAuthMethod(User).find_by_id(db, user_id)
            if not user_obj:
                return self.response(
                    status.HTTP_400_BAD_REQUEST, ErrorMessage.userNotFound
                )
            ride_obj = await UserAuthMethod(Ride).find_ride_by_user_id(db, user_id)
            if not ride_obj:
                return self.response(
                    status.HTTP_400_BAD_REQUEST, ErrorMessage.rideNotFound
                )

            data = {
                "rides": ride_obj   # wrap list inside dict
            }
            rides_data = CustomerRidesResSchema().dump(data)
            for ride in rides_data["rides"]:
                vehicle_obj = await DriverMethod(Vehicle).find_vehicle_by_driver_id(db, ride["driver_id"])
                ride["vehicle_image"] = (
                    f"{aws_config.AWS_BASE_URL}{vehicle_obj.vehicle_image}"
                    if vehicle_obj.vehicle_image is not None
                    else constant.STATUS_NULL
                )
            return self.response(status.HTTP_200_OK, InfoMessage.ridesFetched, rides_data)

        except Exception:
            return self.response(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                ErrorMessage.generalTryAgain,
            )

    async def fetch_driver_rides_service(self, db: AsyncSession, current_user: dict):
        """This method is used to fetch the drivers rides upto 5 days.

        Args:
            db (AsyncSession): Db Session
            current_user (dict): user for which need to fetch the rides.
        """
        try:
            driver_id = current_user.get("user_id")
            driver_obj = await UserAuthMethod(Driver).find_by_id(db, driver_id)
            if not driver_obj:
                return self.response(
                    status.HTTP_400_BAD_REQUEST, ErrorMessage.driverNotFound
                )
            ride_obj = await UserAuthMethod(Ride).find_ride_by_driver_id(db, driver_id)
            if not ride_obj:
                return self.response(
                    status.HTTP_400_BAD_REQUEST, ErrorMessage.rideNotFound
                )

            serialized_data = DriverRidesResponseSchema().dump(ride_obj)
            serialized_data["profile_image"] = (
                f"{aws_config.AWS_BASE_URL}{driver_obj.profile_image}"
                if driver_obj.profile_image
                else constant.STATUS_NULL
            )
            return self.response(
                status.HTTP_200_OK, InfoMessage.ridesFetched, serialized_data
            )

        except Exception:
            return self.response(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                ErrorMessage.generalTryAgain,
            )
