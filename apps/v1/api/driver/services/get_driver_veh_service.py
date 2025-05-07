""" "This module is responsible for the driver vehicle details schema."""

from apps.v1.api.base_service import BaseResponseService
from apps.v1.api.driver.models.model import Driver
from apps.v1.api.vehicle.models.model import Vehicle
from core.utils.message_variable import ErrorMessage, InfoMessage
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import status
from apps.v1.api.auth.models.attribute import UserTypeEnum
from apps.v1.api.auth.models.method import UserAuthMethod
from apps.v1.api.vehicle.models.method import VehicleMethod
from fastapi.encoders import jsonable_encoder


class GetDriverService(BaseResponseService):
    """This class represents the driver vehicle details service"""

    async def get_driver_vehicle_service(self, db: AsyncSession, current_user: dict):
        """This method is used to fetch the driver vehicle details.

        Args:
            db (AsyncSession): database session
            current_user (dict): current user data.
        """
        try:
            driver_id = current_user["user_id"]
            if current_user["user_type"] != UserTypeEnum.DRIVER.value:
                return self.response(
                    status.HTTP_400_BAD_REQUEST, ErrorMessage.userNotFound
                )
            driver_obj = await UserAuthMethod(Driver).find_by_id(db, driver_id)
            if not driver_obj:
                return self.response(
                    status.HTTP_404_NOT_FOUND, ErrorMessage.driverNotFound
                )

            vehicle_data = await VehicleMethod(Vehicle).find_by_driver_id(db, driver_id)
            if not vehicle_data:
                return self.response(
                    status.HTTP_404_NOT_FOUND, ErrorMessage.vehicleNotFound
                )

            data = jsonable_encoder(vehicle_data)

            return self.response(
                status.HTTP_200_OK, InfoMessage.userRetrievedSuccess, data
            )

        except Exception:
            return self.response(
                status.HTTP_400_BAD_REQUEST, ErrorMessage.generalTryAgain
            )
