"""This module is used to emit the socket events by API services."""

import json

from config.redis_config import redis_client
from core.utils.message_variable import *
from socket_server import sio


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
    async def ride_accepted(ride_request_id, ride_id, driver_data):
        """This event is emitted when driver accpeted the ride."""
        await redis_client.publish(
            "socket:events",
            json.dumps({
            "event": "ride_accepted",
            "ride_id": ride_id,
            "data": {
                "status": InfoMessage.reqAccepted,
                "message": InfoMessage.driverHeading,
                "ride_request_id": ride_request_id,
                "ride_id": ride_id,
                "data": driver_data
            }
            })
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
        await redis_client.publish(
            "socket:events",
            json.dumps({
                "event": "no_driver_found",
                "ride_id": ride_id,
                "title": ErrorMessage.noDriverFound,
                "message": ErrorMessage.tryAgain
            })
        )

