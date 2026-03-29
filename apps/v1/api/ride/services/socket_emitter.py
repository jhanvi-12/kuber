"""This module is used to emit the socket events by API services."""

import json
from datetime import datetime
from config.redis_config import redis_client
from core.utils.message_variable import *
from socket_server import sio
from apps.v1.api.ride.models.attribute import RideStatusEnum


class RideSocketEmitter:
    """This class emits all socket events which are used in ride booking system."""

    @staticmethod
    async def ride_searching(ride_id):
        """This method is used for the ride searching"""
        await sio.emit(
            "ride_searching",
            {"ride_id": ride_id},
            room=f"ride:{ride_id}"
        )

    @staticmethod
    async def book_ride_status(
        ride_status: int,
        ride_request_id: str = None,
        ride_id: str = None,
        driver_data: dict = None,
        extra_data: dict = None
    ):
        """
        Unified socket event for all ride booking statuses.
        Emits a single event: 'book_ride_status'
        """

        # Centralized status configuration
        status_config = {
            RideStatusEnum.ACCEPTED.value: {
                "status": RideStatusEnum.ACCEPTED.value,
                "title": InfoMessage.reqAccepted,
                "message": InfoMessage.driverHeading,
                "include_driver": True
            },
            RideStatusEnum.FAILED.value: {
                "status": RideStatusEnum.FAILED.value,
                "title": ErrorMessage.noDriverFound,
                "message": ErrorMessage.tryAgain,
                "include_driver": False
            },
            RideStatusEnum.STARTED.value: {
                "status": RideStatusEnum.STARTED.value,
                "title": InfoMessage.rideStarted,
                "message": InfoMessage.enjoyRide,
                "include_driver": False
            },
            RideStatusEnum.COMPLETED.value: {
                "status": RideStatusEnum.COMPLETED.value,
                "title": InfoMessage.rideCompletedSuccess,
                "message": InfoMessage.thankYou,
                "include_driver": False
            },
            RideStatusEnum.CANCELLED.value: {
                "status": RideStatusEnum.CANCELLED.value,
                "title": InfoMessage.rideCancelledSuccessfully,
                "message": InfoMessage.cancelledMsg,
                "include_driver": False
            }
        }

        config = status_config.get(ride_status)

        if not config:
            raise ValueError(f"Invalid ride status: {ride_status}")

        # Base response data
        data = {
            "ride_request_id": ride_request_id,
            "ride_id": ride_id,
            "title": config.get("title"),
            "message": config.get("message"),
            "status": config.get("status")
        }

        # Attach driver info only when required
        if config.get("include_driver") and driver_data:
            data["driver"] = driver_data

        # Merge additional dynamic fields
        if extra_data:
            data.update(extra_data)

        # Final socket payload
        payload = {
            "event": "book_ride_status",
            "status": ride_status,
            "timestamp": datetime.now().isoformat(),
            "data": data
        }

        await redis_client.publish(
            "socket:events",
            json.dumps(payload)
        )

    @staticmethod
    async def ride_completed(ride_id, data):
        """This method is used to emit when ride is completed by driver."""
        await redis_client.publish(
            "socket:events",
            json.dumps({
            "event": "ride_completed",
            "ride_id": ride_id,
            "data": {
                "message": InfoMessage.rideCompletedSuccess,
                "ride_id": ride_id,
                "data": data
            }
            })
        )

    @staticmethod
    async def no_driver_found(ride_id):
        """This method is used when no drivers are found for the ride."""
        payload = {
            "event": "no_driver_found",
            #"room": f"ride:req:{ride_id}",  # IMPORTANT
            "data": {
                "ride_id": ride_id,
                "title": ErrorMessage.noDriverFound,
                "message": ErrorMessage.tryAgain
            }
        }

        await redis_client.publish(
            "socket:events",
            json.dumps(payload)
        )
