"""Thism module is used to update the driver status."""

from fastapi import status
from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession

from apps.v1.api.auth.models.method import UserAuthMethod
from apps.v1.api.base_service import BaseResponseService
from apps.v1.api.driver.models.model import Driver
from core.utils import constant_variable as constant
from core.utils.message_variable import *
from apps.v1.api.vehicle.models.model import Vehicle
from core.redis_repo import RedisDriverRepo


class UpdateDriverStatusService(BaseResponseService):
    """This class is used to update the driver status."""

    async def update_driver_status_service(
        self, current_user, db: AsyncSession, body
    ):
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
            driver_obj = await UserAuthMethod(Driver).find_by_id(db, driver_id)
            if not driver_obj:
                return self.response(
                    status.HTTP_404_NOT_FOUND, ErrorMessage.driverNotFound
                )
            # Checking that driver uploaded the required vehicle details or not, then able to make it online.
            # TODO :
            driver_obj.is_available = (
                constant.STATUS_ONE
                if body.get("status") == constant.STATUS_ONE
                else constant.STATUS_ZERO
            )

            driver_obj.latitude = body.get("latitude") if body.get("latitude") is not None else None
            driver_obj.longitude = body.get("longitude") if body.get("longitude") is not None else None
            vehicle_obj = await UserAuthMethod(Vehicle).find_by_driver_id(db, driver_id)

            data = {"is_available": driver_obj.is_available}
            db.add(driver_obj)
            await db.commit()

            # Updating the redis with driver latest lat, lng along with device_token.
            RedisDriverRepo.set_available(driver_id, driver_obj.latitude, driver_obj.longitude, vehicle_obj.ride_type, driver_obj.device_token)
            return self.response(
                status.HTTP_200_OK, InfoMessage.driverStatusUpdated, data
            )

        except Exception:
            return self.response(
                status.HTTP_500_INTERNAL_SERVER_ERROR, ErrorMessage.generalTryAgain
            )
