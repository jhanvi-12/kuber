"""This module is responsible to maintain the book ride service logic."""

import asyncio
import json
import math
import uuid
from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from apps.v1.api.auth.models.method import UserAuthMethod
from apps.v1.api.auth.models.model import User
from apps.v1.api.base_service import BaseResponseService
from apps.v1.api.driver.services.driver_search_service import \
    DriverSearchService
from apps.v1.api.ride.models.attribute import RideStatusEnum
from apps.v1.api.ride.services.coupon_service import CouponService
from apps.v1.api.ride.services.socket_emitter import RideSocketEmitter
from core.dispatch_queue import enqueue_dispatch_job
from core.redis_repo import RedisRideRepo
from core.utils import constant_variable as constant
from core.utils.message_variable import *
from config import env_config


class BookRideService(BaseResponseService):
    """This class is used to define the book ride service methods."""

    def calculate_distance(
        self, lat1: float, lon1: float, lat2: float, lon2: float
    ) -> float:
        """
        Calculate the great-circle distance between two points on the Earth using Haversine formula.
        Returns distance in kilometers.

        Args:
            lat1 (float): Latitude of first point
            lon1 (float): Longitude of first point
            lat2 (float): Latitude of second point
            lon2 (float): Longitude of second point

        Returns:
            float: Distance in kilometers
        """
        R = 6371  # Radius of the Earth in km
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)

        a = (
            math.sin(delta_lat / 2) ** 2
            + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
        )

        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        distance = R * c
        return distance

    async def create_book_ride_service(
        self, db: AsyncSession, body: dict, current_user: dict
    ):
        """
        Books a ride for the user.

        Args:
            db (AsyncSession): The database session.
            body (dict): The request body containing ride details.
            current_user (dict): The current user's information.

        Returns:
            dict: A response indicating the success or failure of the ride booking.
        """
        try:
            body = body.dict()
            user_id = current_user.get("user_id")
            user_obj = await UserAuthMethod(User).find_by_id(
                db, user_id
            )
            if not user_obj:
                return self.response(
                    status.HTTP_401_UNAUTHORIZED, ErrorMessage.userNotFound
                )
            # Generate a Ride Request ID for the temp in redis.
            ride_request_id = str(uuid.uuid4())
            coupon_code = body.get("coupon_code")
            # Validate coupon if provided
            if coupon_code:
                result = await CouponService().validate_and_apply(
                    db,
                    user_id,
                    coupon_code,
                    body.get("ride_type")
                )

                if not json.loads(result.body)["status"] == "success":
                    return self.response(
                        status.HTTP_400_BAD_REQUEST,
                        ErrorMessage.couponAlreadyUserOrInvalid,
                    )
            payload = {
                    "pickup_latitude": body["pickup_latitude"],
                    "pickup_longitude": body["pickup_longitude"],
                    "pickup_address": body["pickup_address"],
                    "destination_latitude": body["destination_latitude"],
                    "destination_longitude": body["destination_longitude"],
                    "destination_address": body["destination_address"],
                    "ride_type": body["ride_type"],
                    "ride_fare": body["ride_fare"],
                    "discount_fare": body.get("discount_fare", 0.0),
                    "total_fare": body.get("total_fare", body["ride_fare"]),
                    "distance": body.get("distance", 0.0),
                    "duration": body.get("duration", 0.0),
                    "coupon_code": body.get("coupon_code", None)
                }
            # Store ride request in the redis
            await RedisRideRepo.init_search_state(
                ride_request_id=ride_request_id,
                user_id=current_user["user_id"],
                payload=payload
            )
            # Emit searching state
            user_data = {
                "status": RideStatusEnum.INITIAL.value,
                "ride_request_id": ride_request_id,
                "pickup_latitude": body["pickup_latitude"],
                "pickup_longitude": body["pickup_longitude"],
                "pickup_address": body["pickup_address"],
                "destination_latitude": body["destination_latitude"],
                "destination_longitude": body["destination_longitude"],
                "destination_address": body["destination_address"],
                "ride_fare": body["total_fare"],
                "username": user_obj.full_name,
                "mobile_number": user_obj.mobile
            }
            await RideSocketEmitter.ride_searching(
                ride_request_id, user_id=current_user["user_id"]
            )

            dispatch_mode = env_config.DISPATCH_MODE  # queue | inline
            if dispatch_mode == "queue":
                await enqueue_dispatch_job(
                    ride_request_id=ride_request_id,
                    ride_type=body.get("ride_type"),
                    lat=body.get("pickup_latitude"),
                    lng=body.get("pickup_longitude"),
                    user_data=user_data,
                    user_id=current_user["user_id"],
                )
            else:
                # Start driver search ASYNC (background, inline mode)
                asyncio.create_task(
                    DriverSearchService.start_wave(
                        ride_request_id,
                        body.get("ride_type"),
                        body.get("pickup_latitude"),
                        body.get("pickup_longitude"),
                        user_data,
                        user_id=current_user["user_id"],
                    )
                )

            return self.response(
                status.HTTP_200_OK, InfoMessage.findingDrivers,
                {
                    "ride_request_id": ride_request_id,
                    "status": RideStatusEnum.INITIAL.value
                }
            )

        except Exception:
            return self.response(
                status.HTTP_400_BAD_REQUEST, ErrorMessage.generalTryAgain
            )
