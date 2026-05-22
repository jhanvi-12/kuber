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
            ride = await DriverMethod(Ride).get_driver_by_id(db, ride_id)

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
            if update_status == RideStatusEnum.CANCELLED.value:
                if ride.coupon_code == constant.COUPON_WELCOME50:
                    ride.is_welcome = constant.STATUS_TRUE
                    ride.is_commuter = constant.STATUS_FALSE

                elif ride.coupon_code == constant.COUPON_COMMUTE25:
                    ride.is_commuter = constant.STATUS_TRUE
                    ride.is_welcome = constant.STATUS_FALSE

                else:
                    ride.is_welcome = constant.STATUS_FALSE
                    ride.is_commuter = constant.STATUS_FALSE
    
            ride.status = RideStatusEnum.CANCELLED.value
            ride.cancellation_reason = reason
            ride.cancellation_description = description
            ride.cancelled_by = user_type  # should be "user" or "driver"

            db.add(ride)
            await db.commit()
            await db.refresh(ride)

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
                mapping={
                    "status": "Cancelled",
                    "ride_request_id": ride_request_id
                }
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