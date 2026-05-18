"""Thism module is used to update the driver status."""

from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from apps.v1.api.auth.models.method import UserAuthMethod
from apps.v1.api.base_service import BaseResponseService
from apps.v1.api.driver.models.model import Driver
from apps.v1.api.vehicle.models.model import Vehicle
from core.redis_repo import RedisDriverRepo
from core.utils import constant_variable as constant
from core.utils.message_variable import *


class UpdateDriverStatusService(BaseResponseService):
    """This class is used to update the driver status."""

    async def update_driver_status_service(self, current_user, db: AsyncSession, body):
        """
        Updates the status of a driver.

        Args:
            db (AsyncSession): The database session.
            current_user (int): The ID of the driver.
            body (dict): The driver status body.

        Returns:
            StandardResponse: The response object with status and message.
        """
        try:
            # Update the driver's status
            body = body.dict()
            driver_id = current_user["user_id"]
            is_available = body.get("status") == constant.STATUS_ONE
            lat = body.get("latitude")
            lng = body.get("longitude")

            # Coords are required only when going online
            if is_available and (lat is None or lng is None):
                return self.response(
                    status.HTTP_400_BAD_REQUEST,
                    ErrorMessage.latLngRequired
                )

            driver_obj = await UserAuthMethod(Driver).find_by_id(db, driver_id)
            if not driver_obj:
                return self.response(status.HTTP_404_NOT_FOUND, ErrorMessage.driverNotFound)

            vehicle_obj = await UserAuthMethod(Vehicle).find_by_driver_id(db, driver_id)
            if not vehicle_obj:
                return self.response(status.HTTP_400_BAD_REQUEST, ErrorMessage.vehicleNotFound)

            # Update DB
            driver_obj.is_available = constant.STATUS_ONE if is_available else constant.STATUS_ZERO
            driver_obj.latitude = lat
            driver_obj.longitude = lng
            db.add(driver_obj)
            await db.commit()

            # Sync Redis
            await RedisDriverRepo.update_driver_status(
                driver_id=driver_id,
                ride_type=vehicle_obj.ride_type,
                is_available=is_available,
                lat=lat,
                lng=lng,
                device_token=driver_obj.device_token,
            )

            return self.response(
                status.HTTP_200_OK,
                InfoMessage.driverStatusUpdated,
                {"is_available": driver_obj.is_available}
            )

        except Exception:
            return self.response(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                ErrorMessage.generalTryAgain
            )
