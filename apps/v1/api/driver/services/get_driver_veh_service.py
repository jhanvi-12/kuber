""" "This module is responsible for the driver vehicle details schema."""

from datetime import datetime
from fastapi import status
from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession

from apps.v1.api.auth.models.attribute import UserTypeEnum
from apps.v1.api.auth.models.method import UserAuthMethod
from apps.v1.api.auth.models.model import Admin
from apps.v1.api.base_service import BaseResponseService
from apps.v1.api.driver.models.model import Driver
from apps.v1.api.vehicle.models.method import VehicleMethod
from apps.v1.api.vehicle.models.model import Vehicle
from core.utils.message_variable import ErrorMessage, InfoMessage
from config import aws_config
from apps.v1.api.ride.serializer import DriverListResponseSchema
from apps.v1.api.driver.models.attribute import DriverStatusEnum
from core.utils import constant_variable as constant


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
            data["vehicle_image"] = (
                f"{aws_config.AWS_BASE_URL}{vehicle_data.vehicle_image}"
                if vehicle_data.vehicle_image is not None
                else None
            )
            data["vehicle_insurance_image"] = (
                f"{aws_config.AWS_BASE_URL}{vehicle_data.vehicle_insurance_image}"
                if vehicle_data.vehicle_insurance_image is not None
                else None
            )
            data["license_image"] = (
                f"{aws_config.AWS_BASE_URL}{driver_obj.license_image}"
                if driver_obj.license_image is not None
                else None
            )
            data["license_number"] = driver_obj.license_number
            data["license_expiry_date"] = driver_obj.license_expiry_date.strftime("%Y-%m-%dT%H:%M:%S") if driver_obj.license_expiry_date else None

            return self.response(
                status.HTTP_200_OK, InfoMessage.userRetrievedSuccess, data
            )

        except Exception:
            return self.response(
                status.HTTP_400_BAD_REQUEST, ErrorMessage.generalTryAgain
            )

    async def fetch_drivers_list_service(
        self,
        db: AsyncSession,
        current_user: dict,
        page: int = 1,
        search_query: str = None,
    ):
        """This method is used to fetch the drivers list with pagination response."""
        try:
            # Validate admin
            admin_id = current_user.get("user_id")
            admin_obj = await UserAuthMethod(Admin).find_by_id(db, admin_id)
            if not admin_obj:
                return self.response(
                    status.HTTP_400_BAD_REQUEST, ErrorMessage.adminNotFound
                )

            drivers_data = await UserAuthMethod(
                Driver
            ).find_drivers_list_with_pagination(db, page, search_query)

            data = DriverListResponseSchema().dump(drivers_data)

            for i in data["drivers"]:
                driver_veh_obj = await UserAuthMethod(Vehicle).find_by_driver_id(
                    db, i["id"]
                )
                i["ride_type"] = (
                    driver_veh_obj.ride_type if driver_veh_obj is not None else None
                )

            return self.response(status.HTTP_200_OK, InfoMessage.driversFetched, data)

        except Exception:
            return self.response(
                status.HTTP_400_BAD_REQUEST, ErrorMessage.generalTryAgain
            )

    async def driver_approve_reject_by_admin_service(
        self, db: AsyncSession, current_user: dict, body: dict
    ):
        """
        Admin approves or rejects a driver.
        - Approve: ride_type is mandatory, updates vehicle ride_type
        - Reject: reason is mandatory
        """
        try:
            # --- Validate admin ---
            admin_id = current_user.get("user_id")
            admin_obj = await UserAuthMethod(Admin).find_by_id(db, admin_id)
            if not admin_obj:
                return self.response(status.HTTP_403_FORBIDDEN, ErrorMessage.adminNotFound)

            # --- Validate driver ---
            driver_id = body.get("driver_id")
            if not driver_id:
                return self.response(status.HTTP_400_BAD_REQUEST, ErrorMessage.drivernotFound)

            driver_obj = await UserAuthMethod(Driver).find_by_id(db, driver_id)
            if not driver_obj:
                return self.response(status.HTTP_404_NOT_FOUND, ErrorMessage.driverNotFound)

            # --- Determine approval status ---
            is_approved = body.get("status") == constant.STATUS_ONE
            is_docs_verified = (
                int(DriverStatusEnum.APPROVED.value)
                if is_approved
                else int(DriverStatusEnum.REJECTED.value)
            )

            if is_approved:
                # --- Approval: ride_type is mandatory ---
                ride_type = body.get("ride_type")
                if not ride_type:
                    return self.response(
                        status.HTTP_400_BAD_REQUEST,
                        ErrorMessage.rideTypeRequired  # "ride_type is required to approve a driver"
                    )

                # --- Update vehicle ride_type ---
                veh_obj = await VehicleMethod(Vehicle).find_by_driver_id(db, driver_id)
                if not veh_obj:
                    return self.response(
                        status.HTTP_404_NOT_FOUND,
                        ErrorMessage.vehicleNotFound  # driver must have a vehicle to be approved
                    )
                veh_obj.ride_type = ride_type
                db.add(veh_obj)

                # Clear rejection reason if previously rejected
                driver_obj.reason = None

            else:
                # --- Rejection: reason is mandatory ---
                reason = body.get("reason")
                if not reason or not str(reason).strip():
                    return self.response(
                        status.HTTP_400_BAD_REQUEST,
                        ErrorMessage.rejectionReasonRequired  # "reason is required to reject a driver"
                    )
                driver_obj.reason = str(reason).strip()

            # --- Update driver verification status ---
            driver_obj.is_docs_verified = is_docs_verified
            db.add(driver_obj)
            await db.commit()
            await db.refresh(driver_obj)

            # --- Build safe response ---
            data = jsonable_encoder(driver_obj)
            data.pop("password", None)
            data.pop("device_token", None)

            return self.response(status.HTTP_200_OK, InfoMessage.driverStatusUpdated, data)

        except Exception:
            await db.rollback()
            return self.response(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                ErrorMessage.generalTryAgain
            )
