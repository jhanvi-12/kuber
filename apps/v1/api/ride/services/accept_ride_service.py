"""This module is responsible to maintain the ride acceptance service logic."""

from datetime import datetime

from fastapi import status
from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession

from apps.v1.api.auth.models.method import UserAuthMethod
from apps.v1.api.auth.models.model import User
from apps.v1.api.base_service import BaseResponseService
from apps.v1.api.driver.models.method import DriverMethod
from apps.v1.api.driver.models.model import Driver
from apps.v1.api.vehicle.models.model import Vehicle
from apps.v1.api.ride.models.attribute import RideStatusEnum
from apps.v1.api.ride.models.model import Ride
from apps.v1.api.ride.serializer import RideResponse
from apps.v1.api.ride.services.socket_emitter import RideSocketEmitter
from config import aws_config
from config.redis_config import redis_client
from core.utils import constant_variable as constant
from core.utils.message_variable import *


class RideAcceptService(BaseResponseService):
    """This class is used to define the ride acceptance service methods."""

    async def ride_accepted_service(self, db: AsyncSession, ride_request_id: str, current_user):
        """This method is used to update the ride status when driver accept the ride.

        Args:
            db (AsyncSession): DB session
            ride_id (int): Ride ID
            driver_id (int): Driver ID.
        """
        try:
            driver_id = current_user["user_id"]
            driver_data = await DriverMethod(Driver).get_driver_by_id(db, driver_id)
            if not driver_data:
                return self.response(
                    status.HTTP_400_BAD_REQUEST, ErrorMessage.driverNotFound
                )
            redis_key = f"ride:search:{ride_request_id}"

            # Fetch ride request
            ride_req = await redis_client.hgetall(redis_key)
            if not ride_req:
                return self.response(
                    status.HTTP_400_BAD_REQUEST, ErrorMessage.rideNotFound
                )

            if ride_req.get("status") != "Searching":
                return self.response(
                    status.HTTP_400_BAD_REQUEST, ErrorMessage.rideNotAvailable
                )

            # Atomic lock (only one driver wins)
            locked = await redis_client.set(
                f"ride:lock:{ride_request_id}",
                driver_id,
                nx=True,
                ex=1200
            )

            if not locked:
                return self.response(
                    status.HTTP_400_BAD_REQUEST, ErrorMessage.rideAlreadyAccepted
                )

            # Create Ride in DB NOW
            ride = Ride(
                user_id=int(ride_req["user_id"]),
                driver_id=driver_id,
                pickup_latitude=float(ride_req["pickup_latitude"]),
                pickup_longitude=float(ride_req["pickup_longitude"]),
                pickup_address=ride_req["pickup_address"],
                destination_latitude=float(ride_req["destination_latitude"]),
                destination_longitude=float(ride_req["destination_longitude"]),
                destination_address=ride_req["destination_address"],
                ride_type=ride_req["ride_type"],
                ride_fare=float(ride_req["ride_fare"]),
                status=RideStatusEnum.ACCEPTED.value,
                ride_date=datetime.now(),
            )

            db.add(ride)
            await db.commit()
            await db.refresh(ride)

            vehicle_data = await UserAuthMethod(Vehicle).find_by_driver_id(db, driver_id)
            if not vehicle_data:
                return self.response(
                    status.HTTP_400_BAD_REQUEST, ErrorMessage.vehicleNotFound
                )
            user_data = await UserAuthMethod(User).find_by_id(db, int(ride_req["user_id"]))
            if not user_data:
                return self.response(
                    status.HTTP_400_BAD_REQUEST, ErrorMessage.rideCancelled
                )
            # Update Redis state
            await redis_client.hmset(
                redis_key,
                mapping={
                    "status": RideStatusEnum.ACCEPTED.value,
                    "driver_id": driver_id,
                    "ride_id": ride.id
                }
            )

            # Emit socket event
            data = jsonable_encoder(driver_data)
            data["plate_number"] = vehicle_data.plate_number
            result = RideResponse().dump(data)
            # Emitting the book_ride_status event with accepted status
            await RideSocketEmitter.book_ride_status(
                ride_status=RideStatusEnum.ACCEPTED.value,
                ride_request_id=ride_request_id,
                ride_id=ride.id,
                driver_data=result
            )

            response = jsonable_encoder(user_data)
            response.pop("device_token")
            response.pop("password")
            response["profile_image"] = (
                f"{aws_config.AWS_BASE_URL}{response["profile_image"]}"
                if response["profile_image"] is not None
                else None
            )
            response["ride_fare"] = ride.ride_fare
            return self.response(status.HTTP_200_OK, InfoMessage.rideAcceptedSuccessfully, response)

        except Exception:
            await db.rollback()
            return self.response(
                status.HTTP_400_BAD_REQUEST, ErrorMessage.generalTryAgain
            )

    async def get_complete_ride_service(self, db: AsyncSession, ride_id: int, current_user: dict):
        """Method to set the status of ride as completed by driver and emit the ride_completed event"""
        try:
            driver_id = current_user["user_id"]
            driver_obj = await DriverMethod(Driver).get_driver_by_id(db, driver_id)
            if not driver_obj:
                return self.response(
                    status.HTTP_400_BAD_REQUEST, ErrorMessage.driverNotFound
                )

            ride_obj = await DriverMethod(Ride).get_ride_by_driver(db, driver_id, ride_id)
            if not ride_obj:
                return self.response(
                    status.HTTP_400_BAD_REQUEST, ErrorMessage.rideNotFound
                )

            user_obj = await UserAuthMethod(User).find_by_id(db, ride_obj.user_id)

            ride_obj.status = RideStatusEnum.COMPLETED.value

            data = jsonable_encoder(user_obj)
            data.pop("password")
            data["profile_image"] = (
                f"{aws_config.AWS_BASE_URL}{data["profile_image"]}"
                if data["profile_image"] else constant.STATUS_NULL
            )
            data["ride_fare"] = ride_obj.ride_fare
            data["ride_type"] = ride_obj.ride_type

            # Emit the Ride completed event.
            await RideSocketEmitter.ride_completed(
                ride_id, data
            )

            db.add(ride_obj)
            await db.commit()
            return self.response(
                status.HTTP_200_OK, InfoMessage.rideCompletedSuccess, data
            )

        except Exception:
            return self.response(
                status.HTTP_400_BAD_REQUEST, ErrorMessage.generalTryAgain
            )

    async def fetch_ride_and_driver(self, db: AsyncSession, ride_id: int, driver_id: int):
        """
        Fetch both ride and driver objects.

        Returns:
            tuple: (ride, driver)
        """
        ride = await DriverMethod(Ride).get_driver_by_id(db, ride_id)
        driver = await DriverMethod(Driver).get_driver_by_id(db, driver_id)
        return ride, driver

    def prepare_response_data(self, ride, driver):
        """
        Prepare response data after encoding and filtering sensitive info.

        Returns:
            dict: response data
        """
        ride_obj = jsonable_encoder(ride)
        driver_obj = jsonable_encoder(driver)
        driver_obj["profile_image"] = (
            f"{aws_config.AWS_BASE_URL}{driver.profile_image}"
            if driver.profile_image else constant.STATUS_NULL
        )
        driver_obj.pop("password", None)  # Remove sensitive info safely
        return {"ride": ride_obj, "driver": driver_obj}

    async def get_verified_user_by_email(self, db: AsyncSession, body: dict):
        """ Fetch ride and driver details by ride_id and driver_id.
        Args:
            db (AsyncSession): The database session.
            body (dict): The request body containing ride and driver IDs.
        Returns:
            StandardResponse: The response object with status and message.
        """
        try:
            ride_id = body.get("ride_id")
            driver_id = body.get("driver_id")

            ride, driver = await self.fetch_ride_and_driver(db, ride_id, driver_id)

            if not ride or not driver:
                return self.response(
                    status.HTTP_404_NOT_FOUND,
                    ErrorMessage.rideOrDriverNotFound,
                )

            data = self.prepare_response_data(ride, driver)

            return self.response(
                status.HTTP_200_OK,
                InfoMessage.rideAndDriverFound,
                data=data,
            )
        except Exception:
            return self.response(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                ErrorMessage.generalTryAgain,
            )

    async def user_start_ride_service(self, current_user, db: AsyncSession, ride_id: int):
        """ Accept a ride request by user.

        Args:
            db (AsyncSession): The database session.
            ride_id (int): The ride ID to start.

        Returns:
            StandardResponse: The response object with status and message.
        """
        try:
            driver_id = current_user.get("user_id")
            ride, driver = await self.fetch_ride_and_driver(db, ride_id, driver_id)

            if not ride or not driver:
                return self.response(
                    status.HTTP_404_NOT_FOUND,
                    ErrorMessage.rideOrDriverNotFound,
                )

            ride.status = RideStatusEnum.STARTED.value
            ride.driver_id = driver.id
            db.add(ride)
            await db.commit()

            data = RideResponse().dump(jsonable_encoder(ride))

            return self.response(
                status.HTTP_200_OK,
                InfoMessage.rideStarted,
                data=data,
            )
        except Exception:
            return self.response(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                ErrorMessage.generalTryAgain,
            )
