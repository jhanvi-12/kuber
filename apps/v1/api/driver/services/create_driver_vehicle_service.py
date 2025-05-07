"""This module is responsible for the creation of the driver vehicle service."""

import uuid
from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from apps.v1.api.auth.models.attribute import UserTypeEnum
from apps.v1.api.auth.models.method import UserAuthMethod
from apps.v1.api.vehicle.models.method import VehicleMethod
from apps.v1.api.base_service import BaseResponseService
from apps.v1.api.driver.models.model import Driver
from apps.v1.api.vehicle.models.model import Vehicle
from core.utils import constant_variable as constant
from core.utils.db_method import DataBaseMethod
from fastapi.encoders import jsonable_encoder
from core.utils.message_variable import ErrorMessage, InfoMessage
from config import aws_config
from apps.v1.api.driver.serializer import DriverVehicleDocumentSchema


class DriverService(BaseResponseService):
    """This class includes the service methods for the driver."""

    async def create_driver_vehicle_service(
        self, db: AsyncSession, body, current_user: dict
    ):
        """This method is used to create a vehicle for the driver.

        Args:
            db (AsyncSession): database session
            body: request body
            current_user (dict): current user data.

        Returns:
            dict: response data
        """
        try:
            body = body.dict()
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

            existing_vehicle_obj = await VehicleMethod(Vehicle).find_by_driver_id(
                db, driver_id
            )
            if existing_vehicle_obj:
                return self.response(
                    status.HTTP_400_BAD_REQUEST,
                    ErrorMessage.driverVehicleAlreadyExists,
                )

            vehicle_obj = Vehicle(
                driver_id=driver_id,
                plate_number=body["plate_number"],
                vehicle_model=body["vehicle_model"],
                make=body["make"],
                ride_type=body["ride_type"],
            )

            if not await DataBaseMethod(Vehicle).save(vehicle_obj, db):
                return self.response(
                    status.HTTP_400_BAD_REQUEST, ErrorMessage.errorSavingUser
                )

            data = jsonable_encoder(vehicle_obj)
            return self.response(
                status.HTTP_201_CREATED,
                InfoMessage.driverVehicleCreatedSuccess,
                data,
            )
        except Exception:
            return self.response(
                status.HTTP_400_BAD_REQUEST, ErrorMessage.generalTryAgain
            )

    async def upload_driver_vehicle_docs(
        self, request, db: AsyncSession, data: dict, current_user: dict
    ):
        """This method is used to upload vehicle documents for the driver.

        Args:
            request: request object
            db (AsyncSession): database session
            data (dict): request body
            current_user (dict): current user data.
        Returns:
            dict: response data
        """
        try:
            driver_id = current_user["user_id"]
            if current_user["user_type"] != UserTypeEnum.DRIVER.value:
                return self.response(
                    status.HTTP_400_BAD_REQUEST, ErrorMessage.driverNotFound
                )
            driver_obj = await UserAuthMethod(Driver).find_by_id(db, driver_id)
            if not driver_obj:
                return self.response(
                    status.HTTP_404_NOT_FOUND, ErrorMessage.driverNotFound
                )

            vehicle_obj = await VehicleMethod(Vehicle).find_by_driver_id(db, driver_id)
            if not vehicle_obj:
                return self.response(
                    status.HTTP_404_NOT_FOUND, ErrorMessage.vehicleNotFound
                )

            driver_obj.license_number = data["license_number"]
            driver_obj.license_expiry_date = data["license_expiration_date"]
            vehicle_obj.vehicle_insurance_expiration_date = data[
                "vehicle_insurance_expiration_date"
            ]

            license_image_url = self.get_upload_file_to_s3(
                request,
                data["license_image"],
                f"{aws_config.S3_PATH_DRIVER_LICENSE_IMAGE}{uuid.uuid4()}",
            )
            vehicle_image_url = self.get_upload_file_to_s3(
                request,
                data["vehicle_image"],
                f"{aws_config.S3_PATH_DRIVER_VEHICLE_IMAGE}{uuid.uuid4()}",
            )
            vehicle_insurance_image_url = self.get_upload_file_to_s3(
                request,
                data["vehicle_insurance_image"],
                f"{aws_config.S3_PATH_DRIVER_VEHICLE_INSURANCE_IMAGE}{uuid.uuid4()}",
            )

            if (
                not license_image_url
                or not vehicle_image_url
                or not vehicle_insurance_image_url
            ):
                return self.response(
                    status.HTTP_400_BAD_REQUEST, ErrorMessage.errorSavingUser
                )

            driver_obj.license_image = license_image_url
            vehicle_obj.vehicle_image = vehicle_image_url
            vehicle_obj.vehicle_insurance_image = vehicle_insurance_image_url

            if not await DataBaseMethod(Vehicle).save(vehicle_obj, db):
                return self.response(
                    status.HTTP_400_BAD_REQUEST, ErrorMessage.errorSavingUser
                )

            if not await DataBaseMethod(Driver).save(driver_obj, db):
                return self.response(
                    status.HTTP_400_BAD_REQUEST, ErrorMessage.errorSavingUser
                )

            await db.commit()
            driver_vehicle_data = {**driver_obj.__dict__, "vehicle": vehicle_obj}

            data = jsonable_encoder(driver_vehicle_data)
            data.pop("password")

            if self.convert_datetime_format(data) is constant.STATUS_NULL:
                return self.response(
                    status.HTTP_400_BAD_REQUEST, ErrorMessage.generalTryAgain
                )

            response_data = DriverVehicleDocumentSchema().dump(data)
            response_data["vehicle_insurance_image"] = (
                f"{aws_config.AWS_BASE_URL}{response_data['vehicle_insurance_image']}"
            )
            response_data["vehicle_image"] = (
                f"{aws_config.AWS_BASE_URL}{response_data['vehicle_image']}"
            )
            response_data["license_image"] = (
                f"{aws_config.AWS_BASE_URL}{response_data['license_image']}"
            )

            return self.response(
                status.HTTP_200_OK,
                InfoMessage.driverVehicleDocsUploadedSuccess,
                response_data,
            )
        except Exception:
            return self.response(
                status.HTTP_400_BAD_REQUEST, ErrorMessage.generalTryAgain
            )
