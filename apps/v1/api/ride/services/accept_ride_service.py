"""This module is responsible to maintain the ride acceptance service logic."""

from datetime import datetime

from fastapi import status
from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession
from apps.v1.api.driver.services.driver_firebase_notification import \
    DriverFirebaseNotification
from apps.v1.api.auth.models.method import UserAuthMethod
from apps.v1.api.auth.models.model import User
from apps.v1.api.base_service import BaseResponseService
from apps.v1.api.driver.models.method import DriverMethod
from apps.v1.api.driver.models.model import Driver
from apps.v1.api.vehicle.models.model import Vehicle
from apps.v1.api.ride.models.attribute import RideStatusEnum
from apps.v1.api.ride.models.model import Ride
from apps.v1.api.ride.serializer import RideResponse
from apps.v1.api.ride.services.book_ride_service import BookRideService
from apps.v1.api.ride.services.socket_emitter import RideSocketEmitter
from config import aws_config
from config.redis_config import redis_client
from core.redis_repo import RedisDriverRepo, RIDE_SEARCH_TTL
from core.utils import constant_variable as constant
from core.utils.message_variable import *
from apps.v1.api.driver.services.driver_search_service import DriverSearchService


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

            if ride_req.get("status") != "-1":
                return self.response(
                    status.HTTP_400_BAD_REQUEST, ErrorMessage.rideNotAvailable
                )

            if await RedisDriverRepo.is_driver_busy(driver_id):
                return self.response(
                    status.HTTP_400_BAD_REQUEST, ErrorMessage.driverOnActiveRide
                )

            active_ride = await UserAuthMethod(Ride).find_active_ride_by_driver_id(
                db, driver_id
            )
            if active_ride:
                return self.response(
                    status.HTTP_400_BAD_REQUEST, ErrorMessage.driverOnActiveRide
                )

            # Atomic lock (only one driver wins)
            locked = await redis_client.set(
                f"ride:lock:{ride_request_id}",
                driver_id,
                nx=True,
                ex=120
            )

            if not locked:
                return self.response(
                    status.HTTP_400_BAD_REQUEST, ErrorMessage.rideAlreadyAccepted
                )

            # Create Ride in DB NOW
            ride = Ride(
                ride_uuid=self.generate_ride_id(),
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
                discount_fare=float(ride_req.get("discount_fare", 0.0)),
                total_fare=float(ride_req.get("total_fare")),
                distance=float(ride_req.get("distance", 0.0)),
                duration=float(ride_req.get("duration", 0.0)),
                coupon_code=ride_req.get("coupon_code"),
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
                {
                    "status": str(RideStatusEnum.ACCEPTED.value),
                    "driver_id": str(driver_id),
                    "ride_id": str(ride.id),
                },
            )
            search_ttl = await redis_client.ttl(redis_key)
            mapping_ttl = (
                search_ttl
                if isinstance(search_ttl, int) and search_ttl > 0
                else RIDE_SEARCH_TTL
            )
            await redis_client.set(
                f"ride:db:{ride.id}", ride_request_id, ex=mapping_ttl
            )

            driver_data.is_available = constant.STATUS_FALSE
            db.add(driver_data)
            await db.commit()

            await RedisDriverRepo.mark_driver_busy(
                driver_id=driver_id,
                ride_id=ride.id,
                ride_type=vehicle_data.ride_type,
            )
            await RedisDriverRepo.set_driver_tracking(
                driver_id=driver_id,
                user_id=ride.user_id,
                ride_id=ride.id,
                ride_request_id=ride_request_id,
            )

            # Emit socket event
            data = jsonable_encoder(driver_data)
            data["plate_number"] = vehicle_data.plate_number
            data["make"] = vehicle_data.make
            data["vehicle_type"] = vehicle_data.vehicle_type

            result = RideResponse().dump(data)

            body_msg = InfoMessage.driverHeading
            title_msg = InfoMessage.reqAccepted
            driver_lat, driver_lng = await RedisDriverRepo.get_driver_location(
                driver_id, vehicle_data.ride_type
            )
            if (driver_lat is None or driver_lng is None) and ride_req.get("ride_type"):
                driver_lat, driver_lng = await RedisDriverRepo.get_driver_location(
                    driver_id, ride_req["ride_type"]
                )
            if driver_lat is None or driver_lng is None:
                driver_lat = driver_data.latitude
                driver_lng = driver_data.longitude

            if driver_lat is not None and driver_lng is not None:
                driver_pickup_distance = BookRideService().calculate_distance(
                    float(ride_req["pickup_latitude"]),
                    float(ride_req["pickup_longitude"]),
                    float(driver_lat),
                    float(driver_lng),
                )
                if (
                    constant.ACCEPT_NEARBY_MIN_KM
                    <= driver_pickup_distance
                    <= constant.ACCEPT_NEARBY_MAX_KM
                ):
                    body_msg = InfoMessage.driverNearby
                    title_msg = InfoMessage.rideNearby


            await RideSocketEmitter.book_ride_status(
                ride_status=RideStatusEnum.ACCEPTED.value,
                ride_request_id=ride_request_id,
                ride_id=ride.id,
                driver_data=result,
                user_id=ride.user_id,
                ride_uuid=ride.ride_uuid,
            )
            try:
                serialized_payload = DriverSearchService.serialize_user_data({"status": RideStatusEnum.ACCEPTED.value, "ride_request_id": ride_request_id, "ride_id": ride.id, "driver_data": result, "user_id": ride.user_id, "ride_uuid": ride.ride_uuid})
                await DriverFirebaseNotification().send_notification_to_drivers(
                    user_data.device_token,
                    title_msg,
                    body_msg,
                    serialized_payload
                )
                print(f" Notification sent successfully to user {user_data.id}")

            except Exception as e:
                print(
                    f" Failed to send notification to driver {driver_id}: {str(e)}",
                    exc_info=True
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
            response["ride_id"] = ride.id
            response["ride_uuid"] = ride.ride_uuid
            response["status"] = ride.status
            return self.response(status.HTTP_200_OK, InfoMessage.rideAcceptedSuccessfully, response)

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
