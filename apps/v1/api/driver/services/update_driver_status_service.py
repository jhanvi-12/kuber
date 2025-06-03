"""Thism module is used to update the driver status."""

from fastapi import status
from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession

from apps.v1.api.auth.models.method import UserAuthMethod
from apps.v1.api.base_service import BaseResponseService
from apps.v1.api.driver.models.model import Driver
from core.utils import constant_variable as constant
from core.utils.message_variable import *


class UpdateDriverStatusService(BaseResponseService):
    """This class is used to update the driver status."""

    async def update_driver_status_service(
        self, current_user, db: AsyncSession, driver_status: str
    ):
        """
        Updates the status of a driver.

        Args:
            db (AsyncSession): The database session.
            driver_id (int): The ID of the driver.
            status (str): The new status of the driver.

        Returns:
            StandardResponse: The response object with status and message.
        """
        try:
            # Update the driver's status
            driver_id = current_user["user_id"]
            driver_obj = await UserAuthMethod(Driver).find_by_id(db, driver_id)
            if not driver_obj:
                return self.response(
                    status.HTTP_404_NOT_FOUND, ErrorMessage.driverNotFound
                )

            driver_obj.is_active = (
                constant.STATUS_TRUE
                if driver_status == constant.STATUS_ONE
                else constant.STATUS_FALSE
            )

            data = {"is_active": driver_obj.is_active}
            db.add(driver_obj)
            await db.commit()
            return self.response(
                status.HTTP_200_OK, InfoMessage.driverStatusUpdated, data
            )

        except Exception:
            return self.response(
                status.HTTP_500_INTERNAL_SERVER_ERROR, ErrorMessage.generalTryAgain
            )
