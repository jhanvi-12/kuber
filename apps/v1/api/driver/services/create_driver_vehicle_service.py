"""This module is responsible for the creation of the driver vehicle service."""

import uuid

from fastapi import status
from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession

from apps.v1.api.auth.models.attribute import UserTypeEnum
from apps.v1.api.auth.models.method import UserAuthMethod
from apps.v1.api.base_service import BaseResponseService
from apps.v1.api.driver.models.model import Driver
from apps.v1.api.driver.serializer import DriverVehicleDocumentSchema
from apps.v1.api.vehicle.models.method import VehicleMethod
from apps.v1.api.vehicle.models.model import Vehicle
from config import aws_config
from core.utils import constant_variable as constant
from core.utils.db_method import DataBaseMethod
from core.utils.message_variable import ErrorMessage, InfoMessage


class DriverService(BaseResponseService):
    """This class includes the service methods for the driver."""

    async def create_driver_vehicle_and_docs_service(
        self,
        request,
        db: AsyncSession,
        body,
        files: dict,
        current_user: dict,
    ):
        """
        Create vehicle + upload documents in a single flow
        """
        try:
            body_data = body.dict()
            driver_id = current_user.get("user_id")

            # Validate user
            if current_user.get("user_type") != UserTypeEnum.DRIVER.value:
                return self.response(
                    status.HTTP_400_BAD_REQUEST,
                    ErrorMessage.driverNotFound,
                )

            driver_obj = await UserAuthMethod(Driver).find_by_id(db, driver_id)
            if not driver_obj:
                return self.response(
                    status.HTTP_404_NOT_FOUND,
                    ErrorMessage.driverNotFound,
                )

            # Check existing vehicle
            existing_vehicle = await VehicleMethod(Vehicle).find_by_driver_id(
                db, driver_id
            )
            if existing_vehicle:
                return self.response(
                    status.HTTP_400_BAD_REQUEST,
                    ErrorMessage.driverVehicleAlreadyExists,
                )

            # Create vehicle
            vehicle_obj = Vehicle(
                driver_id=driver_id,
                plate_number=body_data["vehicle_number"],
                vehicle_model=body_data["vehicle_model"],
                make=body_data["make"],
                ride_type=body_data["vehicle_type"],
                vehicle_insurance_expiration_date=body_data[
                    "vehicle_insurance_expiration_date"
                ],
            )
            # Upload images to S3
            license_image_url = self.get_upload_file_to_s3(
                request,
                files["license_image"],
                f"{aws_config.S3_PATH_DRIVER_LICENSE_IMAGE}{uuid.uuid4()}",
            )

            vehicle_image_url = self.get_upload_file_to_s3(
                request,
                files["vehicle_image"],
                f"{aws_config.S3_PATH_DRIVER_VEHICLE_IMAGE}{uuid.uuid4()}",
            )

            insurance_image_url = self.get_upload_file_to_s3(
                request,
                files["vehicle_insurance_image"],
                f"{aws_config.S3_PATH_DRIVER_VEHICLE_INSURANCE_IMAGE}{uuid.uuid4()}",
            )

            if not all(
                [license_image_url, vehicle_image_url, insurance_image_url]
            ):
                return self.response(
                    status.HTTP_400_BAD_REQUEST,
                    ErrorMessage.errorSavingUser,
                )

            # 5️⃣ Update driver & vehicle docs
            driver_obj.license_number = body_data["license_number"]
            driver_obj.license_expiry_date = body_data["license_expiration_date"]
            driver_obj.license_image = license_image_url

            vehicle_obj.vehicle_image = vehicle_image_url
            vehicle_obj.vehicle_insurance_image = insurance_image_url

            # Save all (single transaction)
            if not await DataBaseMethod(Driver).save(driver_obj, db):
                return self.response(
                    status.HTTP_400_BAD_REQUEST,
                    ErrorMessage.errorSavingUser,
                )

            if not await DataBaseMethod(Vehicle).save(vehicle_obj, db):
                return self.response(
                    status.HTTP_400_BAD_REQUEST,
                    ErrorMessage.errorSavingUser,
                )

            # Prepare response
            driver_vehicle_data = {
                **driver_obj.__dict__,
                "vehicle": vehicle_obj,
            }

            data = jsonable_encoder(driver_vehicle_data)
            data.pop("password", None)

            if self.convert_datetime_format(data) is constant.STATUS_NULL:
                return self.response(
                    status.HTTP_400_BAD_REQUEST,
                    ErrorMessage.generalTryAgain,
                )

            response_data = DriverVehicleDocumentSchema().dump(data)

            response_data["license_image"] = (
                f"{aws_config.AWS_BASE_URL}{response_data['license_image']}"
            )
            response_data["vehicle_image"] = (
                f"{aws_config.AWS_BASE_URL}{response_data['vehicle_image']}"
            )
            response_data["vehicle_insurance_image"] = (
                f"{aws_config.AWS_BASE_URL}{response_data['vehicle_insurance_image']}"
            )

            return self.response(
                status.HTTP_201_CREATED,
                InfoMessage.driverVehicleCreatedSuccess,
                response_data,
            )

        except Exception:
            return self.response(
                status.HTTP_400_BAD_REQUEST,
                ErrorMessage.generalTryAgain,
            )
