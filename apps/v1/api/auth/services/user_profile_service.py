"""This module is used to defines the user profile related service functionality."""

import uuid
from datetime import datetime

from apps.v1.api.ride.models.attribute import RideStatusEnum
from fastapi import status
from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession

from apps.v1.api.auth.models.attribute import UserTypeEnum
from apps.v1.api.auth.models.model import OtpVerification, User
from apps.v1.api.base_service import BaseResponseService
from apps.v1.api.driver.models.model import Driver
from config import aws_config, mail_config
from core.utils import constant_variable as constant
from core.utils.db_method import DataBaseMethod
from core.utils.email_service import EmailService
from core.utils.message_variable import ErrorMessage, InfoMessage
from apps.v1.api.auth.serializer import UserProfileSchema
from apps.v1.api.ride.models.model import Ride
from apps.v1.api.auth.models.method import UserAuthMethod


class UserProfileService(BaseResponseService):
    """
    This class is used to define the user profile and edit profile methods.
    """

    async def get_user_profile_service(self, db: AsyncSession, current_user: dict):
        """This method is used to fetch the user profile details.

        Args:
            db (AsyncSession): database session
            current_user (dict): current user data.
        """
        try:
            user_obj = await self.get_current_user_details(db, current_user)
            if not user_obj:
                return self.response(
                    status.HTTP_401_UNAUTHORIZED, ErrorMessage.userNotFound
                )
            res = UserProfileSchema().dump(jsonable_encoder(user_obj))
            res["profile_image"] = (
                f"{aws_config.AWS_BASE_URL}{res['profile_image']}"
                if res.get("profile_image")
                else None
            )

            if user_obj.user_type == UserTypeEnum.DRIVER.value:
                res["ratings"] = user_obj.review
                total_trips = await DataBaseMethod(Ride).count(
                    db,
                    {
                        "driver_id": user_obj.id,
                        "status": RideStatusEnum.COMPLETED.value,
                    },
                )
                res["total_trips"] = total_trips
                res["total_earnings"] = await DataBaseMethod(Ride).sum(
                    db,
                    "ride_fare",
                    {
                        "driver_id": user_obj.id,
                        "status": RideStatusEnum.COMPLETED.value,
                    },
                )
            return self.response(
                status.HTTP_200_OK, InfoMessage.userRetrievedSuccess, res
            )

        except Exception:
            return self.response(
                status.HTTP_400_BAD_REQUEST, ErrorMessage.generalTryAgain
            )

    async def get_edit_user_profile_service(
        self, request, db: AsyncSession, body, current_user
    ):
        """This method is used to edit the user profile details.
        Args:
            db (AsyncSession): database session
            body: request body
            current_user (dict): current user data.
        Returns:
            dict: response data
        """
        try:
            user_obj = await self.get_current_user_details(db, current_user)
            if not user_obj:
                return self.response(
                    status.HTTP_401_UNAUTHORIZED, ErrorMessage.userNotFound
                )

            # Upload image to S3 bucket if provided
            if body.get("profile_image"):
                file_obj = self.get_upload_file_to_s3(
                    request,
                    body["profile_image"],
                    f"{aws_config.AWS_USER_PROFILE_PATH}{uuid.uuid4()}",
                )
            else:
                file_obj = user_obj.profile_image

            user_obj.profile_image = file_obj
            user_obj.full_name = (
                body.get("full_name")
                if body.get("full_name") is not None
                else user_obj.full_name
            )
            user_obj.email = (
                body.get("email") if body.get("email") is not None else user_obj.email
            )

            model = (
                Driver
                if current_user["user_type"] == UserTypeEnum.DRIVER.value
                else User
            )

            if not await DataBaseMethod(model).save(user_obj, db):
                return self.response(
                    status.HTTP_400_BAD_REQUEST, ErrorMessage.errorSavingUser
                )

            data = UserProfileSchema().dump(jsonable_encoder(user_obj))
            data["profile_image"] = (
                f"{aws_config.AWS_BASE_URL}{data['profile_image']}"
                if data.get("profile_image") is not None
                else None
            )

            return self.response(status.HTTP_200_OK, InfoMessage.userUpdated, data)
        except Exception:
            return self.response(
                status.HTTP_400_BAD_REQUEST, ErrorMessage.generalTryAgain
            )

    async def change_user_number_service(
        self, db: AsyncSession, current_user: dict, body: dict
    ):
        """This method is used to initiate the change of user's mobile number by generating and sending OTP to user's email."""
        try:
            # Validate mobile number
            mobile = body.get("mobile")
            if not self.validate_mobile_number(mobile):
                return self.response(
                    status.HTTP_400_BAD_REQUEST, ErrorMessage.invalidMobileNumber
                )

            user_obj = await self.get_current_user_details(db, current_user)
            if not user_obj:
                return self.response(
                    status.HTTP_401_UNAUTHORIZED, ErrorMessage.userNotFound
                )

            user_obj.mobile = mobile
            if not await DataBaseMethod(type(user_obj)).save(user_obj, db):
                return self.response(
                    status.HTTP_400_BAD_REQUEST, ErrorMessage.errorSavingUser
                )
            await db.commit()
            data = jsonable_encoder(user_obj)
            data.pop("password", None)
            if data.get("profile_image"):
                data["profile_image"] = (
                    f"{aws_config.AWS_BASE_URL}{data['profile_image']}"
                )
            return self.response(status.HTTP_200_OK, InfoMessage.numberChanged, data)
        except Exception:
            return self.response(
                status.HTTP_400_BAD_REQUEST, ErrorMessage.generalTryAgain
            )

    async def submit_review_service(
        self, db: AsyncSession, current_user: dict, body: dict
    ):
        """
        Customer submits a review for the driver after ride completion.
        Only customers can submit reviews — drivers cannot.
        """
        try:
            user_type = current_user.get("user_type")
            reviewer_id = current_user["user_id"]
            ride_id = body.get("ride_id")
            rating = body.get("rating")
            review = body.get("review", "")

            # --- Only customers allowed ---
            if user_type != UserTypeEnum.CUSTOMER.value:
                return self.response(
                    status.HTTP_403_FORBIDDEN,
                    ErrorMessage.notAuthorized
                )

            # --- Validate rating ---
            if not rating or not isinstance(rating, (int, float)):
                return self.response(
                    status.HTTP_400_BAD_REQUEST, ErrorMessage.invalidRating
                )
            if float(rating) < 1 or float(rating) > 5:
                return self.response(
                    status.HTTP_400_BAD_REQUEST, ErrorMessage.invalidRating
                )
            rating = round(float(rating), 1)

            # --- Validate ride ---
            ride_obj = await UserAuthMethod(Ride).find_by_id(db, ride_id)
            if not ride_obj:
                return self.response(
                    status.HTTP_404_NOT_FOUND, ErrorMessage.rideNotFound
                )

            # --- Verify customer owns this ride ---
            if ride_obj.user_id != reviewer_id:
                return self.response(
                    status.HTTP_403_FORBIDDEN, ErrorMessage.notAuthorized
                )

            # --- Ride must be completed ---
            if ride_obj.status != RideStatusEnum.COMPLETED.value:
                return self.response(
                    status.HTTP_400_BAD_REQUEST,
                    ErrorMessage.cannotReviewIncompleteRide
                )

            # --- Prevent duplicate review ---
            if ride_obj.driver_rating is not None:
                return self.response(
                    status.HTTP_400_BAD_REQUEST,
                    ErrorMessage.reviewAlreadySubmitted
                )

            # --- Fetch driver ---
            driver_obj = await UserAuthMethod(Driver).find_by_id(db, ride_obj.driver_id)
            if not driver_obj:
                return self.response(
                    status.HTTP_404_NOT_FOUND, ErrorMessage.driverNotFound
                )

            # --- Update driver average rating ---
            driver_obj.review, driver_obj.total_reviews = self._calculate_new_average(
                current_avg=driver_obj.review or 0.0,
                total_reviews=driver_obj.total_reviews or 0,
                new_rating=rating,
            )

            # --- Save review on ride ---
            ride_obj.driver_rating = rating
            ride_obj.driver_review = review

            db.add(driver_obj)
            db.add(ride_obj)
            await db.commit()
            return self.response(status.HTTP_200_OK, InfoMessage.reviewSubmitted)

        except Exception:

            await db.rollback()
            return self.response(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                ErrorMessage.generalTryAgain
            )

    # ---------------------------------------------------------------------------
    # Running average helper — keep this, still needed for driver ratings
    # ---------------------------------------------------------------------------
    @staticmethod
    def _calculate_new_average(
        current_avg: float,
        total_reviews: int,
        new_rating: float,
    ) -> tuple[float, int]:
        """
        Formula: new_avg = (current_avg * total_reviews + new_rating) / (total_reviews + 1)
        """
        new_total = total_reviews + 1
        new_avg = round((current_avg * total_reviews + new_rating) / new_total, 2)
        return new_avg, new_total
