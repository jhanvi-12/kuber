"""This module is used to emit the socket events by API services."""

import json
import logging
from datetime import datetime

from apps.v1.api.ride.models.attribute import RideStatusEnum
from config import aws_config
from config.redis_config import redis_client, SOCKET_CHANNEL
from core.redis_repo import RedisRideRepo
from core.utils.message_variable import *

LOG = logging.getLogger(__name__)


class RideSocketEmitter:
    """This class emits all socket events which are used in ride booking system."""

    @staticmethod
    def _user_room(user_id: int) -> str:
        return f"user:{user_id}"

    @staticmethod
    def _ride_room(ride_request_id: str) -> str:
        return f"ride:{ride_request_id}"

    @staticmethod
    async def _resolve_user_id(
        ride_request_id: str = None, user_id: int = None
    ) -> int | None:
        if user_id is not None:
            return int(user_id)
        if not ride_request_id:
            return None
        ride_data = await RedisRideRepo.get_ride_data(ride_request_id)
        booking_user_id = ride_data.get("user_id")
        return int(booking_user_id) if booking_user_id else None

    @staticmethod
    async def _publish(event: str, data: dict, room: str = None):
        if not room:
            LOG.warning("Socket emit '%s' skipped: no room specified", event)
            return
        payload = {"event": event, "data": data, "room": room}
        await redis_client.publish(SOCKET_CHANNEL, json.dumps(payload))

    @staticmethod
    async def ride_searching(ride_request_id: str, user_id: int = None):
        """Notify the booking customer that driver search has started."""
        resolved_user_id = await RideSocketEmitter._resolve_user_id(
            ride_request_id, user_id
        )
        if not resolved_user_id:
            LOG.warning(
                "ride_searching skipped: no user_id for ride_request_id=%s",
                ride_request_id,
            )
            return

        await RideSocketEmitter._publish(
            "ride_searching",
            {"ride_request_id": ride_request_id, "ride_id": ride_request_id},
            room=RideSocketEmitter._user_room(resolved_user_id),
        )

    @staticmethod
    async def book_ride_status(
        ride_status: int,
        ride_request_id: str = None,
        ride_id: str = None,
        driver_data: dict = None,
        extra_data: dict = None,
        user_id: int = None,
    ):
        """
        Unified socket event for all ride booking statuses.
        Emits a single event: 'book_ride_status' to user:{booking_user_id} only.
        """
        status_config = {
            RideStatusEnum.ACCEPTED.value: {
                "status": RideStatusEnum.ACCEPTED.value,
                "title": InfoMessage.reqAccepted,
                "message": InfoMessage.driverHeading,
                "include_driver": True,
            },
            RideStatusEnum.REACHED.value: {
                "status": RideStatusEnum.REACHED.value,
                "title": InfoMessage.driverArrived,
                "message": InfoMessage.driverReachedSuccessfully,
                "include_driver": True,
            },
            RideStatusEnum.FAILED.value: {
                "status": RideStatusEnum.FAILED.value,
                "title": ErrorMessage.noDriverFound,
                "message": ErrorMessage.tryAgain,
                "include_driver": False,
            },
            RideStatusEnum.STARTED.value: {
                "status": RideStatusEnum.STARTED.value,
                "title": InfoMessage.rideStarted,
                "message": InfoMessage.enjoyRide,
                "include_driver": False,
            },
            RideStatusEnum.COMPLETED.value: {
                "status": RideStatusEnum.COMPLETED.value,
                "title": InfoMessage.rideCompletedSuccess,
                "message": InfoMessage.thankYou,
                "include_driver": False,
            },
            RideStatusEnum.CANCELLED.value: {
                "status": RideStatusEnum.CANCELLED.value,
                "title": InfoMessage.rideCancelledSuccessfully,
                "message": InfoMessage.cancelledMsg,
                "include_driver": False,
            },
        }

        config = status_config.get(ride_status)
        if not config:
            raise ValueError(f"Invalid ride status: {ride_status}")

        resolved_user_id = await RideSocketEmitter._resolve_user_id(
            ride_request_id, user_id
        )
        if not resolved_user_id:
            LOG.warning(
                "book_ride_status skipped: no user_id for ride_request_id=%s",
                ride_request_id,
            )
            return

        data = {
            "ride_request_id": ride_request_id,
            "ride_id": ride_id,
            "title": config.get("title"),
            "message": config.get("message"),
            "status": config.get("status"),
        }

        if config.get("include_driver") and driver_data:
            driver_data["profile_image"] = (
                f"{aws_config.AWS_BASE_URL}{driver_data['profile_image']}"
                if driver_data["profile_image"] is not None
                else None
            )
            data["driver"] = driver_data

        if extra_data:
            data.update(extra_data)

        await RideSocketEmitter._publish(
            "book_ride_status",
            data,
            room=RideSocketEmitter._user_room(resolved_user_id),
        )

    @staticmethod
    async def ride_completed(ride_id, data, user_id: int = None):
        """Emit when ride is completed by driver scoped to the booking customer."""
        if not user_id:
            LOG.warning("ride_completed skipped: user_id is required")
            return
        await RideSocketEmitter._publish(
            "ride_completed",
            {
                "message": InfoMessage.rideCompletedSuccess,
                "ride_id": ride_id,
                "data": data,
            },
            room=RideSocketEmitter._user_room(user_id),
        )

    @staticmethod
    async def no_driver_found(ride_request_id: str, user_id: int = None):
        """Emit when no drivers are found scoped to the booking customer."""
        resolved_user_id = await RideSocketEmitter._resolve_user_id(
            ride_request_id, user_id
        )
        if not resolved_user_id:
            LOG.warning(
                "no_driver_found skipped: no user_id for ride_request_id=%s",
                ride_request_id,
            )
            return
        await RideSocketEmitter._publish(
            "no_driver_found",
            {
                "ride_request_id": ride_request_id,
                "ride_id": ride_request_id,
                "title": ErrorMessage.noDriverFound,
                "message": ErrorMessage.tryAgain,
            },
            room=RideSocketEmitter._user_room(resolved_user_id),
        )
