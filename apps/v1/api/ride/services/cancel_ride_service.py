"""This module is responsible to maintain the ride cancellation service logic."""

from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from apps.v1.api.base_service import BaseResponseService
from apps.v1.api.driver.models.method import DriverMethod
from apps.v1.api.ride.models.attribute import RideStatusEnum
from apps.v1.api.ride.models.model import Ride
from core.utils.message_variable import *
from config.redis_config import redis_client
from core.utils import constant_variable as constant
from apps.v1.api.ride.services.socket_emitter import RideSocketEmitter
from apps.v1.api.auth.models.method import UserAuthMethod
from apps.v1.api.driver.services.driver_firebase_notification import \
    DriverFirebaseNotification
from apps.v1.api.auth.models.attribute import UserTypeEnum
from apps.v1.api.auth.models.model import User
from apps.v1.api.driver.models.model import Driver
from apps.v1.api.driver.services.driver_search_service import DriverSearchService
from apps.v1.api.vehicle.models.model import Vehicle
from core.redis_repo import RedisDriverRepo

class UserRideCancelService(BaseResponseService):
    """This class is used to define the ride acceptance service methods."""

    async def user_ride_cancel_service(self, db: AsyncSession, body: dict, current_user):
        """
        Cancel a ride request by user.

        Args:
            db (AsyncSession): The database session.
            body (dict): The request body containing ride details.

        Returns:
            StandardResponse: The response object with status and message.
        """
        try:
            ride_id = body.get("ride_id")
            user_type = body.get("user_type")
            reason = body.get("reason")
            description = body.get("description")

            user = await self.get_current_user_details(db, current_user)
            if not user:
                return self.response(
                    status.HTTP_404_NOT_FOUND,
                    ErrorMessage.userOrDriverNotFound,
                )
            # Fetch the ride and driver details
            ride = await UserAuthMethod(Ride).find_by_id(
                db, ride_id
            )

            if not ride:
                return self.response(
                    status.HTTP_404_NOT_FOUND,
                    ErrorMessage.rideNotFound,
                )

            if ride.status in [RideStatusEnum.COMPLETED.value, RideStatusEnum.CANCELLED.value]:
                return self.response(
                    status.HTTP_400_BAD_REQUEST,
                    ErrorMessage.rideAlreadyCompletedOrCancelled,
                )

            # Update ride status and store cancellation info
            update_status = ride.status
            if update_status != RideStatusEnum.CANCELLED.value:
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
                # elif ride.coupon_code == constant.COUPON_WELCOME50:
                #     ride.is_welcome = constant.STATUS_TRUE
                #     ride.is_commuter = constant.STATUS_FALSE
                #     ride.is_city = constant.STATUS_FALSE
                #     ride.is_comfort = constant.STATUS_FALSE
                # elif ride.coupon_code == constant.COUPON_COMMUTE25:
                #     ride.is_commuter = constant.STATUS_TRUE
                #     ride.is_welcome = constant.STATUS_FALSE
                #     ride.is_city = constant.STATUS_FALSE
                #     ride.is_comfort = constant.STATUS_FALSE
                else:
                    # TODO : Handle case when no coupon code is applied if needed in future
                    # ride.is_welcome = constant.STATUS_FALSE
                    # ride.is_commuter = constant.STATUS_FALSE
                    ride.is_city = constant.STATUS_FALSE
                    ride.is_comfort = constant.STATUS_FALSE

            ride.status = RideStatusEnum.CANCELLED.value
            ride.cancellation_reason = reason
            ride.cancellation_description = description
            ride.cancelled_by = user_type  # should be "user" or "driver"

            db.add(ride)
            await db.commit()
            await db.refresh(ride)

            if ride.driver_id:
                assigned_driver = await UserAuthMethod(Driver).find_by_id(
                    db, ride.driver_id
                )
                vehicle = await UserAuthMethod(Vehicle).find_by_driver_id(
                    db, ride.driver_id
                )
                if assigned_driver and vehicle:
                    lat, lng = await RedisDriverRepo.get_driver_location(
                        ride.driver_id, vehicle.ride_type
                    )
                    if lat is None or lng is None:
                        lat = assigned_driver.latitude
                        lng = assigned_driver.longitude

                    assigned_driver.is_available = constant.STATUS_TRUE
                    if lat is not None and lng is not None:
                        assigned_driver.latitude = lat
                        assigned_driver.longitude = lng
                    db.add(assigned_driver)
                    await db.commit()
                    await RedisDriverRepo.release_driver_busy(
                        driver_id=ride.driver_id,
                        ride_type=vehicle.ride_type,
                        lat=lat,
                        lng=lng,
                        device_token=assigned_driver.device_token,
                    )

            await RideSocketEmitter.book_ride_status(
                ride_status=ride.status,
                ride_request_id=None,
                ride_id=ride.id,
                driver_data=None,
                user_id=ride.user_id,
            )

            try:
                if user.user_type == UserTypeEnum.DRIVER.value:
                    recipient_id = ride.user_id
                    recipient_model = User
                    notification_title = InfoMessage.rideCancelledTitle
                    notification_message = InfoMessage.driverCancelledRide.format(driver_name=user.full_name)
                else:
                    recipient_id = ride.driver_id
                    recipient_model = Driver
                    notification_title = InfoMessage.rideCancelledTitle
                    notification_message = InfoMessage.userCancelledRide.format(user_name=user.full_name)

                recipient = await UserAuthMethod(recipient_model).find_by_id(
                    db,
                    recipient_id
                )

                if recipient and recipient.device_token:
                    serialized_payload = DriverSearchService.serialize_user_data({"status": ride.status})
                    await DriverFirebaseNotification().send_notification_to_drivers(
                        recipient.device_token,
                        notification_message,
                        notification_title,
                        serialized_payload
                    )
                    print(f" Notification sent successfully to user {recipient.id}")

            except Exception as e:
                print(
                    f" Failed to send notification to driver {recipient.id}: {str(e)}",
                    exc_info=True
                )
            return self.response(
                status.HTTP_200_OK,
                InfoMessage.rideCancelledSuccessfully,
                data={"ride_id": ride.id, "status": ride.status},
            )

        except Exception:
            return self.response(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                ErrorMessage.generalTryAgain,
            )

    async def before_book_ride_cancel_service(self, db: AsyncSession, ride_request_id: str, current_user):
        """
        Cancel a ride request by user before ride booking.

        Args:
            db (AsyncSession): The database session.
            body (dict): The request body containing ride details.

        Returns:
            StandardResponse: The response object with status and message.
        """
        try:
            user = await self.get_current_user_details(db, current_user)
            if not user:
                return self.response(
                    status.HTTP_404_NOT_FOUND,
                    ErrorMessage.userOrDriverNotFound,
                )
            redis_key = f"ride:search:{ride_request_id}"

            # Fetch ride request
            ride_req = await redis_client.hgetall(redis_key)
            if not ride_req:
                return self.response(
                    status.HTTP_400_BAD_REQUEST, ErrorMessage.rideNotFound
                )

            # Update Redis state
            await redis_client.hmset(
                redis_key,
                {
                    "status": "Cancelled",
                    "ride_request_id": ride_request_id,
                },
            )

            return self.response(
                status.HTTP_200_OK,
                InfoMessage.beforeRideCancelMsg,
                data={"ride_request_id": ride_request_id, "status": RideStatusEnum.CANCELLED.value},
            )

        except Exception:
            return self.response(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                ErrorMessage.generalTryAgain,
            )