"""This module is used to emit the socket events by API services."""

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
    async def ride_accepted(ride_id, driver_data):
        """This event is emitted when driver accpeted the ride."""
        await sio.emit(
            "ride_accepted",
            {
                "ride_id": ride_id,
                "driver": driver_data
            },
            room=f"ride:{ride_id}"
        )

    @staticmethod
    async def no_driver_found(ride_id):
        """This method is used when no drivers are found for the ride."""
        print("👥 ROOM MEMBERS:", sio.manager.rooms)
        await sio.emit(
            "no_driver_found",
            {
                "ride_id": ride_id,
                "title": "Oops! No pilot found",
                "message": "Please try again later"
            },
            room=f"ride:{ride_id}"
        )
