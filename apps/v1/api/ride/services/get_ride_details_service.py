"""This module is used to fetch the ride related all details for the driver and customer."""

from fastapi import status
from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from apps.v1.api.auth.models.method import UserAuthMethod
from apps.v1.api.auth.models.model import User
from apps.v1.api.base_service import BaseResponseService
from apps.v1.api.driver.models.method import DriverMethod
from apps.v1.api.driver.models.model import Driver
from apps.v1.api.ride.models.attribute import RideStatusEnum
from apps.v1.api.ride.models.model import Ride
from apps.v1.api.ride.serializer import (
    CustomerRidesResSchema,
    DriverRidesResponseSchema,
    RideResponse,
)
from apps.v1.api.ride.services.socket_emitter import RideSocketEmitter
from apps.v1.api.vehicle.models.model import Vehicle
from config import aws_config
from core.utils import constant_variable as constant
from core.utils.message_variable import *
from core.utils.db_method import DataBaseMethod


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
            if update_status["status"] == RideStatusEnum.COMPLETED.value:
                if ride.coupon_code == constant.COUPON_KUBERSAVER:
                    if ride.ride_type == constant.CITY_RIDE:
                        ride.is_city = constant.STATUS_TRUE
                        ride.is_comfort = constant.STATUS_FALSE
                    elif ride.ride_type == constant.COMFORT_RIDE:
                        ride.is_comfort = constant.STATUS_TRUE
                        ride.is_city = constant.STATUS_FALSE
                    else:
                        ride.is_city = constant.STATUS_FALSE
                        ride.is_comfort = constant.STATUS_FALSE
                    # TODO : Handle other coupon types if needed in future
                    # ride.is_welcome = constant.STATUS_FALSE
                    # ride.is_commuter = constant.STATUS_FALSE
                # elif ride.coupon_code == constant.COUPON_WELCOME50:
                #     ride.is_welcome = constant.STATUS_TRUE
                #     ride.is_city = constant.STATUS_FALSE
                #     ride.is_comfort = constant.STATUS_FALSE
                # elif ride.coupon_code == constant.COUPON_COMMUTE25:
                #     ride.is_commuter = constant.STATUS_TRUE
                #     ride.is_city = constant.STATUS_FALSE
                #     ride.is_comfort = constant.STATUS_FALSE
                else:
                    # TODO : Handle case when no coupon code is applied if needed in future
                    # ride.is_welcome = constant.STATUS_FALSE
                    # ride.is_commuter = constant.STATUS_FALSE
                    ride.is_city = constant.STATUS_FALSE
                    ride.is_comfort = constant.STATUS_FALSE
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
                ride_status=update_status["status"],
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

    async def fetch_user_rides_service(
        self, db: AsyncSession, current_user: dict, body: dict
    ):
        """
        Fetch completed and cancelled rides for a customer within date range.

        Args:
            db: Database session
            current_user: Authenticated user dict
            body: Request body with start_date and end_date
        """
        try:
            # --- Input validation ---
            user_id = current_user.get("user_id")
            if not user_id:
                return self.response(status.HTTP_401_UNAUTHORIZED, ErrorMessage.userNotFound)

            start_date = body.get("start_date")
            end_date = body.get("end_date")

            if not start_date or not end_date:
                return self.response(
                    status.HTTP_400_BAD_REQUEST, ErrorMessage.dateRangeRequired
                )

            # Parse and validate dates
            try:
                if isinstance(start_date, str):
                    start_date = datetime.fromisoformat(start_date)
                if isinstance(end_date, str):
                    end_date = datetime.fromisoformat(end_date)
            except (ValueError, TypeError):
                return self.response(
                    status.HTTP_400_BAD_REQUEST, ErrorMessage.invalidDateFormat
                )

            if start_date > end_date:
                return self.response(
                    status.HTTP_400_BAD_REQUEST, ErrorMessage.invalidDateRange
                )

            # --- Fetch user ---
            user_obj = await UserAuthMethod(User).find_by_id(db, user_id)
            if not user_obj:
                return self.response(status.HTTP_404_NOT_FOUND, ErrorMessage.userNotFound)

            # --- Fetch rides ---
            ride_objs = await UserAuthMethod(Ride).find_ride_by_user_id(
                db, user_id, start_date, end_date
            )

            # Empty rides is valid — return empty list, not 400
            if not ride_objs:
                return self.response(
                    status.HTTP_200_OK,
                    InfoMessage.ridesFetched,
                    {"rides": []}
                )

            # --- Serialize rides ---
            rides_data = CustomerRidesResSchema().dump({"rides": ride_objs})

            # --- Enrich each ride with vehicle and driver data ---
            for ride in rides_data.get("rides", []):
                driver_id = ride.get("driver_id")

                # Attach vehicle data
                try:
                    vehicle_obj = await DriverMethod(Vehicle).find_vehicle_by_driver_id(
                        db, driver_id
                    ) if driver_id else None

                    ride["vehicle_name"] = vehicle_obj.make if vehicle_obj else constant.STATUS_NULL
                    ride["plate_number"] = vehicle_obj.plate_number if vehicle_obj else constant.STATUS_NULL
                    ride["vehicle_image"] = (
                        f"{aws_config.AWS_BASE_URL}{vehicle_obj.vehicle_image}"
                        if vehicle_obj and vehicle_obj.vehicle_image
                        else constant.STATUS_NULL
                    )
                except Exception:
                    ride["vehicle_name"] = constant.STATUS_NULL
                    ride["plate_number"] = constant.STATUS_NULL
                    ride["vehicle_image"] = constant.STATUS_NULL

                # Attach driver data
                try:
                    driver_obj = await UserAuthMethod(Driver).find_by_id(
                        db, driver_id
                    ) if driver_id else None

                    ride["driver_data"] = {
                        "full_name": driver_obj.full_name if driver_obj else constant.STATUS_NULL,
                        "mobile": driver_obj.mobile if driver_obj else constant.STATUS_NULL,
                        "profile_image": (
                            f"{aws_config.AWS_BASE_URL}{driver_obj.profile_image}"
                            if driver_obj and driver_obj.profile_image
                            else constant.STATUS_NULL
                        ),
                        "ratings": driver_obj.review if driver_obj else constant.STATUS_NULL,
                    }
                except Exception:
                    ride["driver_data"] = {
                        "full_name": constant.STATUS_NULL,
                        "mobile": constant.STATUS_NULL,
                        "profile_image": constant.STATUS_NULL,
                        "ratings": constant.STATUS_NULL,
                    }

            return self.response(status.HTTP_200_OK, InfoMessage.ridesFetched, rides_data)

        except Exception:
            return self.response(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                ErrorMessage.generalTryAgain,
            )

    async def fetch_driver_rides_service(
        self, db: AsyncSession, current_user: dict, body: dict
    ):
        """This method is used to fetch the drivers rides upto 5 days.

        Args:
            db (AsyncSession): Db Session
            current_user (dict): user for which need to fetch the rides.
        """
        try:
            driver_id = current_user.get("user_id")
            start_date = body.get("start_date")
            end_date = body.get("end_date")
            driver_obj = await UserAuthMethod(Driver).find_by_id(db, driver_id)
            if not driver_obj:
                return self.response(
                    status.HTTP_400_BAD_REQUEST, ErrorMessage.driverNotFound
                )
            ride_obj = await UserAuthMethod(Ride).find_ride_by_driver_id(
                db, driver_id, start_date, end_date
            )
            if not ride_obj:
                return self.response(
                    status.HTTP_400_BAD_REQUEST, ErrorMessage.rideNotFound
                )

            serialized_data = DriverRidesResponseSchema().dump(ride_obj)
            serialized_data["total_earnings"] = await DataBaseMethod(Ride).sum(
                db,
                "ride_fare",
                {
                    "driver_id": driver_id,
                    "status": RideStatusEnum.COMPLETED.value,
                },
            )
            serialized_data["profile_image"] = (
                f"{aws_config.AWS_BASE_URL}{driver_obj.profile_image}"
                if driver_obj.profile_image
                else constant.STATUS_NULL
            )
            for ride in serialized_data["rides"]:
                user_obj = await UserAuthMethod(User).find_by_id(db, ride["user_id"])
                ride["username"] = user_obj.full_name
                ride["profile_image"] = (
                    f"{aws_config.AWS_BASE_URL}{user_obj.profile_image}"
                    if user_obj.profile_image is not None
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
