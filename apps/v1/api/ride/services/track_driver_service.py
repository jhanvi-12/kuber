"""This module is responsible to track the driver live location."""

from fastapi import status
from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession

from apps.v1.api.base_service import BaseResponseService
from apps.v1.api.driver.models.method import DriverMethod
from apps.v1.api.driver.models.model import Driver
from apps.v1.api.ride.models.attribute import RideStatusEnum
from apps.v1.api.ride.models.model import Ride
from config import aws_config
from apps.v1.api.auth.models.model import User
from core.utils import constant_variable as constant
from core.utils.message_variable import *
from apps.v1.api.ride.services.book_ride_service import BookRideService
from apps.v1.api.ride.serializer import RideResponse

class TrackRideService(BaseResponseService):
    """This class is used to define the driver tracking of the user ride."""

    async def fetch_ride_and_driver(self, db: AsyncSession, ride_id: int, driver_id: int):
        """
        Fetch both ride and driver objects.

        Returns:
            tuple: (ride, driver)
        """
        ride = await DriverMethod(Ride).get_driver_by_id(db, ride_id)
        driver = await DriverMethod(Driver).get_driver_by_id(db, driver_id)
        return ride, driver

    async def user_track_driver_service(
        self, current_user, db: AsyncSession, body: dict
    ):
        """
        Track the driver live location.

        Args:
            db (AsyncSession): The database session.
            body (dict): The request body containing ride details.

        Returns:
            StandardResponse: The response object with status and message.
        """
        try:
            ride_id = body.get("ride_id")
            driver_id = body.get("driver_id")
            new_status = body.get("ride_status")

            user = await DriverMethod(User).get_driver_by_id(db, current_user.get("id"))
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

            # Validate: ride assignment logic TODO: update it
            if ride.status == "Booked":
                # Ride still unassigned
                if new_status != RideStatusEnum.ACCEPTED.value:
                    return self.response(status.HTTP_400_BAD_REQUEST, ErrorMessage.invalidRideStatus)

                if ride.driver_id and ride.driver_id != driver_id:
                    return self.response(status.HTTP_400_BAD_REQUEST, ErrorMessage.rideAlreadyAssigned)

                # First driver accepts
                ride.driver_id = driver_id
                ride.status = RideStatusEnum.ACCEPTED.value

            else:
                # Ride already assigned
                if ride.driver_id != driver_id:
                    return self.response(status.HTTP_403_FORBIDDEN, "You are not authorized for this ride.")

                ride.status = new_status

            # Check the driver distance with user distance
            ride_distance = BookRideService().calculate_distance(
                ride.source_latitude,
                ride.source_longitude,
                driver.latitude,
                driver.longitude,
            )

            print("ride", ride.source_latitude, ride.source_longitude)
            print("driver", driver.latitude, driver.longitude, ride_distance)
            if ride_distance > constant.MAX_DISTANCE:
                driver_status = constant.STATUS_ONE
            elif constant.MIN_DISTANCE < ride_distance <= constant.MAX_DISTANCE:
                driver_status = constant.STATUS_TWO
            else:
                driver_status = constant.STATUS_THREE

            # Save the live latitude and longitude of the driver
            driver.latitude = body.get("latitude")
            driver.longitude = body.get("longitude")
            db.add_all([ride, driver])
            await db.commit()

            # Prepare response data
            response_data = RideResponse().dump(jsonable_encoder(ride))
            response_data["driver_latitude"] = driver.latitude
            response_data["driver_longitude"] = driver.longitude
            response_data["driver_status"] = driver_status

            return self.response(
                status.HTTP_200_OK,
                InfoMessage.driverTrackingSuccess,
                response_data,
            )
        except Exception as e:
            return self.response(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                str(e),
            )
