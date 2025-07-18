"""This module is responsible to maintain the ride cancellation service logic."""

from fastapi import status
from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession

from apps.v1.api.base_service import BaseResponseService
from apps.v1.api.driver.models.method import DriverMethod
from apps.v1.api.driver.models.model import Driver
from apps.v1.api.ride.models.attribute import RideStatusEnum
from apps.v1.api.ride.models.model import Ride
from config import aws_config
from core.utils import constant_variable as constant
from core.utils.message_variable import *


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