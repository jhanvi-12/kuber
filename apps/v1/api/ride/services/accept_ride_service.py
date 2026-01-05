"""This module is responsible to maintain the ride acceptance service logic."""

from fastapi import status
from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession

from apps.v1.api.base_service import BaseResponseService
from apps.v1.api.driver.models.method import DriverMethod
from apps.v1.api.driver.models.model import Driver
from apps.v1.api.ride.models.attribute import RideStatusEnum
from apps.v1.api.ride.serializer import RideResponse
from apps.v1.api.ride.models.model import Ride
from config import aws_config
from core.utils import constant_variable as constant
from core.utils.message_variable import *
from apps.v1.api.auth.models.model import User


class RideAcceptService(BaseResponseService):
    """This class is used to define the ride acceptance service methods."""

    async def ride_accepted_service(self, db: AsyncSession, ride_id: int, driver_id: int):
        """This method is used to update the ride status when driver accept the ride.

        Args:
            db (AsyncSession): DB session
            ride_id (int): Ride ID
            driver_id (int): Driver ID.
        """
        try:
            if not await DriverMethod(Driver).get_driver_by_id(db, driver_id):
                return self.response(
                    status.HTTP_400_BAD_REQUEST, ErrorMessage.driverNotFound
                )
            data = await DriverMethod(Ride).get_driver_by_id(db, ride_id)
            if not data:
                return self.response(
                    status.HTTP_400_BAD_REQUEST, ErrorMessage.rideNotFound
                )

            user_data = await DriverMethod(User).get_driver_by_id(db, data.user_id)
            if not user_data:
                return self.response(
                    status.HTTP_400_BAD_REQUEST, ErrorMessage.userNotFound
                )

            # 3️⃣ Allow accept ONLY if finding drivers
            if data.status != RideStatusEnum.FINDING_DRIVERS.value:
                return self.response(
                    status.HTTP_409_CONFLICT,
                    ErrorMessage.rideAlreadyAccepted
                )

            data.driver_id = driver_id
            data.status = RideStatusEnum.ACCEPTED.value
            db.add(data)
            await db.commit()
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
            await db.rollback()
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

    async def user_start_ride_service(self, current_user, db: AsyncSession, body: dict):
        """ Accept a ride request by user.

        Args:
            db (AsyncSession): The database session.
            body (dict): The request body containing ride details.

        Returns:
            StandardResponse: The response object with status and message.
        """
        try:
            ride_id = body.get("ride_id")
            driver_id = body.get("driver_id")
            ride_status = body.get("ride_status")

            user = await DriverMethod(Driver).get_driver_by_id(db, current_user.get("id"))

            if not user:
                return self.response(
                    status.HTTP_404_NOT_FOUND,
                    ErrorMessage.userNotFound,
                )

            ride, driver = await self.fetch_ride_and_driver(db, ride_id, driver_id)

            if not ride or not driver:
                return self.response(
                    status.HTTP_404_NOT_FOUND,
                    ErrorMessage.rideOrDriverNotFound,
                )

            ride.status = ride_status
            ride.driver_id = driver.id
            db.add(ride)
            await db.commit()

            data = RideResponse().dump(jsonable_encoder(ride))

            return self.response(
                status.HTTP_200_OK,
                InfoMessage.rideAcceptedSuccessfully,
                data=data,
            )
        except Exception:
            return self.response(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                ErrorMessage.generalTryAgain,
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
